import base64
import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """
    Verify LINE webhook HMAC-SHA256 signature.
    
    :param body: Raw request body in bytes.
    :param signature: Base64-encoded signature from X-Line-Signature header.
    :param channel_secret: LINE Channel Secret.
    :return: True if signature is valid, False otherwise.
    """
    if not signature or not channel_secret:
        return False

    clean_secret = channel_secret.strip().strip("'\"")
    clean_signature = signature.strip().strip("'\"")

    try:
        hash_digest = hmac.new(
            clean_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
        expected_signature = base64.b64encode(hash_digest).decode("utf-8")
        return hmac.compare_digest(expected_signature, clean_signature)
    except Exception as exc:
        logger.error(f"Error during signature verification: {exc}")
        return False

