// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.28;

import { Vm, VM_ADDRESS } from "./Vm.sol";
import { CurrencyToken } from "../contracts/CurrencyToken.sol";
import { FundingRequest } from "../contracts/FundingRequest.sol";

/// A token whose mint always fails. burn does nothing. Used to make the SECOND token call of a
/// step fail after the first one (or the state change) already happened.
contract MintFails {
    function mint(address, uint256) external pure {
        revert("MintFailed");
    }

    function burn(address, uint256) external {}
}

/// One step is one unit of work: if any part fails, nothing of it stays (design: use-case.md).
contract AtomicityTest {
    Vm constant vm = Vm(VM_ADDRESS);

    address constant LDN = address(0xA1);
    address constant TOR = address(0xA2);
    address constant TREASURY = address(0xA3);

    uint32 constant RATE = 580_000;
    uint32 constant DATE = 20261018;
    bytes32 constant ID = bytes32(uint256(1));

    function _lists() internal pure returns (address[] memory requesters, address[] memory approvers) {
        requesters = new address[](1);
        requesters[0] = LDN;
        approvers = new address[](1);
        approvers[0] = TOR;
    }

    /// settle = burn CADC, then mint GBPC. Make the mint fail: the burn must be undone too.
    function test_SettleUndoesTheBurnWhenTheMintFails() public {
        CurrencyToken cadc = new CurrencyToken("Canadian Dollar Coin", "CADC", address(this));
        MintFails gbpc = new MintFails();
        (address[] memory requesters, address[] memory approvers) = _lists();
        FundingRequest fr = new FundingRequest(
            address(cadc), address(gbpc), TREASURY, requesters, approvers, 100_000_000, 10_000, 5_000_000
        );
        cadc.setController(address(fr));

        vm.prank(LDN);
        fr.createRequest(ID, 100000, DATE);
        vm.prank(TOR);
        fr.approve(ID);
        require(cadc.totalSupply() == 100000 && cadc.balanceOf(TREASURY) == 100000, "approved");

        vm.prank(TREASURY);
        vm.expectRevert("MintFailed");
        fr.settle(ID, RATE);

        // nothing of the failed step stayed: no burn, no new state, no rate, no GBP amount
        FundingRequest.Request memory r = fr.getRequest(ID);
        require(r.status == FundingRequest.Status.Approved, "state is still Approved");
        require(r.amountGbp == 0 && r.ratePpm == 0, "no amount or rate was recorded");
        require(cadc.totalSupply() == 100000, "the CADC supply is untouched");
        require(cadc.balanceOf(TREASURY) == 100000, "the treasury still holds the CADC");
    }

    /// approve = change state, then mint CADC. Make the mint fail: the state change must be undone.
    function test_ApproveUndoesTheStateWhenTheMintFails() public {
        MintFails cadc = new MintFails();
        CurrencyToken gbpc = new CurrencyToken("Pound Sterling Coin", "GBPC", address(this));
        (address[] memory requesters, address[] memory approvers) = _lists();
        FundingRequest fr = new FundingRequest(
            address(cadc), address(gbpc), TREASURY, requesters, approvers, 100_000_000, 10_000, 5_000_000
        );

        vm.prank(LDN);
        fr.createRequest(ID, 100000, DATE);
        vm.prank(TOR);
        vm.expectRevert("MintFailed");
        fr.approve(ID);

        FundingRequest.Request memory r = fr.getRequest(ID);
        require(r.status == FundingRequest.Status.Requested, "state is still Requested");
        require(r.approver == address(0), "no approver was recorded");
    }

    /// After a failed step the SAME step can be tried again and then works (retry is safe).
    function test_ARetryAfterAFailedSettleWorks() public {
        CurrencyToken cadc = new CurrencyToken("Canadian Dollar Coin", "CADC", address(this));
        CurrencyToken gbpc = new CurrencyToken("Pound Sterling Coin", "GBPC", address(this));
        (address[] memory requesters, address[] memory approvers) = _lists();
        FundingRequest fr = new FundingRequest(
            address(cadc), address(gbpc), TREASURY, requesters, approvers, 100_000_000, 10_000, 5_000_000
        );
        cadc.setController(address(fr));
        gbpc.setController(address(fr));

        vm.prank(LDN);
        fr.createRequest(ID, 100000, DATE);
        vm.prank(TOR);
        fr.approve(ID);

        vm.prank(TREASURY);
        vm.expectRevert("BadRate"); // a bad first attempt (rate out of bounds) changes nothing
        fr.settle(ID, 5_000_001);
        require(cadc.totalSupply() == 100000 && gbpc.totalSupply() == 0, "unchanged after failure");

        vm.prank(TREASURY);
        fr.settle(ID, RATE); // the retry
        require(cadc.totalSupply() == 0 && gbpc.totalSupply() == 58000, "settled once, exactly");
    }
}
