from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_PLANNER_URL = os.getenv("PLANNER_SERVICE_URL", "http://127.0.0.1:8004")


class PlannerClient:
    def __init__(self, base_url: str = DEFAULT_PLANNER_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def get_plan(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/plan")
            response.raise_for_status()
            return response.json()
