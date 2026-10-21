// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

import { Vm, VM_ADDRESS } from "./Vm.sol";
import { CurrencyToken } from "../contracts/CurrencyToken.sol";
import { FundingRequest } from "../contracts/FundingRequest.sol";

contract FundingRequestTest {
    Vm constant vm = Vm(VM_ADDRESS);

    address constant LDN = address(0xA1);
    address constant TOR = address(0xA2);
    address constant TREASURY = address(0xA3);
    address constant OTHER = address(0xA4);

    uint256 constant CAP = 100_000_000; // CAD 1,000,000.00
    uint32 constant MIN_RATE = 10_000; // 0.010000
    uint32 constant MAX_RATE = 5_000_000; // 5.000000
    uint32 constant RATE = 580_000; // 0.580000
    uint32 constant DATE = 20261018;
    bytes32 constant ID = bytes32(uint256(1));

    CurrencyToken cadc;
    CurrencyToken gbpc;
    FundingRequest fr;

    function setUp() public {
        cadc = new CurrencyToken("Canadian Dollar Coin", "CADC", address(this));
        gbpc = new CurrencyToken("Pound Sterling Coin", "GBPC", address(this));
        address[] memory requesters = new address[](1);
        requesters[0] = LDN;
        address[] memory approvers = new address[](1);
        approvers[0] = TOR;
        fr = new FundingRequest(
            address(cadc), address(gbpc), TREASURY, requesters, approvers, CAP, MIN_RATE, MAX_RATE
        );
        cadc.setController(address(fr));
        gbpc.setController(address(fr));
    }

    // ---- helpers ----

    function _create(bytes32 id, uint256 amount) internal {
        vm.prank(LDN);
        fr.createRequest(id, amount, DATE);
    }

    function _approve(bytes32 id) internal {
        vm.prank(TOR);
        fr.approve(id);
    }

    function _settle(bytes32 id, uint32 rate) internal {
        vm.prank(TREASURY);
        fr.settle(id, rate);
    }

    function _status(bytes32 id) internal view returns (FundingRequest.Status) {
        return fr.getRequest(id).status;
    }

    // ---- create ----

    function test_CreateStoresTheRequest() public {
        _create(ID, 100000);
        FundingRequest.Request memory r = fr.getRequest(ID);
        require(r.requester == LDN, "requester");
        require(r.amountCad == 100000, "amount");
        require(r.processingDate == DATE, "date");
        require(r.status == FundingRequest.Status.Requested, "status");
        require(fr.requestCount() == 1 && fr.requestIdAt(0) == ID, "index");
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == 0, "nothing minted yet");
    }

    function test_CreateRequiresTheRequesterRole() public {
        vm.prank(OTHER);
        vm.expectRevert("NotRequester");
        fr.createRequest(ID, 100000, DATE);

        vm.prank(TOR);
        vm.expectRevert("NotRequester");
        fr.createRequest(ID, 100000, DATE);
    }

    function test_CreateRejectsADuplicateId() public {
        _create(ID, 100000);
        vm.prank(LDN);
        vm.expectRevert("Exists");
        fr.createRequest(ID, 5, DATE);
    }

    function test_CreateRejectsBadAmounts() public {
        vm.prank(LDN);
        vm.expectRevert("BadAmount");
        fr.createRequest(ID, 0, DATE);

        vm.prank(LDN);
        vm.expectRevert("BadAmount");
        fr.createRequest(ID, CAP + 1, DATE);

        _create(ID, CAP); // the cap itself is allowed
    }

    function test_CreateRejectsBadDates() public {
        uint32[6] memory bad = [uint32(0), 19991231, 30000101, 20261301, 20260001, 20261032];
        for (uint256 i = 0; i < bad.length; i++) {
            vm.prank(LDN);
            vm.expectRevert("BadDate");
            fr.createRequest(bytes32(i + 100), 100, bad[i]);
        }
    }

    // ---- approve and reject ----

    function test_ApproveMintsCadToTheTreasury() public {
        _create(ID, 100000);
        _approve(ID);
        require(_status(ID) == FundingRequest.Status.Approved, "status");
        require(fr.getRequest(ID).approver == TOR, "approver");
        require(cadc.balanceOf(TREASURY) == 100000, "treasury CADC");
        require(cadc.totalSupply() == 100000, "supply");
    }

    function test_ApproveRules() public {
        _create(ID, 100000);

        vm.prank(OTHER);
        vm.expectRevert("NotApprover");
        fr.approve(ID);

        vm.prank(TREASURY);
        vm.expectRevert("NotApprover");
        fr.approve(ID);

        vm.prank(LDN); // the requester is not an approver either
        vm.expectRevert("NotApprover");
        fr.approve(ID);

        vm.expectRevert("BadState");
        fr.approve(bytes32(uint256(99))); // no such request, called by a non-approver
        require(cadc.totalSupply() == 0, "nothing minted by the failed calls");
    }

    function test_ARequesterWhoIsAlsoAnApproverCannotApproveTheirOwnRequest() public {
        address[] memory both = new address[](1);
        both[0] = LDN;
        FundingRequest fr2 = new FundingRequest(
            address(cadc), address(gbpc), TREASURY, both, both, CAP, MIN_RATE, MAX_RATE
        );
        vm.prank(LDN);
        fr2.createRequest(ID, 100, DATE);
        vm.prank(LDN);
        vm.expectRevert("SelfApproval");
        fr2.approve(ID);
        vm.prank(LDN);
        vm.expectRevert("SelfApproval");
        fr2.reject(ID, "mine");
    }

    function test_ApproveTwiceReverts() public {
        _create(ID, 100000);
        _approve(ID);
        vm.prank(TOR);
        vm.expectRevert("BadState");
        fr.approve(ID);
        require(cadc.totalSupply() == 100000, "minted once");
    }

    function test_RejectMintsNothing() public {
        _create(ID, 100000);
        vm.prank(TOR);
        fr.reject(ID, "over budget");
        require(_status(ID) == FundingRequest.Status.Rejected, "status");
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == 0, "no tokens");

        vm.prank(TOR);
        vm.expectRevert("BadState");
        fr.approve(ID);
    }

    function test_RejectRules() public {
        _create(ID, 100000);

        vm.prank(OTHER);
        vm.expectRevert("NotApprover");
        fr.reject(ID, "x");

        string memory limit = new string(140);
        vm.prank(TOR);
        fr.reject(ID, limit); // 140 characters is allowed

        _create(bytes32(uint256(2)), 100);
        string memory tooLong = new string(141);
        vm.prank(TOR);
        vm.expectRevert("ReasonTooLong");
        fr.reject(bytes32(uint256(2)), tooLong);
    }

    // ---- settle ----

    function test_SettleBurnsCadAndMintsGbp() public {
        _create(ID, 100000);
        _approve(ID);
        _settle(ID, RATE);

        FundingRequest.Request memory r = fr.getRequest(ID);
        require(r.status == FundingRequest.Status.Settled, "status");
        require(r.amountGbp == 58000, "gbp");
        require(r.ratePpm == RATE, "rate");
        require(cadc.totalSupply() == 0 && cadc.balanceOf(TREASURY) == 0, "CADC burned");
        require(gbpc.balanceOf(LDN) == 58000 && gbpc.totalSupply() == 58000, "GBPC minted to LDN");
    }

    function test_SettleRoundsDown() public {
        _create(ID, 10001);
        _approve(ID);
        _settle(ID, RATE); // 100.01 CAD x 0.58 = 58.0058
        require(fr.getRequest(ID).amountGbp == 5800, "floor");
    }

    function test_SettleRules() public {
        _create(ID, 100000);

        vm.prank(TREASURY);
        vm.expectRevert("BadState"); // not approved yet
        fr.settle(ID, RATE);

        _approve(ID);

        vm.prank(TOR);
        vm.expectRevert("NotTreasury");
        fr.settle(ID, RATE);

        vm.prank(LDN);
        vm.expectRevert("NotTreasury");
        fr.settle(ID, RATE);

        uint32[3] memory badRates = [uint32(0), MIN_RATE - 1, MAX_RATE + 1];
        for (uint256 i = 0; i < badRates.length; i++) {
            vm.prank(TREASURY);
            vm.expectRevert("BadRate");
            fr.settle(ID, badRates[i]);
        }

        _settle(ID, MIN_RATE); // the bounds themselves are allowed
        vm.prank(TREASURY);
        vm.expectRevert("BadState"); // twice
        fr.settle(ID, RATE);
    }

    function test_SettleThatRoundsToZeroReverts() public {
        _create(ID, 1); // 0.01 CAD
        _approve(ID);
        vm.prank(TREASURY);
        vm.expectRevert("BadAmount"); // 1 x 0.58 = 0 pence
        fr.settle(ID, RATE);
        require(_status(ID) == FundingRequest.Status.Approved, "still approved");
        require(cadc.balanceOf(TREASURY) == 1, "CADC still held");
    }

    // ---- redeem ----

    function test_RedeemBurnsTheGbp() public {
        _create(ID, 100000);
        _approve(ID);
        _settle(ID, RATE);
        vm.prank(LDN);
        fr.redeem(ID);
        require(_status(ID) == FundingRequest.Status.Redeemed, "status");
        require(gbpc.totalSupply() == 0 && gbpc.balanceOf(LDN) == 0, "GBPC burned");
        require(fr.getRequest(ID).amountGbp == 58000, "the record keeps the amount");
    }

    function test_RedeemRules() public {
        _create(ID, 100000);
        vm.prank(LDN);
        vm.expectRevert("BadState"); // before settlement
        fr.redeem(ID);

        _approve(ID);
        _settle(ID, RATE);

        vm.prank(TOR);
        vm.expectRevert("NotBeneficiary");
        fr.redeem(ID);

        vm.prank(LDN);
        fr.redeem(ID);
        vm.prank(LDN);
        vm.expectRevert("BadState"); // twice
        fr.redeem(ID);
    }

    /// The GBPC of a settled request cannot be sent elsewhere, so `redeem` always has it to burn.
    function test_TheBeneficiaryCannotSendTheGbpAwayBeforeRedeeming() public {
        _create(ID, 100000);
        _approve(ID);
        _settle(ID, RATE);
        vm.prank(LDN);
        (bool sent,) = address(gbpc).call(abi.encodeWithSignature("transfer(address,uint256)", OTHER, 1));
        require(!sent, "the GBP cannot be moved");
        require(gbpc.balanceOf(LDN) == 58000, "all of it is still there");
        vm.prank(LDN);
        fr.redeem(ID);
        require(_status(ID) == FundingRequest.Status.Redeemed, "redeemed");
    }

    /// The same for the treasury: the CADC it holds cannot be moved away, so `settle` can burn it.
    function test_TheTreasuryCannotSendTheCadAwayBeforeSettling() public {
        _create(ID, 100000);
        _approve(ID);
        vm.prank(TREASURY);
        (bool sent,) = address(cadc).call(abi.encodeWithSignature("transfer(address,uint256)", OTHER, 1));
        require(!sent, "the CAD cannot be moved");
        _settle(ID, RATE);
        require(_status(ID) == FundingRequest.Status.Settled, "settled");
    }

    // ---- constructor ----

    function test_ConstructorRejectsBadSettings() public {
        address[] memory none = new address[](0);
        vm.expectRevert("BadAddress");
        new FundingRequest(address(0), address(gbpc), TREASURY, none, none, CAP, MIN_RATE, MAX_RATE);
        vm.expectRevert("BadAmount");
        new FundingRequest(address(cadc), address(gbpc), TREASURY, none, none, 0, MIN_RATE, MAX_RATE);
        vm.expectRevert("BadRate");
        new FundingRequest(address(cadc), address(gbpc), TREASURY, none, none, CAP, 0, MAX_RATE);
        vm.expectRevert("BadRate");
        new FundingRequest(address(cadc), address(gbpc), TREASURY, none, none, CAP, 9, 8);
    }

    // ---- properties ----

    /// For any amount and rate: gbp = floor(cad x rate / 1e6), and the supplies follow the
    /// four stages of one request (TR-NFR-02): CADC outstanding while Approved, GBPC while Settled.
    function testFuzz_ConversionAndConservation(uint256 amountSeed, uint32 rateSeed) public {
        uint256 amount = (amountSeed % CAP) + 1;
        uint32 rate = MIN_RATE + (rateSeed % (MAX_RATE - MIN_RATE + 1));
        uint256 expected = (amount * rate) / 1_000_000;

        _create(ID, amount);
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == 0, "requested");

        _approve(ID);
        require(cadc.totalSupply() == amount && gbpc.totalSupply() == 0, "approved");

        if (expected == 0) {
            vm.prank(TREASURY);
            vm.expectRevert("BadAmount");
            fr.settle(ID, rate);
            require(cadc.totalSupply() == amount && gbpc.totalSupply() == 0, "still approved");
            return;
        }

        _settle(ID, rate);
        require(fr.getRequest(ID).amountGbp == expected, "formula");
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == expected, "settled");

        vm.prank(LDN);
        fr.redeem(ID);
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == 0, "redeemed");
    }
}
