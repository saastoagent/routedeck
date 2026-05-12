from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from routedeck_core import (
    RouteDeckActionSpec,
    RouteDeckEdgeSpec,
    RouteDeckManifest,
    RouteDeckNodeSpec,
    build_runtime_snapshot,
    validate_manifest,
)

app = FastAPI(title="RouteDeck Minimal Example")

MANIFEST = RouteDeckManifest(
    version="minimal_v1",
    nodes=[
        RouteDeckNodeSpec(
            id="intent",
            label="Intent",
            lane="system",
            description="Collect the user's desired task.",
            expected_input="A short task description.",
            allowed_actions=["intent.confirm"],
            recovery_prompt="Describe the task or confirm the current draft.",
        ),
        RouteDeckNodeSpec(
            id="done",
            label="Done",
            lane="terminal",
            description="Terminal state after the task is confirmed.",
        ),
    ],
    edges=[
        RouteDeckEdgeSpec(from_stage="intent", to_stage="done", type="conditional", condition="confirmed", action_id="intent.confirm"),
    ],
    actions=[
        RouteDeckActionSpec(
            id="intent.confirm",
            label="Confirm",
            description="Confirm the current task draft.",
            emphasis="primary",
            allowed_nodes=["intent"],
        )
    ],
)


class ActionRequest(BaseModel):
    current_node: str = "intent"
    selected_action_id: str | None = None


@app.get("/manifest")
def manifest():
    errors = validate_manifest(MANIFEST)
    return {"manifest": MANIFEST.model_dump(mode="json", by_alias=True), "errors": errors}


@app.get("/snapshot")
def snapshot(current_node: str = "intent"):
    return build_runtime_snapshot(
        MANIFEST,
        current_node=current_node,
        valid_actions=[MANIFEST.actions[0].model_dump(mode="json")],
        blocked_actions=[],
        executed_nodes=["intent"] if current_node == "intent" else ["intent", "done"],
    )


@app.post("/action")
def action(body: ActionRequest):
    if body.current_node == "intent" and body.selected_action_id == "intent.confirm":
        return {"next_node": "done", "message": "Confirmed."}
    return {"next_node": body.current_node, "message": "Action is not valid here."}
