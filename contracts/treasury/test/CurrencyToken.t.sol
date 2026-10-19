// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

import { Vm, VM_ADDRESS } from "./Vm.sol";
import { CurrencyToken } from "../contracts/CurrencyToken.sol";

contract CurrencyTokenTest {
    Vm constant vm = Vm(VM_ADDRESS);

    address constant CONTROLLER = address(0xC0);
    address constant ALICE = address(0xA1);
    address constant BOB = address(0xB0);

    CurrencyToken token;

    // This contract is the admin: it deploys the token.
    function setUp() public {
        token = new CurrencyToken("Canadian Dollar Coin", "CADC", address(this));
    }

    function test_Metadata() public view {
        require(token.decimals() == 2, "decimals");
        require(keccak256(bytes(token.symbol())) == keccak256("CADC"), "symbol");
        require(token.admin() == address(this), "admin");
    }

    function test_ControllerIsSetOnceByTheAdmin() public {
        token.setController(CONTROLLER);
        require(token.controller() == CONTROLLER, "controller");

        vm.expectRevert("ControllerSet");
        token.setController(ALICE);
    }

    function test_OnlyTheAdminSetsTheController() public {
        vm.prank(ALICE);
        vm.expectRevert("NotAdmin");
        token.setController(ALICE);
    }

    function test_ControllerCannotBeZero() public {
        vm.expectRevert("BadController");
        token.setController(address(0));
    }

    function test_NobodyCanMintOrBurnBeforeTheControllerIsSet() public {
        vm.expectRevert("NotController");
        token.mint(ALICE, 1);

        vm.expectRevert("NotController");
        token.burn(ALICE, 1);
    }

    function test_TheAdminCannotMint() public {
        token.setController(CONTROLLER);
        vm.expectRevert("NotController");
        token.mint(ALICE, 1);
    }

    function test_OnlyTheControllerMintsAndBurns() public {
        token.setController(CONTROLLER);

        vm.prank(CONTROLLER);
        token.mint(ALICE, 500);
        require(token.balanceOf(ALICE) == 500, "balance after mint");
        require(token.totalSupply() == 500, "supply after mint");

        vm.prank(ALICE);
        vm.expectRevert("NotController");
        token.burn(ALICE, 100);

        vm.prank(CONTROLLER);
        token.burn(ALICE, 200);
        require(token.balanceOf(ALICE) == 300, "balance after burn");
        require(token.totalSupply() == 300, "supply after burn");
    }

    function test_BurnMoreThanTheBalanceReverts() public {
        token.setController(CONTROLLER);
        vm.prank(CONTROLLER);
        token.mint(ALICE, 10);

        vm.prank(CONTROLLER);
        vm.expectRevert("InsufficientBalance");
        token.burn(ALICE, 11);
    }

    function test_MintToTheZeroAddressReverts() public {
        token.setController(CONTROLLER);
        vm.prank(CONTROLLER);
        vm.expectRevert("BadRecipient");
        token.mint(address(0), 1);
    }

    function test_TransferAndAllowanceFollowErc20() public {
        token.setController(CONTROLLER);
        vm.prank(CONTROLLER);
        token.mint(ALICE, 100);

        vm.prank(ALICE);
        token.transfer(BOB, 40);
        require(token.balanceOf(ALICE) == 60 && token.balanceOf(BOB) == 40, "transfer");

        vm.prank(ALICE);
        token.approve(BOB, 25);
        vm.prank(BOB);
        token.transferFrom(ALICE, BOB, 25);
        require(token.balanceOf(ALICE) == 35 && token.balanceOf(BOB) == 65, "transferFrom");
        require(token.allowance(ALICE, BOB) == 0, "allowance used");

        vm.prank(BOB);
        vm.expectRevert("InsufficientAllowance");
        token.transferFrom(ALICE, BOB, 1);
        require(token.totalSupply() == 100, "transfers do not change the supply");
    }

    function test_TransferMoreThanTheBalanceReverts() public {
        vm.prank(ALICE);
        vm.expectRevert("InsufficientBalance");
        token.transfer(BOB, 1);
    }
}
