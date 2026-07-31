from __future__ import annotations

import json

import pytest

from scripts.export_contracts import (
    _object_descriptors,
    render_runtime_descriptors,
    transport_schema,
)


MAX_SAFE_INTEGER = 9_007_199_254_740_991


def test_runtime_object_descriptors_match_pydantic_schema() -> None:
    schema = transport_schema()
    descriptors = _object_descriptors(schema)

    for name, descriptor in descriptors.items():
        source = schema if name == "RouteDeckTransportContracts" else schema["$defs"][name]
        properties = set(source.get("properties", {}))
        required = set(source.get("required", []))
        assert set(descriptor["required"]) == required
        assert set(descriptor["optional"]) == properties - required
        assert descriptor["additionalProperties"] is (
            source.get("additionalProperties", True) is not False
        )
        assert descriptor["defaults"] == {
            property_name: property_schema["default"]
            for property_name, property_schema in source.get("properties", {}).items()
            if "default" in property_schema
        }

    interaction = descriptors["RouteDeckInteractionState"]
    assert "request_id" in interaction["optional"]
    assert interaction["additionalProperties"] is False


def test_legacy_conversation_schema_preserves_browser_safe_value_domains() -> None:
    definitions = transport_schema()["$defs"]

    for name in (
        "ConversationStreamStartPayload",
        "ConversationUserMessagePayload",
        "ConversationAssistantDeltaPayload",
        "ConversationAssistantResetPayload",
        "ConversationAssistantEndPayload",
        "ConversationStreamEndPayload",
    ):
        assert definitions[name]["properties"]["request_id"]["maxLength"] == 256

    assert (
        definitions["ConversationStreamStartPayload"]["properties"]
        ["session_version"]["maximum"]
        == MAX_SAFE_INTEGER
    )
    assistant_end = definitions["ConversationAssistantEndPayload"]["properties"]
    assert assistant_end["session_version"]["maximum"] == MAX_SAFE_INTEGER
    assert assistant_end["projection_version"]["maximum"] == MAX_SAFE_INTEGER

    history = definitions["PublicConversationTurn"]["properties"]
    assert history["turn_id"]["minLength"] == 1
    request_id_string = next(
        item for item in history["request_id"]["anyOf"] if item.get("type") == "string"
    )
    assert "minLength" not in request_id_string


def test_runtime_descriptor_render_is_deterministic_and_valid_typescript_data() -> None:
    schema = transport_schema()

    first = render_runtime_descriptors(schema)
    second = render_runtime_descriptors(json.loads(json.dumps(schema)))

    assert first == second
    assert "generatedObjectDescriptors" in first
    assert "PublicProjectionResponse" in first
    assert "PublicOperationResult" in first


def test_runtime_descriptor_generation_fails_loudly_for_nested_all_of() -> None:
    with pytest.raises(
        ValueError,
        match=r"does not support allOf at \$\.\$defs\.Composed\.properties\.value",
    ):
        _object_descriptors(
            {
                "type": "object",
                "properties": {},
                "$defs": {
                    "Composed": {
                        "type": "object",
                        "properties": {
                            "value": {
                                "allOf": [
                                    {"type": "string"},
                                ]
                            }
                        },
                    }
                },
            }
        )
