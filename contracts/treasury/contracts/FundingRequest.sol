// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

interface ICurrency {
    function mint(address to, uint256 amount) external;
    function burn(address from, uint256 amount) external;
}

/// Cross-border branch funding: a request is created, approved (mints CADC to the treasury),
/// settled (burns CADC, mints GBPC at a recorded rate) and redeemed (burns GBPC).
/// Roles are fixed at deployment. Amounts are minor units (2 decimals), rates are parts per million.
/// Reverts use plain strings: FireFly's error text carries only Error("...") reasons.
contract FundingRequest {
    enum Status { None, Requested, Approved, Rejected, Settled, Redeemed }

    struct Request {
        address requester; // also the beneficiary
        uint32 processingDate; // yyyymmdd of the requester's local date
        Status status;
        uint256 amountCad;
        uint256 amountGbp; // 0 until Settled
        uint32 ratePpm; // 0 until Settled
        address approver; // set on approve or reject
    }

    uint256 public constant RATE_SCALE = 1_000_000;
    uint256 public constant MAX_REASON_LENGTH = 140;

    ICurrency public immutable cadc;
    ICurrency public immutable gbpc;
    address public immutable treasury;
    uint256 public immutable maxAmountCad;
    uint32 public immutable minRatePpm;
    uint32 public immutable maxRatePpm;

    mapping(address => bool) private requesters;
    mapping(address => bool) private approvers;

    mapping(bytes32 => Request) private requests;
    bytes32[] private ids;

    event Requested(bytes32 indexed id, address indexed requester, uint256 amountCad, uint32 processingDate);
    event Approved(bytes32 indexed id, address indexed approver, uint256 amountCad);
    event Rejected(bytes32 indexed id, address indexed approver, string reason);
    event Settled(bytes32 indexed id, uint256 amountCad, uint256 amountGbp, uint32 ratePpm);
    event Redeemed(bytes32 indexed id, address indexed beneficiary, uint256 amountGbp);

    constructor(
        address cadc_,
        address gbpc_,
        address treasury_,
        address[] memory requesters_,
        address[] memory approvers_,
        uint256 maxAmountCad_,
        uint32 minRatePpm_,
        uint32 maxRatePpm_
    ) {
        require(cadc_ != address(0) && gbpc_ != address(0) && treasury_ != address(0), "BadAddress");
        require(maxAmountCad_ > 0, "BadAmount");
        require(minRatePpm_ > 0 && minRatePpm_ <= maxRatePpm_, "BadRate");
        cadc = ICurrency(cadc_);
        gbpc = ICurrency(gbpc_);
        treasury = treasury_;
        maxAmountCad = maxAmountCad_;
        minRatePpm = minRatePpm_;
        maxRatePpm = maxRatePpm_;
        for (uint256 i = 0; i < requesters_.length; i++) {
            requesters[requesters_[i]] = true;
        }
        for (uint256 i = 0; i < approvers_.length; i++) {
            approvers[approvers_[i]] = true;
        }
    }

    function createRequest(bytes32 id, uint256 amountCad, uint32 processingDate) external {
        require(requesters[msg.sender], "NotRequester");
        require(requests[id].status == Status.None, "Exists");
        require(amountCad > 0 && amountCad <= maxAmountCad, "BadAmount");
        require(_validDate(processingDate), "BadDate");
        requests[id] = Request({
            requester: msg.sender,
            processingDate: processingDate,
            status: Status.Requested,
            amountCad: amountCad,
            amountGbp: 0,
            ratePpm: 0,
            approver: address(0)
        });
        ids.push(id);
        emit Requested(id, msg.sender, amountCad, processingDate);
    }

    function approve(bytes32 id) external {
        Request storage r = _decidable(id);
        r.status = Status.Approved;
        r.approver = msg.sender;
        emit Approved(id, msg.sender, r.amountCad);
        cadc.mint(treasury, r.amountCad);
    }

    function reject(bytes32 id, string calldata reason) external {
        require(bytes(reason).length <= MAX_REASON_LENGTH, "ReasonTooLong");
        Request storage r = _decidable(id);
        r.status = Status.Rejected;
        r.approver = msg.sender;
        emit Rejected(id, msg.sender, reason);
    }

    function settle(bytes32 id, uint32 ratePpm) external {
        Request storage r = requests[id];
        require(r.status == Status.Approved, "BadState");
        require(msg.sender == treasury, "NotTreasury");
        require(ratePpm >= minRatePpm && ratePpm <= maxRatePpm, "BadRate");
        uint256 gbp = (r.amountCad * ratePpm) / RATE_SCALE;
        require(gbp > 0, "BadAmount");
        r.status = Status.Settled;
        r.amountGbp = gbp;
        r.ratePpm = ratePpm;
        emit Settled(id, r.amountCad, gbp, ratePpm);
        cadc.burn(treasury, r.amountCad);
        gbpc.mint(r.requester, gbp);
    }

    function redeem(bytes32 id) external {
        Request storage r = requests[id];
        require(r.status == Status.Settled, "BadState");
        require(msg.sender == r.requester, "NotBeneficiary");
        r.status = Status.Redeemed;
        emit Redeemed(id, msg.sender, r.amountGbp);
        gbpc.burn(msg.sender, r.amountGbp);
    }

    function isRequester(address account) external view returns (bool) {
        return requesters[account];
    }

    function isApprover(address account) external view returns (bool) {
        return approvers[account];
    }

    function getRequest(bytes32 id) external view returns (Request memory) {
        return requests[id];
    }

    function requestCount() external view returns (uint256) {
        return ids.length;
    }

    function requestIdAt(uint256 index) external view returns (bytes32) {
        return ids[index];
    }

    /// A request still waiting for a decision, and the caller may decide it.
    function _decidable(bytes32 id) private view returns (Request storage r) {
        r = requests[id];
        require(r.status == Status.Requested, "BadState");
        require(approvers[msg.sender], "NotApprover");
        require(msg.sender != r.requester, "SelfApproval");
    }

    function _validDate(uint32 d) private pure returns (bool) {
        uint32 month = (d / 100) % 100;
        uint32 day = d % 100;
        return d >= 20000101 && d <= 29991231 && month >= 1 && month <= 12 && day >= 1 && day <= 31;
    }
}
