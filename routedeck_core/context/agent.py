from __future__ import annotations

from dataclasses import dataclass

from ..app.compiled import CompiledApplication
from ..app.feature import Feature
from ..contracts.agent import AgentPolicyRef, AgentPolicy
from ..contracts.application import Node
from ..contracts.operations import Operation
from ..contracts.projection import PublicEntityHandle
from ..contracts.session import RouteDeckSession
from ..contracts.suggestions import SuggestedAction
from ..contracts.surfaces import Surface
from ..projection.policy import (
    resolve_projection_mode,
    visible_entity_handles,
    visible_suggested_actions,
)
from ..validation import RouteDeckValidationError
from .framework_policies import ROUTEDECK_FRAMEWORK_AGENT_POLICIES


@dataclass(frozen=True)
class ResolvedAgentContext:
    """Canonical current scope shared by model adapters and public projection."""

    node: Node
    legal_operations: tuple[Operation, ...]
    active_surface: Surface | None
    visible_entities: tuple[PublicEntityHandle, ...]
    suggested_actions: tuple[SuggestedAction, ...]
    policies: tuple[AgentPolicy, ...]
    policy_provenance: tuple["ResolvedPolicyProvenance", ...]


@dataclass(frozen=True)
class ResolvedPolicyProvenance:
    policy: AgentPolicy
    scope: str
    owner_id: str
    source_order: int


@dataclass(frozen=True)
class AgentContextLens:
    """Resolve only trusted declarations and state legal at the current node."""

    app: CompiledApplication

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
        suggested_actions = visible_suggested_actions(
            node,
            session,
            legal_operation_ids,
        )
        policy_ref_groups = (
            ("feature", feature.namespace, feature.policy_refs),
            ("node", node.id, node.policy_refs),
            *(
                ("capability", capability.id, capability.policy_refs)
                for capability in node.capabilities
            ),
            *(
                (("surface", mode.active_surface.id, mode.active_surface.policy_refs),)
                if mode.active_surface is not None
                else ()
            ),
            *(
                ("operation", operation.id, operation.policy_refs)
                for operation in mode.legal_operations
            ),
        )
        policies, provenance = self._resolve_policies(policy_ref_groups)
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
            policies=policies,
            policy_provenance=provenance,
        )

    def _resolve_policies(
        self,
        ref_groups: tuple[tuple[str, str, tuple[AgentPolicyRef, ...]], ...],
    ) -> tuple[tuple[AgentPolicy, ...], tuple[ResolvedPolicyProvenance, ...]]:
        resolved: list[AgentPolicy] = []
        provenance: list[ResolvedPolicyProvenance] = []
        seen: set[str] = set()

        def add(policy: AgentPolicy, scope: str, owner_id: str) -> None:
            if policy.id in seen:
                return
            seen.add(policy.id)
            resolved.append(policy)
            provenance.append(
                ResolvedPolicyProvenance(
                    policy=policy,
                    scope=scope,
                    owner_id=owner_id,
                    source_order=len(provenance),
                )
            )

        for policy in ROUTEDECK_FRAMEWORK_AGENT_POLICIES:
            add(policy, "framework", "routedeck")
        for scope, owner_id, refs in ref_groups:
            for ref in refs:
                resolved_policy = self.app.agent_policies.get(ref.id)
                if resolved_policy is None:
                    raise RouteDeckValidationError(
                        f"Compiled app references missing agent policy {ref.id!r}"
                    )
                add(resolved_policy, scope, owner_id)
        return tuple(resolved), tuple(provenance)

    def _current_node(self, session: RouteDeckSession) -> Node:
        try:
            return self.app.require_node(session.current.node_id)
        except RouteDeckValidationError as error:
            raise RouteDeckValidationError(
                f"Session references unknown node: {session.current.node_id}"
            ) from error

    def _current_feature(self, node: Node) -> Feature:
        matches = tuple(
            feature
            for feature in self.app.application.features
            if any(candidate.id == node.id for candidate in feature.nodes)
        )
        if len(matches) != 1:
            raise RouteDeckValidationError(
                f"Node {node.id!r} must belong to exactly one compiled feature"
            )
        return matches[0]


__all__ = ["AgentContextLens", "ResolvedAgentContext", "ResolvedPolicyProvenance"]
