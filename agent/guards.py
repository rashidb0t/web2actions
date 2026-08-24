"""
Challenge guards for Web2Actions (Module 17 / STORY-17.5).

Detects MFA, CAPTCHA, and anti-bot challenge signals in captured traffic and
page state, and reports them so the pipeline can explicitly refuse rather than
silently produce a broken connector. This is the documented boundary: Web2Actions
does NOT support MFA / CAPTCHA / anti-bot challenges (PRD §2 honest scoping).

Detection is signal-based and conservative: it looks for well-known URL and
content markers and returns a structured verdict. It never guesses a site is a
challenge based on a single generic token.
"""

from typing import Any, Dict, List, Optional

#: URL path/query tokens that strongly indicate MFA / 2FA flows.
_MFA_URL_TOKENS = ("/mfa", "/2fa", "/two-factor", "/otp", "/verify", "/totp",
                   "/authenticator", "twofactor", "2step", "verification-code")
#: MFA-related words that might appear in response bodies / titles.
_MFA_TEXT = ("two-factor", "two factor", "verification code", "authenticator app",
             "multi-factor", "enter your code", "otp code")

#: CAPTCHA / anti-bot tokens in URLs / headless detection markers.
_CAPTCHA_URL = ("captcha", "recaptcha", "hcaptcha", "g-recaptcha", "turnstile", "cf-turnstile")
#: Anti-bot / challenge page markers (Cloudflare "Just a moment", ...).
_BOT_BODY = ("just a moment", "not a robot", "unusual traffic", "challenge-platform",
             "cf-chl", "verifying you are human", "attention required")


def _scan_urls(entries: List[Dict[str, Any]]) -> Dict[str, bool]:
    """Scan captured request URLs for challenge tokens."""
    found = {"mfa": False, "captcha": False, "bot": False}
    for e in entries:
        url = (e.get("url") or "").lower()
        if any(t in url for t in _MFA_URL_TOKENS):
            found["mfa"] = True
        if any(t in url for t in _CAPTCHA_URL):
            found["captcha"] = True
        if any(t in url for t in _BOT_BODY):
            found["bot"] = True
        # A captured response body (if present) can carry markers too.
        body = (e.get("response_body") or "").lower()
        if body:
            if any(t in body for t in _MFA_TEXT):
                found["mfa"] = True
            if any(t in body for t in _BOT_BODY):
                found["bot"] = True
    return found


def _scan_text(text: str) -> Dict[str, bool]:
    """Scan arbitrary page text (title/html) for challenge markers."""
    t = (text or "").lower()
    return {
        "mfa": any(w in t for w in _MFA_TEXT) or any(w in t for w in _MFA_URL_TOKENS),
        "captcha": any(w in t for w in _CAPTCHA_URL),
        "bot": any(w in t for w in _BOT_BODY),
    }


def detect_challenges(
    entries: List[Dict[str, Any]],
    page_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect MFA / CAPTCHA / anti-bot signals across captured traffic and an
    optional page snapshot.

    Returns a verdict dict: {"blocked": bool, "reasons": [...]}. `blocked` is
    True when any challenge signal is found — the caller should refuse.
    """
    from_urls = _scan_urls(entries)
    reasons = []
    if page_text:
        from_text = _scan_text(page_text)
        for key, label in (("mfa", "MFA / two-factor auth"),
                           ("captcha", "CAPTCHA"),
                           ("bot", "anti-bot challenge")):
            if from_urls.get(key) or from_text.get(key):
                reasons.append(label)
    else:
        for key, label in (("mfa", "MFA / two-factor auth"),
                           ("captcha", "CAPTCHA"),
                           ("bot", "anti-bot challenge")):
            if from_urls.get(key):
                reasons.append(label)

    return {"blocked": bool(reasons), "reasons": reasons}


CHALLENGE_MESSAGE = (
    "This site appears to use {reasons}, which Web2Actions does not support. "
    "MFA / CAPTCHA / anti-bot flows cannot be captured and turned into tools. "
    "Refusing to continue so you don't get a broken connector."
)