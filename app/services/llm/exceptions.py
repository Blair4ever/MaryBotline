class LLMError(Exception):
    """Base exception for all LLM client errors."""
    pass


class ConfigurationError(LLMError):
    """Raised when LLM configuration is missing or invalid."""
    pass


class AuthenticationError(LLMError):
    """Raised when endpoint authentication fails (401/403)."""
    pass


class EndpointConnectionError(LLMError):
    """Raised when network connection to endpoint fails or times out."""
    pass


class ProviderAPIError(LLMError):
    """Raised when provider returns a server or validation error (4xx/5xx)."""
    pass


class UnsupportedCapabilityError(LLMError):
    """Raised when an operation requires a capability the model/endpoint does not support."""
    pass
