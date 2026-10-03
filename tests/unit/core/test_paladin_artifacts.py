import json

import pytest

from src.core.paladin.artifacts import PaladinArtifact, parse_artifact_yaml

SAMPLE = """\
apiVersion: core.paladin.io/v1alpha1
kind: SmartContractDeployment
metadata:
  labels:
    app.kubernetes.io/name: operator-go
  name: sample-contract
spec:
  abiJSON: |-
    [
      {
        "inputs": [
          {
            "name": "rootless",
            "type": "bool"
          }
        ],
        "type": "constructor"
      }
    ]
  bytecode: 0x6080604052
  from: sample.operator
  node: node1
  paramsJSON: |-
    [
      false
    ]
  requiredContractDeployments:
  - first
  - second
  txType: public
status: {}
"""


def test_the_name_abi_bytecode_sender_params_and_requirements_are_read() -> None:
    artifact = parse_artifact_yaml(SAMPLE)
    assert isinstance(artifact, PaladinArtifact)
    assert artifact.name == "sample-contract"
    assert artifact.abi == [
        {"inputs": [{"name": "rootless", "type": "bool"}], "type": "constructor"}
    ]
    assert artifact.bytecode == "0x6080604052"
    assert artifact.sender == "sample.operator"
    assert json.loads(artifact.params_json) == [False]
    assert artifact.requires == ("first", "second")


def test_an_artifact_without_requirements_has_none_and_a_plain_params_value() -> None:
    text = SAMPLE.replace("  requiredContractDeployments:\n  - first\n  - second\n", "")
    text = text.replace("  paramsJSON: |-\n    [\n      false\n    ]\n", "  paramsJSON: '{}'\n")
    artifact = parse_artifact_yaml(text)
    assert artifact.requires == ()
    assert artifact.params_json == "{}"


def test_the_init_code_size_is_its_byte_length() -> None:
    assert parse_artifact_yaml(SAMPLE).init_size == 5


@pytest.mark.parametrize("missing", ["abiJSON", "bytecode", "from"])
def test_a_file_without_a_needed_field_is_rejected_by_name(missing: str) -> None:
    text = "\n".join(
        line for line in SAMPLE.splitlines() if not line.strip().startswith(missing)
    )
    with pytest.raises(ValueError, match=missing):
        parse_artifact_yaml(text)


def test_a_file_that_is_not_a_smart_contract_deployment_is_rejected() -> None:
    with pytest.raises(ValueError, match="SmartContractDeployment"):
        parse_artifact_yaml(SAMPLE.replace("kind: SmartContractDeployment", "kind: Other"))
