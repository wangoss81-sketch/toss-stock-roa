from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from toss_roa.strategy import (
    InfiniteBuyPlanner,
    PlannedOrder,
    Position,
    StrategyConfig,
    format_decimal,
    parse_config,
    position_from_holdings,
)
from toss_roa.toss_client import TossCredentials, TossInvestClient


@dataclass(frozen=True)
class AppContext:
    client: TossInvestClient
    account_seq: int
    strategy: StrategyConfig


@dataclass(frozen=True)
class StrategySnapshot:
    symbol: str
    currency: str
    last_price: Decimal
    previous_close: Decimal
    position: Position
    cash_buying_power: Decimal
    open_orders: list[dict[str, Any]]
    planned_orders: list[PlannedOrder]
    market_open: bool
    take_profit_multiplier: Decimal
    market_message: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"설정 파일이 없습니다: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_context(config_path: Path) -> AppContext:
    data = load_json(config_path)
    client = TossInvestClient(
        TossCredentials(
            client_id=os.getenv("TOSS_CLIENT_ID", data.get("client_id", "")),
            client_secret=os.getenv("TOSS_CLIENT_SECRET", data.get("client_secret", "")),
        )
    )

    account_seq = data.get("account_seq")
    if account_seq is None:
        accounts = client.get_accounts()
        if not accounts:
            raise SystemExit("사용 가능한 계좌가 없습니다.")
        account_seq = accounts[0]["accountSeq"]

    return AppContext(
        client=client,
        account_seq=int(account_seq),
        strategy=parse_config(data),
    )


def build_snapshot(context: AppContext) -> StrategySnapshot:
    strategy = context.strategy
    calendar = context.client.get_us_market_calendar(us_local_date())
    today_market = calendar["today"]
    market_open = today_market.get("regularMarket") is not None
    market_message = None if market_open else f"미국장 휴장일입니다: {today_market['date']}"

    prices = context.client.get_prices([strategy.symbol])
    if not prices:
        raise RuntimeError(f"현재가를 찾지 못했습니다: {strategy.symbol}")
    last_price = Decimal(str(prices[0]["lastPrice"]))

    candles = context.client.get_candles(strategy.symbol, interval="1d", count=2)
    if len(candles) < 2:
        raise RuntimeError(f"전날 종가를 찾지 못했습니다: {strategy.symbol}")
    previous_close = Decimal(str(candles[1]["closePrice"]))

    holdings = context.client.get_holdings(context.account_seq, strategy.symbol)
    position = position_from_holdings(holdings, strategy.symbol)
    buying_power = context.client.get_buying_power(context.account_seq, strategy.currency)
    cash_buying_power = Decimal(str(buying_power["cashBuyingPower"]))
    open_orders = context.client.get_orders(context.account_seq, "OPEN", strategy.symbol)
    planned_orders = []
    if market_open:
        planned_orders = InfiniteBuyPlanner(strategy).plan(previous_close, cash_buying_power, position)

    return StrategySnapshot(
        symbol=strategy.symbol,
        currency=strategy.currency,
        last_price=last_price,
        previous_close=previous_close,
        position=position,
        cash_buying_power=cash_buying_power,
        open_orders=open_orders,
        planned_orders=planned_orders,
        market_open=market_open,
        take_profit_multiplier=strategy.take_profit_multiplier,
        market_message=market_message,
    )


def submit_planned_orders(context: AppContext, snapshot: StrategySnapshot) -> list[dict[str, Any]]:
    if not snapshot.market_open:
        raise RuntimeError(snapshot.market_message or "미국장이 열리지 않아 주문을 제출하지 않습니다.")
    if snapshot.open_orders:
        raise RuntimeError("진행 중 주문이 있어 새 주문은 만들지 않습니다.")
    results = []
    for order in snapshot.planned_orders:
        results.append(context.client.create_order(context.account_seq, order.to_toss_payload(context.strategy.symbol)))
    return results


