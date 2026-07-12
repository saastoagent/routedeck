from __future__ import annotations


class MedusaClientError(RuntimeError):
    """Base class for local client-configuration and contract misuse."""


class MedusaClientConfigurationError(MedusaClientError):
    """The adapter was constructed without a required invariant."""


class MedusaClientContractError(MedusaClientError):
    """A caller supplied a value that violates the typed client contract."""


__all__ = [
    "MedusaClientConfigurationError",
    "MedusaClientContractError",
    "MedusaClientError",
]
