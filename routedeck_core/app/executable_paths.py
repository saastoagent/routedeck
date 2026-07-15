from __future__ import annotations

from ..contracts.application import NodeSpec
from ..contracts.navigation import TransitionSpec
from ..contracts.operations import ReviewPolicy
from ..validation import RouteDeckValidationError
from .compiled import ExecutableTestPath


def _derive_executable_test_paths(
    *,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
) -> tuple[ExecutableTestPath, ...]:
    paths: list[ExecutableTestPath] = []
    for transition in transitions:
        paths.append(
            ExecutableTestPath(
                node_id=transition.source.id,
                source_node_id=transition.source.id,
                target_node_id=transition.target.id,
                operation_id=transition.operation.id,
                outcome=transition.outcome,
                branch="transition",
            )
        )
    for node in nodes:
        paths.append(
            ExecutableTestPath(
                node_id=node.id,
                deep_link_policy=node.route.deep_link_policy,
                branch="deep_link",
            )
        )
        for operation in node.operations:
            paths.append(
                ExecutableTestPath(
                    node_id=node.id,
                    operation_id=operation.id,
                    safety_class=operation.safety_class,
                    branch="safety",
                )
            )
            if operation.review_policy is ReviewPolicy.REQUIRED:
                paths.extend(
                    (
                        ExecutableTestPath(
                            node_id=node.id,
                            operation_id=operation.id,
                            branch="review_approved",
                        ),
                        ExecutableTestPath(
                            node_id=node.id,
                            operation_id=operation.id,
                            branch="review_rejected",
                        ),
                    )
                )
        for directive in node.recovery.directives:
            paths.append(
                ExecutableTestPath(
                    node_id=node.id,
                    branch="recovery",
                    recovery_directive=directive,
                )
            )
    return tuple(paths)


def _validate_executable_test_paths(
    *,
    nodes: tuple[NodeSpec, ...],
    transitions: tuple[TransitionSpec, ...],
    paths: tuple[ExecutableTestPath, ...],
) -> None:
    covered_transitions = {
        (
            path.source_node_id,
            path.operation_id,
            path.outcome,
            path.target_node_id,
        )
        for path in paths
        if path.branch == "transition"
    }
    required_transitions = {
        (
            transition.source.id,
            transition.operation.id,
            transition.outcome,
            transition.target.id,
        )
        for transition in transitions
    }
    covered_deep_links = {
        (path.node_id, path.deep_link_policy)
        for path in paths
        if path.branch == "deep_link"
    }
    required_deep_links = {(node.id, node.route.deep_link_policy) for node in nodes}
    covered_safety = {
        (path.node_id, path.operation_id, path.safety_class)
        for path in paths
        if path.branch == "safety"
    }
    required_safety = {
        (node.id, operation.id, operation.safety_class)
        for node in nodes
        for operation in node.operations
    }
    covered_review = {
        (path.node_id, path.operation_id, path.branch)
        for path in paths
        if path.branch in {"review_approved", "review_rejected"}
    }
    required_review = {
        (node.id, operation.id, branch)
        for node in nodes
        for operation in node.operations
        if operation.review_policy is ReviewPolicy.REQUIRED
        for branch in ("review_approved", "review_rejected")
    }
    covered_recovery = {
        (path.node_id, path.recovery_directive)
        for path in paths
        if path.branch == "recovery"
    }
    required_recovery = {
        (node.id, directive) for node in nodes for directive in node.recovery.directives
    }
    if not (
        covered_transitions >= required_transitions
        and covered_deep_links >= required_deep_links
        and covered_safety >= required_safety
        and covered_review >= required_review
        and covered_recovery >= required_recovery
    ):
        raise RouteDeckValidationError(
            "Executable test paths do not cover every declared branch"
        )
