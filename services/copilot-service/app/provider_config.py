from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

_ALLOWED_PROVIDERS = {"disabled", "local", "external"}


@dataclass(frozen=True)
class ProviderConfig:
    requested_provider: str
    effective_provider: str
    provider_mode: str
    warnings: list[str] = field(default_factory=list)
    used_external_provider: bool = False


def parse_provider_config(env: Mapping[str, str] | None = None) -> ProviderConfig:
    source = env if env is not None else os.environ
    raw_provider = source.get("COPILOT_PROVIDER")

    if raw_provider is None:
        return ProviderConfig(
            requested_provider="missing",
            effective_provider="disabled",
            provider_mode="disabled",
            warnings=["copilot_provider_missing"],
        )

    normalized = raw_provider.strip().lower()
    if not normalized:
        return ProviderConfig(
            requested_provider="empty",
            effective_provider="disabled",
            provider_mode="disabled",
            warnings=["copilot_provider_empty"],
        )

    if normalized in _ALLOWED_PROVIDERS:
        effective = "disabled" if normalized in {"local", "external"} else normalized
        return ProviderConfig(
            requested_provider=normalized,
            effective_provider=effective,
            provider_mode=effective,
            warnings=[],
        )

    return ProviderConfig(
        requested_provider=normalized,
        effective_provider="disabled",
        provider_mode="disabled",
        warnings=["copilot_provider_unknown"],
    )
