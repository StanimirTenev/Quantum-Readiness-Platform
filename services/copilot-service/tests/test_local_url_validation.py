from app.local_url_validation import validate_local_url


def test_validate_local_url_accepts_localhost() -> None:
    result = validate_local_url("http://localhost:11434")
    assert result.is_allowed is True
    assert result.reason == "allowed"


def test_validate_local_url_accepts_loopback_ipv4() -> None:
    result = validate_local_url("http://127.0.0.1:11434")
    assert result.is_allowed is True


def test_validate_local_url_accepts_private_192_range() -> None:
    result = validate_local_url("http://192.168.1.10:11434")
    assert result.is_allowed is True


def test_validate_local_url_accepts_private_10_range() -> None:
    result = validate_local_url("http://10.0.0.5:11434")
    assert result.is_allowed is True


def test_validate_local_url_accepts_private_172_range() -> None:
    result = validate_local_url("http://172.16.0.5:11434")
    assert result.is_allowed is True


def test_validate_local_url_accepts_ipv6_loopback() -> None:
    result = validate_local_url("http://[::1]:11434")
    assert result.is_allowed is True


def test_validate_local_url_rejects_public_ipv4() -> None:
    result = validate_local_url("http://8.8.8.8:11434")
    assert result.is_allowed is False
    assert result.reason == "host_not_local"


def test_validate_local_url_rejects_public_dns_openai() -> None:
    result = validate_local_url("https://api.openai.com")
    assert result.is_allowed is False


def test_validate_local_url_rejects_public_dns_example() -> None:
    result = validate_local_url("https://example.com")
    assert result.is_allowed is False


def test_validate_local_url_rejects_malformed_string() -> None:
    result = validate_local_url("http://[::1")
    assert result.is_allowed is False


def test_validate_local_url_rejects_without_scheme() -> None:
    result = validate_local_url("localhost:11434")
    assert result.is_allowed is False
    assert result.reason == "scheme_missing"


def test_validate_local_url_rejects_unsupported_scheme() -> None:
    result = validate_local_url("ftp://localhost")
    assert result.is_allowed is False
    assert result.reason == "scheme_unsupported"


def test_validate_local_url_rejects_credentials() -> None:
    result = validate_local_url("http://user:pass@localhost:11434")
    assert result.is_allowed is False
    assert result.reason == "credentials_not_allowed"
