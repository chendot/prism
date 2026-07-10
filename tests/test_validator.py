import warnings

import pytest

from prism.core.schema import PrismDoc
from prism.core.validator import PrismValidationError, validate_prism_doc, validate_prism_file


def test_validator_accepts_treasury_example() -> None:
    prism = validate_prism_file("examples/treasury.yaml")

    assert len(prism.nodes) == 7


def test_validator_rejects_role_not_in_ontology() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["role"] = "not_a_financial_role"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="Unknown role"):
        validate_prism_doc(invalid)


@pytest.mark.parametrize("weight", ["high", "normal"])
def test_validator_rejects_weight_not_in_ontology(weight: str) -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["weight"] = weight
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="Available weights: muted, primary, secondary"):
        validate_prism_doc(invalid)


def test_validator_rejects_unknown_edge_node() -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["edges"][0]["to"] = "missing_node"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="unknown to node"):
        validate_prism_doc(invalid)


def test_validator_accepts_parallel_lanes_example() -> None:
    prism = validate_prism_file("examples/stablecoin-interest-parallel-lanes.yaml")

    assert prism.render.template == "parallel_lanes"


def test_validator_requires_node_lanes_only_for_parallel_lanes() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0].pop("lane")
    invalid_parallel = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="must define lane"):
        validate_prism_doc(invalid_parallel)

    data["render"]["template"] = "value_flow"
    non_parallel = PrismDoc.model_validate(data)

    validate_prism_doc(non_parallel)


def test_validator_rejects_unknown_parallel_lane() -> None:
    prism = PrismDoc.from_yaml("examples/stablecoin-interest-parallel-lanes.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    data["nodes"][0]["lane"] = "missing_lane"
    invalid = PrismDoc.model_validate(data)

    with pytest.raises(PrismValidationError, match="must match render.lanes id"):
        validate_prism_doc(invalid)


@pytest.mark.parametrize("thesis_count", [2, 3])
def test_validator_warns_only_above_thesis_soft_limit(thesis_count: int) -> None:
    prism = PrismDoc.from_yaml("examples/treasury.yaml")
    data = prism.model_dump(mode="json", by_alias=True)
    for node in data["nodes"][:thesis_count]:
        node["role"] = "thesis"
    candidate = PrismDoc.model_validate(data)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validated = validate_prism_doc(candidate)

    assert validated is candidate
    thesis_warnings = [warning for warning in caught if "thesis nodes" in str(warning.message)]
    assert len(thesis_warnings) == (1 if thesis_count == 3 else 0)
