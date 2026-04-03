from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_RETRIEVAL_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8006")


class RetrievalClient:
    def __init__(self, base_url: str = DEFAULT_RETRIEVAL_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def get_overview(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/overview")
            response.raise_for_status()
            return response.json()

    def get_asset(self, asset_name: str) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/asset", params={"asset_name": asset_name})
            response.raise_for_status()
            return response.json()

    def search(self, query: str) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{self.base_url}/search", json={"query": query})
            response.raise_for_status()
            return response.json()