def format_snapshot(snapshot: StrategySnapshot, include_plan: bool = False) -> str:
    lines = [
        "=== 상태 ===",
        f"종목: {snapshot.symbol}",
        f"현재가: {snapshot.last_price} {snapshot.currency}",
        f"전날 종가: {snapshot.previous_close} {snapshot.currency}",
        f"보유수량: {snapshot.position.quantity}",
        f"평균단가: {snapshot.position.average_price}",
    ]
    if snapshot.position.exists:
        target_price = snapshot.position.average_price * snapshot.take_profit_multiplier
        lines.extend(
            [
                f"평단 대비: {format_percent(percent_change(snapshot.last_price, snapshot.position.average_price))}",
                f"목표 매도가: {format_money(target_price)} {snapshot.currency}",
                f"목표까지: {format_percent(percent_change(target_price, snapshot.last_price))}",
            ]
        )
    lines.extend(
        [
            f"매수가능금액: {snapshot.cash_buying_power} {snapshot.currency}",
            f"진행 중 주문: {len(snapshot.open_orders)}건",
            f"미국장: {'영업일' if snapshot.market_open else '휴장'}",
        ]
    )
    if snapshot.market_message:
        lines.append(snapshot.market_message)
    if include_plan:
        lines.append("")
        lines.append("=== 주문 계획 ===")
        if not snapshot.market_open:
            lines.append(snapshot.market_message or "미국장이 열리지 않아 주문을 만들지 않습니다.")
        elif snapshot.open_orders:
            lines.append("진행 중 주문이 있어 새 주문은 만들지 않습니다.")
        elif not snapshot.planned_orders:
            lines.append("생성할 주문이 없습니다.")
        else:
            for index, order in enumerate(snapshot.planned_orders, start=1):
                if index > 1:
                    lines.append("")
                lines.append(f"{index}. {order.reason}")
                lines.extend(format_planned_order(order, snapshot.symbol, snapshot.currency))
    return "\n".join(lines)


def format_planned_order(order: PlannedOrder, symbol: str, currency: str) -> list[str]:
    order_method = "종가 지정가(LOC)" if order.time_in_force == "CLS" else "지정가"
    lines = [
        f"종목: {symbol}",
        f"구분: {'매도' if order.side == 'SELL' else '매수'}",
        f"주문방식: {order_method}",
    ]
    if order.quantity is not None:
        lines.append(f"수량: {format_decimal(order.quantity)}주")
    if order.price is not None:
        lines.append(f"가격: {format_money(order.price)} {currency}")
    if order.order_amount is not None:
        lines.append(f"주문금액: {format_money(order.order_amount)} {currency}")
    return lines


def format_submission_results(snapshot: StrategySnapshot, results: list[dict[str, Any]]) -> str:
    lines = ["=== 주문 제출 결과 ==="]
    for index, order in enumerate(snapshot.planned_orders, start=1):
        result = results[index - 1] if index <= len(results) else {}
        status = "접수 완료" if result.get("orderId") else "응답 확인 필요"
        lines.append("")
        lines.append(f"{index}. {planned_order_name(order)} {status}")
        lines.extend(format_planned_order(order, snapshot.symbol, snapshot.currency))
    return "\n".join(lines)


def planned_order_name(order: PlannedOrder) -> str:
    if order.side == "SELL":
        return "전량 매도 주문"
    if "평단가" in order.reason:
        return "평단가 기준 LOC 매수 주문"
    if "전날 종가" in order.reason:
        return "전날 종가 기준 LOC 매수 주문"
    return "매수 주문"


def format_open_orders(orders: list[dict[str, Any]], symbol: str) -> str:
    if not orders:
        return f"진행 중 {symbol} 주문이 없습니다."

    lines = [f"진행 중 {symbol} 주문 {len(orders)}건"]
    for index, order in enumerate(orders, start=1):
        execution = order.get("execution") or {}
        filled_quantity = execution.get("filledQuantity", "0")
        quantity = order.get("quantity") or "-"
        price = order.get("price") or "-"
        order_amount = order.get("orderAmount")
        time_in_force = order.get("timeInForce")

        title_parts = [
            str(order.get("side", "-")),
            str(order.get("orderType", "-")),
        ]
        if time_in_force:
            title_parts.append(str(time_in_force))

        lines.append("")
        lines.append(f"{index}. {' '.join(title_parts)}")
        lines.append(f"가격: {price}")
        if order_amount:
            lines.append(f"주문금액: {order_amount}")
        lines.append(f"수량: {quantity}")
        lines.append(f"상태: {order.get('status', '-')}")
        lines.append(f"체결: {filled_quantity} / {quantity}")
        if order.get("orderedAt"):
            lines.append(f"주문시각: {order['orderedAt']}")
    return "\n".join(lines)


def percent_change(new_value: Decimal, base_value: Decimal) -> Decimal:
    if base_value == 0:
        return Decimal("0")
    return ((new_value - base_value) / base_value) * Decimal("100")


def format_percent(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded}%"


def format_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def us_local_date() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
