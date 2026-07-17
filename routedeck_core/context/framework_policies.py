from __future__ import annotations

from enum import StrEnum

from ..contracts.agent import AgentPolicy


class RouteDeckAgentPolicyType(StrEnum):
    EXECUTION_AUTHORITY = "routedeck.execution_authority"
    INTENT_AUTHORITY = "routedeck.intent_authority"
    STATE_AUTHORITY = "routedeck.state_authority"


ROUTEDECK_FRAMEWORK_AGENT_POLICIES = (
    AgentPolicy(
        id=RouteDeckAgentPolicyType.EXECUTION_AUTHORITY,
        instruction=(
            "Call only tools listed as legal in the current RouteDeck context. "
            "Copy opaque interaction handles exactly as supplied. Call tools "
            "serially and wait for each result before choosing another tool."
        ),
    ),
    AgentPolicy(
        id=RouteDeckAgentPolicyType.INTENT_AUTHORITY,
        instruction=(
            "An operation being legal means it is permitted, not requested. "
            "Perform an operation only when the current user turn requires that "
            "application action; prior activity does not authorize repetition."
        ),
    ),
    AgentPolicy(
        id=RouteDeckAgentPolicyType.STATE_AUTHORITY,
        instruction=(
            "Treat completed tool results and the refreshed RouteDeck context as "
            "the only authority for application state. Do not claim a state change "
            "before a completed result confirms it. If review or user input is "
            "required, explain that state and wait."
        ),
    ),
)


__all__ = ["ROUTEDECK_FRAMEWORK_AGENT_POLICIES", "RouteDeckAgentPolicyType"]
