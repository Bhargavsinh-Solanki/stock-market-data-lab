"""Rate-limited, retrying HTTP client with robots.txt compliance.

Every outbound request:
  * identifies itself with a descriptive User-Agent including a contact email
  * is checked against the host's robots.txt (unless disabled in settings)
  * is throttled to at most one request per `rate_limit_seconds` per client
  * retries transient failures with exponential backoff
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ComplianceError(RuntimeError):
    """Raised when a request would violate robots.txt or a source toggle."""


class RateLimitedClient:
    def __init__(self, rate_limit_seconds: float | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._rate_limit = (
            settings.rate_limit_seconds if rate_limit_seconds is None else rate_limit_seconds
        )
        self._last_request_at = 0.0
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._client = httpx.Client(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    # -- robots.txt ---------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        host = urlparse(url).netloc
        if host not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
            try:
                resp = self._client.get(robots_url)
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                else:
                    rp.parse([])  # no robots.txt -> everything allowed
            except httpx.HTTPError:
                logger.warning("Could not fetch robots.txt for %s; assuming allowed", host)
                rp.parse([])
            self._robots_cache[host] = rp
        return self._robots_cache[host]

    def _check_allowed(self, url: str) -> None:
        if not self._settings.respect_robots_txt:
            return
        rp = self._robots_for(url)
        if not rp.can_fetch(self._settings.user_agent, url):
            raise ComplianceError(
                f"robots.txt for {urlparse(url).netloc} disallows fetching {url}; "
                "skipping per compliance policy."
            )

    # -- throttling ---------------------------------------------------------
    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._rate_limit:
            time.sleep(self._rate_limit - elapsed)
        self._last_request_at = time.monotonic()

    # -- public API ---------------------------------------------------------
    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        self._check_allowed(url)
        self._throttle()
        resp = self._client.get(url, params=params)
        if resp.status_code == 429:
            # Server asked us to slow down: honor it, then let tenacity retry.
            retry_after = float(resp.headers.get("Retry-After", 30))
            logger.warning("HTTP 429 from %s; sleeping %.0fs", url, retry_after)
            time.sleep(retry_after)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RateLimitedClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
