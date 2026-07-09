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
