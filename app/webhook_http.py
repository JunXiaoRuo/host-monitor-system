"""HTTP helpers for outbound webhook calls."""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


_SENSITIVE_QUERY_KEYS = {"key", "token", "access_token", "secret", "signature"}


def create_webhook_session():
    """Create a session for webhook calls.

    Requests reads proxy settings from the environment by default. That is
    convenient on developer machines, but it breaks notification delivery when
    a stale system proxy is present. Keep this off unless explicitly enabled.
    """
    session = requests.Session()
    session.trust_env = os.environ.get("WEBHOOK_TRUST_ENV", "false").lower() in {"true", "1", "yes"}
    return session


def mask_webhook_url(url):
    """Mask sensitive query values before writing a webhook URL to logs."""
    if not url:
        return url

    try:
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in _SENSITIVE_QUERY_KEYS:
                value = "***"
            query.append((key, value))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, safe="*"), parts.fragment))
    except Exception:
        return url


def sanitize_request_error(error, url):
    """Remove sensitive webhook tokens from exception text."""
    message = str(error)
    if not url:
        return message

    masked_url = mask_webhook_url(url)
    message = message.replace(url, masked_url)

    try:
        parts = urlsplit(url)
        masked_path = urlunsplit(("", "", parts.path, urlsplit(masked_url).query, ""))
        original_path = urlunsplit(("", "", parts.path, parts.query, ""))
        message = message.replace(original_path, masked_path)

        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in _SENSITIVE_QUERY_KEYS and value:
                message = message.replace(value, "***")
    except Exception:
        pass

    return message


_SESSION = create_webhook_session()


def webhook_request(method, url, **kwargs):
    return _SESSION.request(method, url, **kwargs)
