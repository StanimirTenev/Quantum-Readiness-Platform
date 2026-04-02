from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_RISK_ENGINE_URL = os.getenv("RISK_ENGINE_URL", "http://127.0.0.1:8002")


class RiskEngineClient:
    def __init__(self, base_url: str = DEFAULT_RISK_ENGINE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def score(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self.base_url}/score", json=payload)
            response.raise_for_status()
            return response.json()
