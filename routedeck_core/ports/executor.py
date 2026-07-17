from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from ..contracts.operations import (
    OperationOutcome,
    OperationSource,
    Operation,
)
from ..contracts.projection import FrozenJsonObject


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResolvedEntityInput(_FrozenContract):
    argument_name: str = Field(min_length=1)
    entity_kind: str = Field(min_length=1)
    private_id: SecretStr


class ExecutionContext(_FrozenContract):
    session_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    source: OperationSource
    context_fingerprint: str = Field(min_length=1)
    provider_values: FrozenJsonObject = Field(
        default_factory=lambda: FrozenJsonObject({})
    )
    resolved_entities: tuple[ResolvedEntityInput, ...] = ()

    @model_validator(mode="after")
    def _unique_entity_arguments(self) -> ExecutionContext:
        names = tuple(item.argument_name for item in self.resolved_entities)
        if len(names) != len(set(names)):
            raise ValueError("resolved entity argument names must be unique")
        return self

    def private_entity_id(self, argument_name: str) -> str:
        for entity in self.resolved_entities:
            if entity.argument_name == argument_name:
                return entity.private_id.get_secret_value()
        raise KeyError(argument_name)


class OperationHandler(Protocol):
    async def __call__(
        self,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome: ...


@dataclass(frozen=True)
class OperationBinding:
    operation: Operation
    handler: OperationHandler


@runtime_checkable
class OperationExecutor(Protocol):
    async def execute(
        self,
        binding: OperationBinding,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome: ...


class RegisteredOperationExecutor:
    """Invoke the one handler carried by an already validated binding."""

    async def execute(
        self,
        binding: OperationBinding,
        arguments: Mapping[str, Any],
        context: ExecutionContext,
    ) -> OperationOutcome:
        outcome = await binding.handler(arguments, context)
        if not isinstance(outcome, OperationOutcome):
            raise TypeError("Operation handlers must return OperationOutcome")
        return outcome


__all__ = [
    "ExecutionContext",
    "OperationBinding",
    "OperationExecutor",
    "OperationHandler",
    "RegisteredOperationExecutor",
    "ResolvedEntityInput",
]
