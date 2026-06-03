from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx

from core.config import Settings


@dataclass(frozen=True)
class ConnectionStatus:
    name: str
    url: str
    ok: bool
    status_code: int | None = None
    error: str | None = None


async def probe_medusa_setup(settings: Settings, timeout: float = 2.0) -> dict:
    backend_url = f"{settings.medusa_backend_url.rstrip('/')}/health"
    storefront_url = settings.medusa_storefront_url.rstrip("/")

    async with httpx.AsyncClient(timeout=timeout) as client:
        backend = await _probe(client, "backend", backend_url)
        storefront = await _probe(client, "storefront", storefront_url)

    ready = backend.ok and storefront.ok
    return {
        "setup": {"ready": ready, "mode": "local-demo"},
        "connections": [asdict(backend), asdict(storefront)],
    }


async def _probe(client: httpx.AsyncClient, name: str, url: str) -> ConnectionStatus:
    try:
        response = await client.get(url)
        return ConnectionStatus(
            name=name,
            url=url,
            ok=response.status_code < 500,
            status_code=response.status_code,
        )
    except httpx.HTTPError as exc:
        return ConnectionStatus(name=name, url=url, ok=False, error=type(exc).__name__)
