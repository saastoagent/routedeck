"""Transport-independent contracts plus the sole Medusa HTTP adapter."""

from . import models as _models
from .errors import (
    MedusaClientConfigurationError,
    MedusaClientContractError,
    MedusaClientError,
)
from .http import (
    HttpMedusaStoreClient,
    MedusaStoreEvidenceSink,
    StoreCallEvidence,
    TransportFailureEvidence,
    classify_transport_failure,
)
from .models import *  # noqa: F403
from .protocol import MedusaStoreClient

__all__ = [
    *_models.__all__,
    "HttpMedusaStoreClient",
    "MedusaClientConfigurationError",
    "MedusaClientContractError",
    "MedusaClientError",
    "MedusaStoreClient",
    "MedusaStoreEvidenceSink",
    "StoreCallEvidence",
    "TransportFailureEvidence",
    "classify_transport_failure",
]
