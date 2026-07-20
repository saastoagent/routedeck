from __future__ import annotations

import json
from pathlib import Path

from jsonschema.validators import validator_for

from medusa_agent.composition import compile_medusa_app


VECTOR_PATH = (
    Path(__file__).resolve().parents[3] / "contracts" / "surface-props-parity.json"
)
EXPECTED_SURFACES = {
    "catalog.product_grid",
    "catalog.product_detail",
    "cart.summary",
    "checkout.contact_form",
    "checkout.shipping_options",
    "checkout.payment_method",
    "checkout.order_review",
    "orders.confirmation",
}


def test_canonical_surface_schemas_match_shared_parity_vectors() -> None:
    vectors = json.loads(VECTOR_PATH.read_text(encoding="utf-8"))["vectors"]
    app = compile_medusa_app()

    assert {vector["surface_id"] for vector in vectors} == EXPECTED_SURFACES
    for surface_id in EXPECTED_SURFACES:
        surface_vectors = [
            vector for vector in vectors if vector["surface_id"] == surface_id
        ]
        assert {vector["valid"] for vector in surface_vectors} == {False, True}

    for vector in vectors:
        surface = app.surfaces[vector["surface_id"]]
        schema = surface.public_props_schema_value()
        validator_type = validator_for(schema)
        validator_type.check_schema(schema)
        actual = validator_type(schema).is_valid(vector["payload"])
        assert actual is vector["valid"], (
            f"{vector['case_id']} ({vector['surface_id']}) expected "
            f"valid={vector['valid']}, got {actual}"
        )
