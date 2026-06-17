from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.chat import router as chat_router
from routes.projection import router as projection_router
from routes.route_stream import router as route_stream_router


app = FastAPI(title="Medusa Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5198", "http://127.0.0.1:5198"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(projection_router)
app.include_router(route_stream_router)


@app.get("/api/medusa-agent/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
