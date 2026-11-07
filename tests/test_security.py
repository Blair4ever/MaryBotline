import base64
import hashlib
import hmac
import pytest
from app.core.security import verify_line_signature


def generate_valid_signature(body: bytes, secret: str) -> str:
    """Helper to compute valid HMAC-SHA256 signature."""
    hash_digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(hash_digest).decode("utf-8")


def test_signature_verification_valid():
    secret = "my_channel_secret"
    body = b'{"events":[{"type":"message"}]}'
    valid_sig = generate_valid_signature(body, secret)

    assert verify_line_signature(body, valid_sig, secret) is True


def test_signature_verification_invalid():
    secret = "my_channel_secret"
    body = b'{"events":[{"type":"message"}]}'
    invalid_sig = "invalid_base64_signature="

    assert verify_line_signature(body, invalid_sig, secret) is False


def test_signature_verification_tampered_body():
    secret = "my_channel_secret"
    original_body = b'{"events":[{"type":"message"}]}'
    tampered_body = b'{"events":[{"type":"message","hacked":true}]}'
    sig = generate_valid_signature(original_body, secret)

    assert verify_line_signature(tampered_body, sig, secret) is False


def test_signature_verification_missing_args():
    assert verify_line_signature(b"", "", "") is False
    assert verify_line_signature(b"data", "", "secret") is False
    assert verify_line_signature(b"data", "sig", "") is False

