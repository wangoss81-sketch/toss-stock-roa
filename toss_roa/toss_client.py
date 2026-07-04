from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class TossApiError(RuntimeError):
    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(f"Toss API error {status}: {payload}")


@dataclass
class TossCredentials:
    client_id: str
    client_secret: str


class TossInvestClient:
    def __init__(
        self,
        credentials: TossCredentials,
        base_url: str = "https://openapi.tossinvest.com",
        timeout: float = 20.0,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._access_token: str | None = None
        self._expires_at = 0.0

    def issue_token(self) -> str:
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
            }
        ).encode()
        payload = self._raw_request(
            "POST",
            "/oauth2/token",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=False,
        )
        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = token
        self._expires_at = time.time() + max(0, expires_in - 60)
        return token

    def get_accounts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/accounts")["result"]

    def get_prices(self, symbols: list[str]) -> list[dict[str, Any]]:
        params = {"symbols": ",".join(symbols)}
        return self._request("GET", "/api/v1/prices", params=params)["result"]

    def get_candles(
        self,
        symbol: str,
        interval: str = "1d",
        count: int = 2,
        adjusted: bool = True,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": symbol,
            "interval": interval,
            "count": count,
            "adjusted": str(adjusted).lower(),
        }
        return self._request("GET", "/api/v1/candles", params=params)["result"]["candles"]

    def get_us_market_calendar(self, date: str | None = None) -> dict[str, Any]:
        params = {"date": date} if date else None
        return self._request("GET", "/api/v1/market-calendar/US", params=params)["result"]

    def get_holdings(self, account_seq: int, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return self._request(
            "GET",
            "/api/v1/holdings",
            params=params,
            account_seq=account_seq,
        )["result"]

    def get_buying_power(self, account_seq: int, currency: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/buying-power",
            params={"currency": currency},
            account_seq=account_seq,
        )["result"]

    def get_orders(self, account_seq: int, status: str, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"status": status}
        if symbol:
            params["symbol"] = symbol
        return self._request(
            "GET",
            "/api/v1/orders",
            params=params,
            account_seq=account_seq,
        )["result"]["orders"]

    def create_order(self, account_seq: int, order: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/orders",
            payload=order,
            account_seq=account_seq,
        )["result"]

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        account_seq: int | None = None,
    ) -> dict[str, Any]:
        if not self._access_token or time.time() >= self._expires_at:
            self.issue_token()
        headers = {"Authorization": f"Bearer {self._access_token}"}
        if account_seq is not None:
            headers["X-Tossinvest-Account"] = str(account_seq)
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        return self._raw_request(method, path, params=params, body=body, headers=headers)

    def _raw_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        if params:
            path = f"{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers or {},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode()
                return json.loads(text) if text else {}
        except urllib.error.HTTPError as exc:
            text = exc.read().decode()
            try:
                payload: Any = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            raise TossApiError(exc.code, payload) from exc
