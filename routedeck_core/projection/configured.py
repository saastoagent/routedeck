from __future__ import annotations

from dataclasses import dataclass

from ..app import CompiledRouteDeckApp
from ..contracts.projection import PublicProjection
from ..contracts.session import RouteDeckSession
from ..navigation.transactions import PublicKeyValidatorFactory
from ..ports import Clock
from .projector import ProjectionProjector


@dataclass(frozen=True)
class ConfiguredSessionProjector:
    """Project each session with the configured clock and route-key policy."""

    app: CompiledRouteDeckApp
    clock: Clock
    public_key_validator_factory: PublicKeyValidatorFactory

    def project(self, session: RouteDeckSession) -> PublicProjection:
        return ProjectionProjector(
            app=self.app,
            public_key_validator=self.public_key_validator_factory(session),
            now=self.clock.now(),
        ).project(session)


__all__ = ["ConfiguredSessionProjector"]
