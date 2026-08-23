"""
Network traffic recorder for Playwright browser sessions.
Captures HTTP requests and responses with headers, payloads, and status codes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page, Request, Response


class NetworkRecorder:
    """Listens to network events on a Playwright page and records all traffic."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self._request_map: Dict[Request, Dict[str, Any]] = {}
        self._response_map: Dict[int, Response] = {}
        self._page: Optional[Page] = None
        self._is_recording: bool = False

    def start(self, page: Page):
        """Attach request and response listeners to the page."""
        self._page = page
        self._is_recording = True
        page.on("request", self._handle_request)
        page.on("response", self._handle_response)

    def stop(self):
        """Detach network listeners and finalize response bodies."""
        if self._page is not None and self._is_recording:
            self._page.remove_listener("request", self._handle_request)
            self._page.remove_listener("response", self._handle_response)
            self._is_recording = False
        self._finalize_response_bodies()

    def _handle_request(self, request: Request):
        """Record outbound HTTP request details."""
        entry: Dict[str, Any] = {
            "method": request.method,
            "url": request.url,
            "headers": dict(request.headers),
            "post_data": request.post_data,
            "resource_type": request.resource_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response_status": None,
            "response_headers": {},
            "response_body": None,
        }
        self._request_map[request] = entry
        self.entries.append(entry)

    def _handle_response(self, response: Response):
        """Record incoming HTTP response status and headers, queuing response for body read."""
        request = response.request
        entry = self._request_map.get(request)
        if not entry:
            return

        entry["response_status"] = response.status
        entry["response_headers"] = dict(response.headers)
        self._response_map[id(entry)] = response

    def _finalize_response_bodies(self):
        """Safely read response text for captured entries after network completion."""
        for entry in self.entries:
            if entry["response_body"] is not None:
                continue

            response = self._response_map.get(id(entry))
            if response is None:
                continue

            try:
                content_type = entry["response_headers"].get("content-type", "")
                if any(t in content_type for t in ["json", "text", "javascript", "xml", "html"]):
                    entry["response_body"] = response.text()
            except Exception:
                entry["response_body"] = None

    def get_entries(self) -> List[Dict[str, Any]]:
        """Return finalized list of network traffic entries."""
        self._finalize_response_bodies()
        return list(self.entries)

    def clear(self):
        """Clear all captured traffic entries."""
        self.entries.clear()
        self._request_map.clear()
        self._response_map.clear()
