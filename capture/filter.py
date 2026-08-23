"""
Noise filter for captured network traffic in Web2Actions.
Strips analytics, tracking pixels, ads, and static assets to isolate genuine API endpoints.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import re

# Known tracking, analytics, and telemetry domains/path patterns
TRACKING_PATTERNS = [
    r"google-analytics\.com",
    r"googletagmanager\.com",
    r"analytics\.google\.com",
    r"segment\.io",
    r"segment\.com",
    r"mixpanel\.com",
    r"hotjar\.com",
    r"sentry\.io",
    r"ingest\.sentry\.io",
    r"facebook\.net",
    r"facebook\.com/tr",
    r"clarity\.ms",
    r"amplitude\.com",
    r"posthog\.com",
    r"datadoghq\.com",
    r"intercom\.io",
    r"crisp\.chat",
    r"driftt\.com",
    r"/telemetry",
    r"/analytics",
    r"/collect",
    r"/beacon",
]

# Static asset file extensions
STATIC_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".css", ".scss", ".less",
    ".map", ".mp4", ".webm", ".mp3", ".wav", ".ogg",
}

# Non-API resource types reported by browser
STATIC_RESOURCE_TYPES = {"image", "font", "stylesheet", "media", "manifest"}


def is_static_asset(url: str, resource_type: str = "") -> bool:
    """Return True if the request is for a static asset (image, font, stylesheet)."""
    if resource_type.lower() in STATIC_RESOURCE_TYPES:
        return True

    parsed_path = urlparse(url).path.lower()
    return any(parsed_path.endswith(ext) for ext in STATIC_EXTENSIONS)


def is_analytics_or_tracking(url: str) -> bool:
    """Return True if the URL matches known analytics, telemetry, or ad networks."""
    lower_url = url.lower()
    return any(re.search(pattern, lower_url) is not None for pattern in TRACKING_PATTERNS)


def is_api_candidate(entry: Dict[str, Any], target_domain: Optional[str] = None) -> bool:
    """
    Evaluate if a captured network entry represents a meaningful API endpoint.
    Filters out static assets and tracking requests.
    """
    url = entry.get("url", "")
    resource_type = entry.get("resource_type", "")

    if not url:
        return False

    # Filter out static files and tracking calls
    if is_static_asset(url, resource_type):
        return False
    if is_analytics_or_tracking(url):
        return False

    # Optional domain filter
    if target_domain:
        entry_domain = urlparse(url).netloc.lower()
        target = target_domain.lower()
        if entry_domain != target and not entry_domain.endswith("." + target):
            return False

    # Check for API indicators (methods other than GET, or json/xhr/fetch indicators)
    method = entry.get("method", "GET").upper()
    if method in {"POST", "PUT", "DELETE", "PATCH"}:
        return True

    content_type = entry.get("response_headers", {}).get("content-type", "").lower()
    if any(t in content_type for t in ["application/json", "application/xml", "text/xml"]):
        return True

    if resource_type in {"xhr", "fetch"}:
        return True

    # Keep URL if path explicitly indicates an API endpoint
    path = urlparse(url).path.lower()
    if any(token in path for token in ["/api/", "/v1/", "/v2/", "/v3/", "/graphql", "/rest/"]):
        return True

    return False


def filter_traffic(
    entries: List[Dict[str, Any]],
    target_domain: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter a list of captured network entries, keeping only real API candidates."""
    return [entry for entry in entries if is_api_candidate(entry, target_domain)]
