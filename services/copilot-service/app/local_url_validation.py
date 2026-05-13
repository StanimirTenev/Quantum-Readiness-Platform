from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from urllib.parse import SplitResult, urlsplit


@dataclass(frozen=True)
class LocalUrlValidationResult:
    is_allowed: bool
    reason: str
    normalized_url: str | None


def validate_local_url(raw_url: str | None) -> LocalUrlValidationResult:
    if raw_url is None:
        return LocalUrlValidationResult(False, "url_missing", None)

    candidate = raw_url.strip()
    if not candidate:
        return LocalUrlValidationResult(False, "url_empty", None)

    if "://" not in candidate:
        return LocalUrlValidationResult(False, "scheme_missing", None)

    try:
        parsed = urlsplit(candidate)
    except Exception:
        return LocalUrlValidationResult(False, "url_parse_error", None)

    if not parsed.scheme:
        return LocalUrlValidationResult(False, "scheme_missing", None)

    if parsed.scheme not in {"http", "https"}:
        return LocalUrlValidationResult(False, "scheme_unsupported", None)

    if parsed.username is not None or parsed.password is not None:
        return LocalUrlValidationResult(False, "credentials_not_allowed", None)

    if not parsed.hostname:
        return LocalUrlValidationResult(False, "host_missing", None)

    if not _is_allowed_local_host(parsed.hostname):
        return LocalUrlValidationResult(False, "host_not_local", None)

    return LocalUrlValidationResult(True, "allowed", _normalize_url(parsed))


def _is_allowed_local_host(hostname: str) -> bool:
    host = hostname.strip().lower()
    if host == "localhost":
        return True

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False

    if isinstance(addr, ipaddress.IPv6Address):
        return addr == ipaddress.IPv6Address("::1")

    return (
        addr in ipaddress.ip_network("10.0.0.0/8")
        or addr in ipaddress.ip_network("172.16.0.0/12")
        or addr in ipaddress.ip_network("192.168.0.0/16")
        or addr == ipaddress.IPv4Address("127.0.0.1")
    )


def _normalize_url(parsed: SplitResult) -> str:
    return parsed.geturl()
