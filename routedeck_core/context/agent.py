from __future__ import annotations

from dataclasses import dataclass

from ..app.compiled import CompiledRouteDeckApp
from ..app.feature import FeatureSpec
from ..contracts.agent import AgentPolicyRef, AgentPolicySpec
from ..contracts.application import NodeSpec
from ..contracts.operations import OperationSpec
from ..contracts.projection import PublicEntityHandle
from ..contracts.session import RouteDeckSession
from ..contracts.suggestions import SuggestedActionSpec
from ..contracts.surfaces import SurfaceSpec
from ..projection.policy import resolve_projection_mode, visible_entity_handles
from ..validation import RouteDeckValidationError
from .framework_policies import ROUTEDECK_FRAMEWORK_AGENT_POLICIES


@dataclass(frozen=True)
class ResolvedAgentContext:
    """Canonical current scope shared by model adapters and public projection."""

    node: NodeSpec
    legal_operations: tuple[OperationSpec, ...]
    active_surface: SurfaceSpec | None
    visible_entities: tuple[PublicEntityHandle, ...]
    suggested_actions: tuple[SuggestedActionSpec, ...]
    policies: tuple[AgentPolicySpec, ...]


@dataclass(frozen=True)
class AgentContextLens:
    """Resolve only trusted declarations and state legal at the current node."""

    app: CompiledRouteDeckApp

    def resolve(self, session: RouteDeckSession) -> ResolvedAgentContext:
        node = self._current_node(session)
        feature = self._current_feature(node)
        mode = resolve_projection_mode(self.app, node, session)
        legal_operation_ids = frozenset(
            operation.id for operation in mode.legal_operations
        )
        declared_entity_kinds = frozenset(
            provider.entity_kind for provider in node.entity_providers
        )
        suggested_actions = tuple(
            action
            for action in node.suggested_actions
            if action.operation_id in legal_operation_ids
        )
        policy_refs = (
            feature.policy_refs,
            node.policy_refs,
            *(capability.policy_refs for capability in node.capabilities),
            *(
                (mode.active_surface.policy_refs,)
                if mode.active_surface is not None
                else ()
            ),
            *(
                operation.policy_refs
                for operation in mode.legal_operations
            ),
        )
        return ResolvedAgentContext(
            node=node,
            legal_operations=mode.legal_operations,
            active_surface=mode.active_surface,
            visible_entities=visible_entity_handles(
                session,
                legal_operation_ids,
                declared_entity_kinds,
            ),
            suggested_actions=suggested_actions,
            policies=self._resolve_policies(policy_refs),
        )

    def _resolve_policies(
        self,
        ref_groups: tuple[tuple[AgentPolicyRef, ...], ...],
    ) -> tuple[AgentPolicySpec, ...]:
        resolved: list[AgentPolicySpec] = []
        seen: set[str] = set()

        def add(policy: AgentPolicySpec) -> None:
            if policy.id in seen:
                return
            seen.add(policy.id)
            resolved.append(policy)

        for policy in ROUTEDECK_FRAMEWORK_AGENT_POLICIES:
            add(policy)
        for refs in ref_groups:
            for ref in refs:
                policy = self.app.agent_policies.get(ref.id)
                if policy is None:
                    raise RouteDeckValidationError(
                        f"Compiled app references missing agent policy {ref.id!r}"
                    )
                add(policy)
        return tuple(resolved)

    def _current_node(self, session: RouteDeckSession) -> NodeSpec:
        node = next(
            (
                candidate
                for candidate in self.app.spec.nodes
                if candidate.id == session.current.node_id
            ),
            None,
        )
        if node is None:
            raise RouteDeckValidationError(
                f"Session references unknown node: {session.current.node_id}"
            )
        return node

    def _current_feature(self, node: NodeSpec) -> FeatureSpec:
        matches = tuple(
            feature
            for feature in self.app.source_spec.features
            if any(candidate.id == node.id for candidate in feature.nodes)
        )
        if len(matches) != 1:
            raise RouteDeckValidationError(
                f"Node {node.id!r} must belong to exactly one compiled feature"
            )
        return matches[0]


__all__ = ["AgentContextLens", "ResolvedAgentContext"]
