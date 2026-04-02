from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_INVENTORY_URL = os.getenv("INVENTORY_SERVICE_URL", "http://127.0.0.1:8001")


class InventoryClient:
    def __init__(self, base_url: str = DEFAULT_INVENTORY_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def get_assets(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/assets")
            response.raise_for_status()
            return response.json()

    def get_scans(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/scans")
            response.raise_for_status()
            return response.json()

    def get_risks(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/risks")
            response.raise_for_status()
            return response.json()

    def get_scan(self, scan_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/scans/{scan_id}")
            response.raise_for_status()
            return response.json()
