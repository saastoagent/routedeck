"""Transport-independent contracts plus the canonical Medusa HTTP facade."""

from . import models as _models
from .errors import (
    MedusaClientConfigurationError,
    MedusaClientContractError,
    MedusaClientError,
)
from .evidence import MedusaStoreEvidenceSink, StoreCallEvidence
from .http import HttpMedusaStoreClient
from .models import *  # noqa: F403
from .protocol import MedusaStoreClient
from .transport import TransportFailureEvidence, classify_transport_failure

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
