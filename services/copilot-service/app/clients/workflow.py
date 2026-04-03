from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_WORKFLOW_URL = os.getenv("WORKFLOW_SERVICE_URL", "http://127.0.0.1:8005")


class WorkflowClient:
    def __init__(self, base_url: str = DEFAULT_WORKFLOW_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def get_tasks(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/tasks")
            response.raise_for_status()
            return response.json()

    def get_approvals(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/approvals")
            response.raise_for_status()
            return response.json()
