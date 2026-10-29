"""
Portal HTTP client.
Handles Better-Auth session management, automatic re-auth, and HMAC request signing.
"""

import asyncio
import hashlib
import hmac
import logging
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_AUTH_PATH = "/api/auth/sign-in/email"
_KEYS_PATH = "/portal/keys"


class PortalClient:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._auth_lock = asyncio.Lock()
        self._authenticated = False
        self._signing_secret: Optional[str] = None
        self._semaphore = asyncio.Semaphore(settings.portal_max_concurrency)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.portal_url,
                timeout=settings.portal_timeout,
                follow_redirects=True,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            self._authenticated = False
            self._signing_secret = None

    async def login(self) -> None:
        """Authenticate against the portal and store the session cookie."""
        async with self._auth_lock:
            if self._authenticated:
                return

            client = await self._ensure_client()
            logger.info("Authenticating with portal at %s...", settings.portal_url)

            resp = await client.post(
                _AUTH_PATH,
                json={
                    "email": settings.portal_email,
                    "password": settings.portal_password,
                },
            )

            if resp.status_code not in (200, 201):
                raise RuntimeError(
                    f"Portal login failed - HTTP {resp.status_code}: {resp.text[:200]}"
                )

            self._authenticated = True
            logger.info("Portal authentication successful.")

    async def get_signing_secret(self) -> str:
        """Fetch and cache the HMAC signing secret used for /portal/export."""
        if self._signing_secret:
            return self._signing_secret

        resp = await self.get(_KEYS_PATH)
        if resp.status_code == 200:
            data = resp.json()
            secret = data.get("data", {}).get("signingSecret")
            if secret:
                self._signing_secret = secret
                return secret

        raise RuntimeError("Failed to fetch signing secret from portal.")

    def sign_request(self, method: str, path: str, query: str, secret: str) -> dict[str, str]:
        """
        Generate HMAC-SHA256 signature required by /portal/export.
        Canonical string format: f"{method}\\n{path}\\n{query}\\n{timestamp}"
        """
        timestamp = str(int(time.time()))
        canonical_msg = f"{method}\n{path}\n{query}\n{timestamp}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), canonical_msg, hashlib.sha256).hexdigest()
        return {
            "x-timestamp": timestamp,
            "x-signature": signature,
        }

    def _looks_like_auth_redirect(self, resp: httpx.Response) -> bool:
        if resp.status_code == 401:
            return True
        if "login" in str(resp.url).lower() and resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type:
                return True
        return False

    async def _reauth(self) -> None:
        self._authenticated = False
        self._signing_secret = None
        await self.login()

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """
        Send an authenticated GET request to the portal.
        Re-authenticates automatically if session expires.
        """
        if not self._authenticated:
            await self.login()

        client = await self._ensure_client()

        async with self._semaphore:
            resp = await client.get(path, **kwargs)

        if self._looks_like_auth_redirect(resp):
            logger.warning("Session expired or unauthorized - re-authenticating...")
            await self._reauth()
            async with self._semaphore:
                resp = await client.get(path, **kwargs)

        return resp


portal_client = PortalClient()
