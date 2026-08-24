"""
Unit tests for captured network traffic noise filtering.
"""

import os
import sys
import unittest

CAPTURE_PKG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if CAPTURE_PKG_DIR not in sys.path:
    sys.path.insert(0, CAPTURE_PKG_DIR)

from filter import is_static_asset, is_analytics_or_tracking, is_api_candidate, filter_traffic


class TestNoiseFilter(unittest.TestCase):
    """Test suite verifying removal of noise (analytics, assets) and retention of API calls."""

    def test_static_asset_detection(self):
        """Identifies image, font, CSS, and media asset URLs."""
        self.assertTrue(is_static_asset("https://example.com/logo.png"))
        self.assertTrue(is_static_asset("https://example.com/styles/main.css"))
        self.assertTrue(is_static_asset("https://example.com/fonts/inter.woff2"))
        self.assertTrue(is_static_asset("https://example.com/favicon.ico"))
        self.assertTrue(is_static_asset("https://example.com/dynamic-image", resource_type="image"))
        self.assertFalse(is_static_asset("https://example.com/api/v1/users", resource_type="fetch"))

    def test_analytics_and_tracking_detection(self):
        """Identifies telemetry, tracking scripts, and analytics endpoints."""
        self.assertTrue(is_analytics_or_tracking("https://www.google-analytics.com/g/collect"))
        self.assertTrue(is_analytics_or_tracking("https://api.segment.io/v1/track"))
        self.assertTrue(is_analytics_or_tracking("https://o12345.ingest.sentry.io/api/123/envelope/"))
        self.assertTrue(is_analytics_or_tracking("https://example.com/telemetry/events"))
        self.assertFalse(is_analytics_or_tracking("https://example.com/api/v1/checkout"))

    def test_filter_traffic_pipeline(self):
        """Filter preserves real API requests and removes noise."""
        raw_traffic = [
            # Real API calls
            {
                "method": "POST",
                "url": "https://api.example.com/v1/auth/login",
                "resource_type": "fetch",
                "response_headers": {"content-type": "application/json"},
            },
            {
                "method": "GET",
                "url": "https://api.example.com/v1/customers?page=1",
                "resource_type": "xhr",
                "response_headers": {"content-type": "application/json; charset=utf-8"},
            },
            {
                "method": "DELETE",
                "url": "https://api.example.com/v1/customers/c_456",
                "resource_type": "fetch",
                "response_headers": {"content-type": "application/json"},
            },
            # Cross-domain API call (e.g. Supabase backend) — must be KEPT now
            {
                "method": "POST",
                "url": "https://abc.supabase.co/rest/v1/tasks",
                "resource_type": "fetch",
                "response_headers": {"content-type": "application/json"},
            },
            # Noise to be filtered out
            {
                "method": "GET",
                "url": "https://www.googletagmanager.com/gtm.js?id=GTM-1234",
                "resource_type": "script",
                "response_headers": {"content-type": "application/javascript"},
            },
            {
                "method": "POST",
                "url": "https://api.segment.io/v1/p",
                "resource_type": "fetch",
                "response_headers": {"content-type": "application/json"},
            },
            {
                "method": "GET",
                "url": "https://example.com/static/img/hero.webp",
                "resource_type": "image",
                "response_headers": {"content-type": "image/webp"},
            },
            {
                "method": "GET",
                "url": "https://example.com/assets/app.css",
                "resource_type": "stylesheet",
                "response_headers": {"content-type": "text/css"},
            },
        ]

        filtered = filter_traffic(raw_traffic)
        self.assertEqual(len(filtered), 4)

        urls = [entry["url"] for entry in filtered]
        self.assertIn("https://api.example.com/v1/auth/login", urls)
        self.assertIn("https://api.example.com/v1/customers?page=1", urls)
        self.assertIn("https://api.example.com/v1/customers/c_456", urls)
        # Cross-domain (Supabase) API call is preserved without a domain filter
        self.assertIn("https://abc.supabase.co/rest/v1/tasks", urls)

    def test_filter_keep_domains_is_opt_in(self):
        """Passing keep_domains restricts to those hosts (opt-in filtering)."""
        raw = [
            {"method": "GET", "url": "https://api.example.com/v1/items",
             "resource_type": "fetch", "response_headers": {"content-type": "application/json"}},
            {"method": "GET", "url": "https://abc.supabase.co/rest/v1/table",
             "resource_type": "fetch", "response_headers": {"content-type": "application/json"}},
        ]
        # With keep_domains, only the listed host survives.
        only_api = filter_traffic(raw, keep_domains=["api.example.com"])
        self.assertEqual([e["url"] for e in only_api], ["https://api.example.com/v1/items"])

        # Without keep_domains, both survive.
        both = filter_traffic(raw)
        self.assertEqual(len(both), 2)


if __name__ == "__main__":
    unittest.main()
