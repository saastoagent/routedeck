FROM python:3.11-slim

WORKDIR /app/routedeck

COPY pyproject.toml README.md ./
COPY routedeck_core ./routedeck_core
RUN pip install --no-cache-dir -e . fastapi==0.115.6 uvicorn[standard]==0.34.0 pydantic==2.10.4

COPY examples/minimal-fastapi-react/backend ./examples/minimal-fastapi-react/backend
WORKDIR /app/routedeck/examples/minimal-fastapi-react

EXPOSE 8096
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8096"]
