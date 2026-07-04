from __future__ import annotations

import argparse
import json

from pathlib import Path

from toss_roa.engine import build_snapshot, format_snapshot, load_context, load_json, submit_planned_orders
from toss_roa.toss_client import TossApiError, TossCredentials, TossInvestClient


def main() -> None:
    parser = argparse.ArgumentParser(description="토스증권 API 기반 라오어식 무한매수법 실행 도구")
    parser.add_argument("--config", default="config.json", help="설정 JSON 경로")
    parser.add_argument("--execute", action="store_true", help="실제 주문을 제출합니다. 없으면 드라이런입니다.")
    parser.add_argument("--accounts", action="store_true", help="계좌 목록만 조회합니다.")
    args = parser.parse_args()

    try:
        run(args)
    except TossApiError as exc:
        print(f"토스 API 오류 {exc.status}: {json.dumps(exc.payload, ensure_ascii=False)}")


def run(args: argparse.Namespace) -> None:
    if args.accounts:
        data = load_json(Path(args.config))
        client = TossInvestClient(
            TossCredentials(
                client_id=data.get("client_id", ""),
                client_secret=data.get("client_secret", ""),
            )
        )
        print_json(client.get_accounts())
        return

    context = load_context(Path(args.config))

    snapshot = build_snapshot(context)
    print(format_snapshot(snapshot, include_plan=True))
    if snapshot.open_orders:
        return

    if not snapshot.planned_orders:
        return

    if args.execute:
        print("\n=== 주문 제출 결과 ===")
        print_json(submit_planned_orders(context, snapshot))
    else:
        print("\n드라이런: 실제 주문은 제출하지 않았습니다. 실행하려면 --execute를 붙이세요.")


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
