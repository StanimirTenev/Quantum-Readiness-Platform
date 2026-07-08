from app.models import TLSEvidence


def test_structured_key_size_bits_normalizes_to_public_key_size():
    evidence = TLSEvidence(
        target="example.com:443",
        certificate={
            "subject": {"display_dn": "CN=example.com"},
            "algorithms": {"signature": "SHA256-RSA", "public_key": "RSA"},
            "key": {"type": "RSA", "size_bits": 1024},
        },
    )

    assert evidence.certificate.public_key_algorithm == "RSA"
    assert evidence.certificate.public_key_size == 1024


def test_flat_public_key_size_still_works_without_structured_key_block():
    evidence = TLSEvidence(
        target="example.com:443",
        certificate={"public_key_algorithm": "RSA", "public_key_size": 2048},
    )

    assert evidence.certificate.public_key_size == 2048


def test_collected_is_inferred_true_when_certificate_present_and_unset():
    evidence = TLSEvidence(
        target="example.com:443",
        certificate={"public_key_algorithm": "RSA", "public_key_size": 2048},
    )

    assert evidence.collected is True


def test_collected_explicit_value_is_not_overridden():
    evidence = TLSEvidence(
        target="example.com:443",
        collected=False,
        certificate={"public_key_algorithm": "RSA", "public_key_size": 2048},
    )

    assert evidence.collected is False


def test_collected_stays_unset_without_a_certificate():
    evidence = TLSEvidence(target="example.com:443")

    assert evidence.collected is None
    assert evidence.certificate is None
