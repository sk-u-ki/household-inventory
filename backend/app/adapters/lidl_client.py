"""Live Lidl Plus tickets client. Refresh token only — no browser login here."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from app.config import Settings, get_settings

AUTH_API = "https://accounts.lidl.com"
TICKET_API = "https://tickets.lidlplus.com/api/v2"
TICKET_V3_API = "https://tickets.lidlplus.com/api/v3"
CLIENT_ID = "LidlPlusNativeClient"
APP_VERSION = "17.9.3"
TOKEN_LEEWAY = timedelta(seconds=30)
DEFAULT_TOKEN_FILE = Path.home() / ".config/lidl-plus/refresh_token"


class LidlClientError(RuntimeError):
    """Lidl Plus API is unreachable or rejected the request."""


class LidlNotConfigured(LidlClientError):
    """Refresh token is missing."""


class LidlPlusClient:
    def __init__(
        self,
        refresh_token: str,
        language: str = "pl",
        country: str = "PL",
        token_file: Path | None = None,
    ) -> None:
        self.language = language.lower()
        self.country = country.upper()
        self.token_file = token_file
        self._refresh_token = refresh_token.strip()
        self._access_token = ""
        self._expires: datetime | None = None
        self._session = requests.Session()

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> LidlPlusClient:
        cfg = settings or get_settings()
        token_file = Path(cfg.lidl_refresh_token_file).expanduser() if cfg.lidl_refresh_token_file else DEFAULT_TOKEN_FILE
        token = (cfg.lidl_refresh_token or "").strip()
        used_file: Path | None = None
        if not token and token_file.is_file():
            token = token_file.read_text(encoding="utf-8").strip()
            used_file = token_file
        if not token:
            raise LidlNotConfigured(
                "Lidl refresh token is missing. Set LIDL_REFRESH_TOKEN or save it to ~/.config/lidl-plus/refresh_token"
            )
        return cls(
            refresh_token=token,
            language=cfg.lidl_language,
            country=cfg.lidl_country,
            token_file=used_file if used_file else (token_file if cfg.lidl_refresh_token_file else None),
        )

    def tickets(self) -> list[dict[str, Any]]:
        url = f"{TICKET_API}/{self.country}/tickets"
        tickets: list[dict[str, Any]] = []
        page_number = 1
        while True:
            page = self._request("GET", url, params={"pageNumber": page_number, "onlyFavorite": "false"})
            page_tickets = page.get("tickets") or []
            tickets.extend(page_tickets)
            if not page_tickets or len(tickets) >= page.get("totalCount", len(tickets)):
                break
            page_number += 1
        return tickets

    def ticket(self, ticket_id: str) -> dict[str, Any]:
        url = f"{TICKET_API}/{self.country}/tickets/{ticket_id}"
        try:
            return self._request("GET", url)
        except LidlClientError:
            return self._request("GET", f"{TICKET_V3_API}/{self.country}/tickets/{ticket_id}")

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._session.request(
                method,
                url,
                headers={**self._headers(), **kwargs.pop("headers", {})},
                timeout=20,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise LidlClientError(f"Lidl Plus request failed: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "App-Version": APP_VERSION,
            "Operating-System": "iOs",
            "App": "com.lidl.eci.lidl.plus",
            "Accept-Language": self.language,
        }

    def _ensure_token(self) -> None:
        now = datetime.now(timezone.utc)
        if self._access_token and self._expires and now + TOKEN_LEEWAY < self._expires:
            return
        secret = base64.b64encode(f"{CLIENT_ID}:secret".encode()).decode()
        try:
            response = self._session.post(
                f"{AUTH_API}/connect/token",
                headers={
                    "Authorization": f"Basic {secret}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"refresh_token": self._refresh_token, "grant_type": "refresh_token"},
                timeout=20,
            )
            response.raise_for_status()
            tokens = response.json()
        except requests.RequestException as exc:
            raise LidlClientError("Lidl Plus login expired. Refresh the token and try again.") from exc

        self._access_token = tokens["access_token"]
        self._expires = now + timedelta(seconds=int(tokens["expires_in"]))
        new_refresh = (tokens.get("refresh_token") or "").strip()
        if new_refresh and new_refresh != self._refresh_token:
            self._refresh_token = new_refresh
            if self.token_file is not None:
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                self.token_file.write_text(new_refresh + "\n", encoding="utf-8")
                self.token_file.chmod(0o600)
