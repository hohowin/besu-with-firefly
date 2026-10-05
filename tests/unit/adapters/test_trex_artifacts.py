"""The plan against the real, pinned T-REX and OnchainID artifacts (`npm ci` in contracts/)."""

import pytest

from src.adapters.trex_artifacts import ArtifactsMissingError, load_artifact
from src.core.trex.limits import size_problems
from src.core.trex.plan import Call, Deploy, build_plan

try:
    load_artifact(next(s for s in build_plan() if isinstance(s, Deploy)).artifact)
except ArtifactsMissingError:
    pytest.skip("run `npm ci` in contracts/ first", allow_module_level=True)

DEPLOYS = [s for s in build_plan() if isinstance(s, Deploy)]
CALLS = [s for s in build_plan() if isinstance(s, Call)]


@pytest.mark.parametrize("step", DEPLOYS, ids=lambda s: s.name)
def test_every_contract_has_bytecode_and_a_constructor_that_matches_the_plan(step: Deploy) -> None:
    artifact = load_artifact(step.artifact)
    assert artifact.bytecode.startswith("0x") and len(artifact.bytecode) > 10
    constructors = [e for e in artifact.abi if e["type"] == "constructor"]
    expected = len(constructors[0]["inputs"]) if constructors else 0
    assert len(step.args) == expected, f"{step.name}: plan has {len(step.args)} constructor args"


@pytest.mark.parametrize("step", DEPLOYS, ids=lambda s: s.name)
def test_every_contract_fits_the_ethereum_size_limits(step: Deploy) -> None:
    artifact = load_artifact(step.artifact)
    assert size_problems(step.name, artifact.deployed_size, artifact.init_size) == []


@pytest.mark.parametrize("call", CALLS, ids=lambda c: f"{c.contract}.{c.method}")
def test_every_planned_call_names_a_real_method_with_the_right_number_of_inputs(call: Call) -> None:
    owner = next(s for s in DEPLOYS if s.name == call.contract)
    abi = load_artifact(owner.artifact).abi
    functions = [e for e in abi if e["type"] == "function" and e["name"] == call.method]
    assert functions, f"{call.contract} has no function {call.method}"
    assert len(functions[0]["inputs"]) == len(call.args)


def test_the_closest_contract_to_the_size_limit_is_known_and_still_fits() -> None:
    sizes = {s.name: load_artifact(s.artifact).deployed_size for s in DEPLOYS}
    name = max(sizes, key=lambda n: sizes[n])
    assert name == "trex-factory"
    assert sizes[name] <= 24_576


def test_a_missing_package_gives_a_clear_hint(tmp_path: object) -> None:
    from pathlib import Path

    with pytest.raises(ArtifactsMissingError, match="npm ci"):
        load_artifact(DEPLOYS[0].artifact, modules=Path(str(tmp_path)) / "nothing")


def test_the_artifact_folder_defaults_to_contracts_node_modules() -> None:
    from src.adapters.trex_artifacts import REPO_ROOT, contracts_node_modules

    assert contracts_node_modules({}) == REPO_ROOT / "contracts" / "node_modules"


def test_the_artifact_folder_can_be_moved_with_an_environment_variable() -> None:
    from pathlib import Path

    from src.adapters.trex_artifacts import contracts_node_modules

    env = {"CONTRACTS_NODE_MODULES": "/opt/contracts/node_modules"}
    assert contracts_node_modules(env) == Path("/opt/contracts/node_modules")


def test_a_blank_artifact_folder_variable_is_refused() -> None:
    import pytest

    from src.adapters.trex_artifacts import contracts_node_modules

    with pytest.raises(ValueError, match="CONTRACTS_NODE_MODULES"):
        contracts_node_modules({"CONTRACTS_NODE_MODULES": "  "})
