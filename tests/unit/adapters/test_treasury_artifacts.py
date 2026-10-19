"""The plan against the real committed artifacts in contracts/treasury/compiled/."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.adapters.treasury_artifacts import COMPILED, ChecksumError, load_treasury_artifact
from src.adapters.trex_artifacts import ArtifactsMissingError
from src.core.treasury.plan import REQUEST_ARTIFACT, TOKEN_ARTIFACT, build_plan
from src.core.trex.limits import size_problems
from src.core.trex.plan import Artifact, Call, Deploy

DEPLOYS = [s for s in build_plan() if isinstance(s, Deploy)]
CALLS = [s for s in build_plan() if isinstance(s, Call)]


@pytest.mark.parametrize("step", DEPLOYS, ids=lambda s: s.name)
def test_constructor_matches_the_plan(step: Deploy) -> None:
    artifact = load_treasury_artifact(step.artifact)
    assert artifact.bytecode.startswith("0x") and len(artifact.bytecode) > 10
    constructor = next(e for e in artifact.abi if e["type"] == "constructor")
    assert len(step.args) == len(constructor["inputs"])


@pytest.mark.parametrize("step", DEPLOYS, ids=lambda s: s.name)
def test_every_contract_fits_the_size_limits(step: Deploy) -> None:
    artifact = load_treasury_artifact(step.artifact)
    assert size_problems(step.name, artifact.deployed_size, artifact.init_size) == []


@pytest.mark.parametrize("call", CALLS, ids=lambda c: f"{c.contract}.{c.method}")
def test_planned_calls_name_real_methods(call: Call) -> None:
    owner = next(s for s in DEPLOYS if s.name == call.contract)
    abi = load_treasury_artifact(owner.artifact).abi
    functions = [e for e in abi if e["type"] == "function" and e["name"] == call.method]
    assert functions
    assert len(functions[0]["inputs"]) == len(call.args)


def test_every_input_has_a_name() -> None:
    """FireFly takes inputs by name, so every input of every function needs one."""
    for artifact in (TOKEN_ARTIFACT, REQUEST_ARTIFACT):
        for entry in load_treasury_artifact(artifact).abi:
            if entry["type"] in ("function", "constructor"):
                assert all(item["name"] for item in entry["inputs"]), entry


def test_the_request_contract_has_the_functions_the_design_names() -> None:
    abi = load_treasury_artifact(REQUEST_ARTIFACT).abi
    names = {e["name"] for e in abi if e["type"] == "function"}
    wanted = {"createRequest", "approve", "reject", "settle", "redeem", "getRequest"}
    assert wanted | {"requestCount", "requestIdAt", "treasury"} <= names


def _copy(tmp_path: Path) -> Path:
    folder = tmp_path / "compiled"
    shutil.copytree(COMPILED, folder)
    return folder


def test_a_changed_artifact_is_refused(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    path = folder / "FundingRequest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["bytecode"] = data["bytecode"][:-2] + "00"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ChecksumError, match="does not match"):
        load_treasury_artifact(REQUEST_ARTIFACT, folder)


def test_a_file_missing_from_the_checksum_list_is_refused(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / "SHA256SUMS").write_text("", encoding="utf-8")
    with pytest.raises(ChecksumError, match="not listed"):
        load_treasury_artifact(TOKEN_ARTIFACT, folder)


def test_a_missing_checksum_file_is_refused(tmp_path: Path) -> None:
    folder = _copy(tmp_path)
    (folder / "SHA256SUMS").unlink()
    with pytest.raises(ChecksumError, match="not found"):
        load_treasury_artifact(TOKEN_ARTIFACT, folder)


def test_a_missing_artifact_says_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(ArtifactsMissingError, match="npm run build"):
        load_treasury_artifact(TOKEN_ARTIFACT, tmp_path)


def test_another_package_is_refused() -> None:
    with pytest.raises(ValueError, match="not a treasury artifact"):
        load_treasury_artifact(Artifact("t-rex", "x"))


def test_the_committed_checksums_match_the_files() -> None:
    for line in (COMPILED / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition(" *")
        assert hashlib.sha256((COMPILED / name).read_bytes()).hexdigest() == digest
