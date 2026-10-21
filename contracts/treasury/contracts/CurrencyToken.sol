// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

/// A ledger token for one currency (2 decimals). It has the ERC-20 read functions and events, but
/// it is NOT transferable: there is no transfer, approve or transferFrom. Tokens are only created
/// (mint) and destroyed (burn), and only by the `controller`, which is the FundingRequest contract
/// and is set once by the admin (TD-02). So a holder can neither send tokens away nor block a
/// step by moving them.
/// Reverts use plain strings: FireFly's error text carries only Error("...") reasons.
contract CurrencyToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 2;

    uint256 public totalSupply;
    mapping(address => uint256) private balances;

    address public immutable admin;
    address public controller;

    // The standard ERC-20 event. A mint is a Transfer from the zero address, a burn is a Transfer
    // to the zero address, so wallets and the Explorer show them correctly.
    event Transfer(address indexed from, address indexed to, uint256 value);
    event ControllerSet(address indexed controller);

    constructor(string memory name_, string memory symbol_, address admin_) {
        require(admin_ != address(0), "BadAdmin");
        name = name_;
        symbol = symbol_;
        admin = admin_;
    }

    // Explicit getter, not a public mapping: FireFly passes inputs by name and a mapping getter has none.
    function balanceOf(address account) external view returns (uint256) {
        return balances[account];
    }

    function setController(address controller_) external {
        require(msg.sender == admin, "NotAdmin");
        require(controller == address(0), "ControllerSet");
        require(controller_ != address(0), "BadController");
        controller = controller_;
        emit ControllerSet(controller_);
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == controller, "NotController");
        require(to != address(0), "BadRecipient");
        totalSupply += amount;
        balances[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(address from, uint256 amount) external {
        require(msg.sender == controller, "NotController");
        require(balances[from] >= amount, "InsufficientBalance");
        balances[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }
}
