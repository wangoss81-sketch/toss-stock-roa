from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from toss_roa.engine import AppContext
from toss_roa.engine import build_snapshot, format_open_orders, format_snapshot, load_context, load_json, submit_planned_orders


@dataclass(frozen=True)
class TelegramConfig:
    token: str
    allowed_chat_ids: set[int]
    auto_enabled: bool = False
    auto_run_at: str = "05:50"
    timezone: str = "Asia/Seoul"


class TelegramClient:
    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"timeout": 25}
        if offset is not None:
            params["offset"] = offset
        return self._request("getUpdates", params)["result"]

    def send_message(self, chat_id: int, text: str) -> None:
        chunks = split_message(text)
        for chunk in chunks:
            self._request("sendMessage", {"chat_id": chat_id, "text": chunk})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        body = urllib.parse.urlencode(params).encode()
        request = urllib.request.Request(f"{self.base_url}/{method}", data=body, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode()
            raise RuntimeError(f"Telegram API error {exc.code}: {body_text}") from exc


class TossRoaBot:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.raw_config = load_json(config_path)
        self.telegram_config = parse_telegram_config(self.raw_config)
        self.telegram = TelegramClient(self.telegram_config.token)
        self._context: AppContext | None = None
        self.next_offset: int | None = None
        self.auto_enabled = self.telegram_config.auto_enabled
        self.last_auto_run_date: str | None = None

    def run_forever(self) -> None:
        self._broadcast("Toss ROA 봇이 시작됐습니다. /help 로 명령을 확인하세요.")
        while True:
            self._run_auto_if_due()
            try:
                updates = self.telegram.get_updates(self.next_offset)
            except Exception:
                time.sleep(5)
                continue
            for update in updates:
                self.next_offset = update["update_id"] + 1
                self._handle_update(update)

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not isinstance(chat_id, int) or not text:
            return
        if not self._is_allowed(chat_id):
            self.telegram.send_message(chat_id, "허용되지 않은 채팅입니다.")
            return

        command = text.split()[0].split("@")[0].lower()
        try:
            if command in {"/start", "/help"}:
                self.telegram.send_message(chat_id, help_text())
            elif command == "/whoami":
                self.telegram.send_message(chat_id, f"chat_id: {chat_id}")
            elif command == "/status":
                snapshot = build_snapshot(self.context)
                self.telegram.send_message(chat_id, format_snapshot(snapshot))
            elif command == "/plan":
                snapshot = build_snapshot(self.context)
                self.telegram.send_message(chat_id, format_snapshot(snapshot, include_plan=True))
            elif command == "/orders":
                orders = self.context.client.get_orders(self.context.account_seq, "OPEN", self.context.strategy.symbol)
                self.telegram.send_message(chat_id, format_open_orders(orders, self.context.strategy.symbol))
            elif command == "/run":
                self.telegram.send_message(chat_id, self._execute_once())
            elif command == "/auto_on":
                self.auto_enabled = True
                self.telegram.send_message(chat_id, f"자동 실행을 켰습니다. 매일 {self.telegram_config.auto_run_at} {self.telegram_config.timezone}")
            elif command == "/auto_off":
                self.auto_enabled = False
                self.telegram.send_message(chat_id, "자동 실행을 껐습니다.")
            elif command == "/auto":
                status = "ON" if self.auto_enabled else "OFF"
                self.telegram.send_message(chat_id, f"자동 실행: {status}\n시간: {self.telegram_config.auto_run_at} {self.telegram_config.timezone}")
            else:
                self.telegram.send_message(chat_id, "알 수 없는 명령입니다. /help 를 입력하세요.")
        except Exception as exc:
            self.telegram.send_message(chat_id, f"오류: {exc}")

    def _execute_once(self) -> str:
        snapshot = build_snapshot(self.context)
        if snapshot.open_orders:
            return format_snapshot(snapshot, include_plan=True)
        if not snapshot.planned_orders:
            return "제출할 주문이 없습니다."
        results = submit_planned_orders(self.context, snapshot)
        return format_snapshot(snapshot, include_plan=True) + "\n\n=== 주문 제출 결과 ===\n" + json.dumps(results, ensure_ascii=False, indent=2)

    def _run_auto_if_due(self) -> None:
        if not self.auto_enabled:
            return
        now = datetime.now(ZoneInfo(self.telegram_config.timezone))
        if now.strftime("%H:%M") != self.telegram_config.auto_run_at:
            return
        today = now.strftime("%Y-%m-%d")
        if self.last_auto_run_date == today:
            return
        self.last_auto_run_date = today
        try:
            message = "[자동 실행]\n" + self._execute_once()
        except Exception as exc:
            message = f"[자동 실행 오류]\n{exc}"
        self._broadcast(message)

    def _broadcast(self, text: str) -> None:
        for chat_id in self.telegram_config.allowed_chat_ids:
            self.telegram.send_message(chat_id, text)

    def _is_allowed(self, chat_id: int) -> bool:
        return not self.telegram_config.allowed_chat_ids or chat_id in self.telegram_config.allowed_chat_ids

    @property
    def context(self) -> AppContext:
        if self._context is None:
            self._context = load_context(self.config_path)
        return self._context


def parse_telegram_config(data: dict[str, Any]) -> TelegramConfig:
    raw = data.get("telegram", {})
    token = os.getenv("TELEGRAM_BOT_TOKEN", raw.get("bot_token", ""))
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN 환경변수 또는 config.json의 telegram.bot_token이 필요합니다.")
    chat_ids = {int(chat_id) for chat_id in raw.get("allowed_chat_ids", [])}
    auto = raw.get("auto", {})
    return TelegramConfig(
        token=token,
        allowed_chat_ids=chat_ids,
        auto_enabled=bool(auto.get("enabled", False)),
        auto_run_at=str(auto.get("run_at", "05:50")),
        timezone=str(auto.get("timezone", "Asia/Seoul")),
    )


def help_text() -> str:
    return "\n".join(
        [
            "Toss ROA 명령",
            "/status - 현재 상태",
            "/whoami - 내 chat_id 확인",
            "/plan - 오늘 걸 주문 미리보기",
            "/orders - 진행 중 주문 상세",
            "/run - 실제 주문 제출",
            "/auto - 자동 실행 상태",
            "/auto_on - 자동 실행 켜기",
            "/auto_off - 자동 실행 끄기",
        ]
    )


def split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    return [text[index : index + limit] for index in range(0, len(text), limit)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Toss ROA Telegram bot")
    parser.add_argument("--config", default="config.json", help="설정 JSON 경로")
    args = parser.parse_args()
    TossRoaBot(Path(args.config)).run_forever()


if __name__ == "__main__":
    main()
