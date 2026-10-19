// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

/// A minimal ERC-20 for one currency (2 decimals). Only the `controller` can mint and burn.
/// The controller is the FundingRequest contract and is set once by the admin (TD-02).
/// Reverts use plain strings: FireFly's error text carries only Error("...") reasons.
contract CurrencyToken {
    string public name;
    string public symbol;
    uint8 public constant decimals = 2;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public immutable admin;
    address public controller;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event ControllerSet(address indexed controller);

    constructor(string memory name_, string memory symbol_, address admin_) {
        require(admin_ != address(0), "BadAdmin");
        name = name_;
        symbol = symbol_;
        admin = admin_;
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
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(address from, uint256 amount) external {
        require(msg.sender == controller, "NotController");
        require(balanceOf[from] >= amount, "InsufficientBalance");
        balanceOf[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= amount, "InsufficientAllowance");
        if (allowed != type(uint256).max) {
            allowance[from][msg.sender] = allowed - amount;
        }
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) private {
        require(to != address(0), "BadRecipient");
        require(balanceOf[from] >= amount, "InsufficientBalance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}
