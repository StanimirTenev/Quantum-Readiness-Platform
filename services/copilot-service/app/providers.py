from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from typing import Any

from .local_url_validation import validate_local_url
from .provider_config import ProviderConfig, parse_provider_config

DISABLED_ANSWER = (
    "Copilot provider is disabled. The deterministic QRP core remains available. "
    "Configure a local provider for offline analysis."
)


class CopilotProvider(ABC):
    @abstractmethod
    def query(self, request_id: str | None) -> dict[str, Any]:
        """Return a copilot response for the requested mode."""


class DisabledCopilotProvider(CopilotProvider):
    def query(self, request_id: str | None) -> dict[str, Any]:
        return _build_disabled_response(parse_provider_config(), request_id)


class CopilotProviderRuntime:
    def __init__(self, disabled_provider: CopilotProvider | None = None) -> None:
        self._disabled_provider = disabled_provider or DisabledCopilotProvider()

    def query(self, request_id: str | None) -> dict[str, Any]:
        return self._disabled_provider.query(request_id)


def _build_disabled_response(provider_config: ProviderConfig, request_id: str | None) -> dict[str, Any]:
    warnings = ["copilot_provider_disabled", *provider_config.warnings]
    metadata: dict[str, Any] = {
        "provider_name": "disabled",
        "requested_provider": provider_config.requested_provider,
        "effective_provider": provider_config.effective_provider,
    }

    if provider_config.warnings:
        metadata["provider_config_reason"] = provider_config.warnings[0]

    if provider_config.requested_provider == "external":
        warnings.append("copilot_external_provider_not_implemented")

    if provider_config.requested_provider == "local":
        local_validation = validate_local_url(os.environ.get("COPILOT_LOCAL_URL"))
        metadata["local_url_validation_reason"] = local_validation.reason
        if local_validation.is_allowed:
            warnings.append("copilot_local_provider_not_implemented")
        else:
            warnings.append("copilot_local_url_rejected")

    resolved_request_id = request_id or f"copilot-disabled-{uuid.uuid4().hex[:12]}"
    metadata["request_id"] = resolved_request_id

    return {
        "answer": DISABLED_ANSWER,
        "provider_mode": "disabled",
        "citations": [],
        "warnings": list(dict.fromkeys(warnings)),
        "used_external_provider": False,
        "redaction_applied": False,
        "metadata": metadata,
    }
