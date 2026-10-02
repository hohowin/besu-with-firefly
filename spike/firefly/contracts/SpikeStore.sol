// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract SpikeStore {
    uint256 private value;
    event ValueSet(address indexed setter, uint256 value);

    function set(uint256 v) external {
        value = v;
        emit ValueSet(msg.sender, v);
    }

    function get() external view returns (uint256) {
        return value;
    }
}
