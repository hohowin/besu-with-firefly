import pytest

from src.core.paladin.bootstrap import (
    ADDRESS_NAMES,
    FACTORY_INITIALIZE_SELECTOR,
    ConfigConflict,
    deploy_params,
    final_config,
    initialize_call_data,
)

BASE = "nodeName: node1\nlog:\n  level: info\n"
REGISTRY = "0x" + "aa" * 20
PROXY = "0x" + "bb" * 20
NOTO = "0x" + "cc" * 20
FACTORY = "0x" + "dd" * 20


def test_the_four_contracts_are_recorded_under_paladin_prefixed_names() -> None:
    assert ADDRESS_NAMES == {
        "registry": "paladin-registry",
        "noto": "paladin-noto",
        "noto_factory": "paladin-noto-factory",
        "noto_factory_proxy": "paladin-noto-factory-proxy",
    }


def test_the_proxy_is_initialised_with_the_noto_implementation() -> None:
    # initialize(address): the 4 byte selector, then the address left-padded to 32 bytes.
    assert FACTORY_INITIALIZE_SELECTOR == "0xc4d66de8"
    assert initialize_call_data(NOTO) == "0xc4d66de8" + "00" * 12 + "cc" * 20


def test_an_address_in_upper_case_or_without_0x_gives_the_same_call_data() -> None:
    assert initialize_call_data("CC" * 20) == initialize_call_data(NOTO)


def test_a_malformed_address_is_rejected() -> None:
    with pytest.raises(ValueError, match="20 bytes"):
        initialize_call_data("0x1234")


def test_constructor_data_for_each_contract() -> None:
    assert deploy_params("registry", {}) == [False]
    assert deploy_params("noto", {}) == {}
    assert deploy_params("noto_factory", {}) == {}
    addresses = {"noto": NOTO, "noto_factory": FACTORY}
    assert deploy_params("noto_factory_proxy", addresses) == [
        FACTORY,
        initialize_call_data(NOTO),
    ]


def test_the_proxy_cannot_be_deployed_before_the_contracts_it_points_at() -> None:
    with pytest.raises(KeyError, match="noto_factory"):
        deploy_params("noto_factory_proxy", {"noto": NOTO})


def test_an_unknown_contract_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        deploy_params("pente_factory", {})


def test_the_final_config_adds_the_noto_domain_and_the_evm_registry() -> None:
    text = final_config(BASE, registry=REGISTRY, factory_proxy=PROXY)
    assert text.startswith(BASE)
    assert "domains:\n  noto:\n" in text
    assert f"registryAddress: {PROXY}\n" in text
    assert "library: /app/domains/libnoto.so" in text
    assert "factoryVersion: 2" in text
    assert "registries:\n  evm-registry:\n" in text
    assert f"contractAddress: {REGISTRY}\n" in text
    assert "library: /app/registries/libevm.so" in text


def test_the_final_config_does_not_change_the_base_text() -> None:
    text = final_config(BASE, registry=REGISTRY, factory_proxy=PROXY)
    assert text.splitlines()[: len(BASE.splitlines())] == BASE.splitlines()


def test_building_it_again_from_the_same_base_gives_the_same_text() -> None:
    first = final_config(BASE, registry=REGISTRY, factory_proxy=PROXY)
    assert final_config(BASE, registry=REGISTRY, factory_proxy=PROXY) == first


def test_a_base_that_already_has_a_domain_is_a_conflict() -> None:
    already = final_config(BASE, registry=REGISTRY, factory_proxy=PROXY)
    with pytest.raises(ConfigConflict, match="already has a domains"):
        final_config(already, registry=REGISTRY, factory_proxy=PROXY)
