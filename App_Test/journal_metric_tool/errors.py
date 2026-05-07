import requests

from .scholar import ScholarProfileError


def classify_error(error: Exception) -> str:
    if isinstance(error, ScholarProfileError):
        return "scholar_blocked"
    if isinstance(error, requests.Timeout):
        return "timeout"
    if isinstance(error, requests.ConnectionError):
        return "network"
    if isinstance(error, requests.HTTPError):
        status_code = error.response.status_code if error.response is not None else None
        if status_code == 429:
            return "rate_limited"
        if status_code and status_code >= 500:
            return "server_error"
        return "http_error"
    return "unknown_error"
