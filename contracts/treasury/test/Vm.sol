// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

/// The few cheatcodes the tests use, declared here so the project needs no forge-std dependency.
interface Vm {
    function prank(address sender) external;
    function expectRevert(bytes calldata reason) external;
}

address constant VM_ADDRESS = 0x7109709ECfa91a80626fF3989D68f67F5b1DD12D;
