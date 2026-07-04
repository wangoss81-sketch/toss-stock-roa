from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any


@dataclass(frozen=True)
class StrategyConfig:
    symbol: str = "TQQQ"
    currency: str = "USD"
    average_down_buy_quantity: Decimal = Decimal("1")
    previous_close_buy_quantity: Decimal = Decimal("1")
    previous_close_multiplier: Decimal = Decimal("1.15")
    take_profit_multiplier: Decimal = Decimal("1.10")
    min_cash_buffer: Decimal = Decimal("0")


@dataclass(frozen=True)
class Position:
    quantity: Decimal
    average_price: Decimal

    @property
    def exists(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True)
class BuySignal:
    quantity: Decimal
    limit_price: Decimal
    reason: str


@dataclass(frozen=True)
class PlannedOrder:
    side: str
    order_type: str
    time_in_force: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    order_amount: Decimal | None = None
    reason: str = ""

    def to_toss_payload(self, symbol: str) -> dict[str, str]:
        payload: dict[str, str] = {
            "symbol": symbol,
            "side": self.side,
            "orderType": self.order_type,
        }
        if self.time_in_force is not None:
            payload["timeInForce"] = self.time_in_force
        if self.quantity is not None:
            payload["quantity"] = format_decimal(self.quantity)
        if self.price is not None:
            payload["price"] = format_decimal(self.price)
        if self.order_amount is not None:
            payload["orderAmount"] = format_decimal(self.order_amount)
        return payload


def parse_config(data: dict[str, Any]) -> StrategyConfig:
    raw = data.get("strategy", {})
    symbol = str(raw.get("symbol", "TQQQ")).upper()
    if symbol != "TQQQ":
        raise ValueError("이 프로그램은 TQQQ 전용입니다. strategy.symbol을 TQQQ로 설정하세요.")
    return StrategyConfig(
        symbol=symbol,
        currency=str(raw.get("currency", "USD")).upper(),
        average_down_buy_quantity=Decimal(str(raw.get("average_down_buy_quantity", "1"))),
        previous_close_buy_quantity=Decimal(str(raw.get("previous_close_buy_quantity", "1"))),
        previous_close_multiplier=Decimal(str(raw.get("previous_close_multiplier", "1.15"))),
        take_profit_multiplier=Decimal(str(raw.get("take_profit_multiplier", "1.10"))),
        min_cash_buffer=Decimal(str(raw.get("min_cash_buffer", "0"))),
    )


def position_from_holdings(holdings: dict[str, Any], symbol: str) -> Position:
    for item in holdings.get("items", []):
        if item.get("symbol", "").upper() == symbol.upper():
            return Position(
                quantity=Decimal(str(item["quantity"])),
                average_price=Decimal(str(item["averagePurchasePrice"])),
            )
    return Position(quantity=Decimal("0"), average_price=Decimal("0"))


class InfiniteBuyPlanner:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def plan(
        self,
        previous_close: Decimal,
        cash_buying_power: Decimal,
        position: Position,
    ) -> list[PlannedOrder]:
        planned_orders: list[PlannedOrder] = []
        if position.exists:
            target_price = position.average_price * self.config.take_profit_multiplier
            planned_orders.append(
                PlannedOrder(
                    side="SELL",
                    order_type="LIMIT",
                    quantity=position.quantity,
                    price=round_price(target_price, self.config.currency),
                    reason=f"평단가의 {self.config.take_profit_multiplier}배에 도달하면 전량 매도되도록 지정가 매도입니다.",
                )
            )

        available_cash = cash_buying_power - self.config.min_cash_buffer
        if available_cash <= 0:
            return planned_orders

        for buy_signal in self._buy_signals(previous_close, position):
            required_cash = buy_signal.limit_price * buy_signal.quantity
            if available_cash < required_cash:
                continue
            available_cash -= required_cash
            planned_orders.append(
                PlannedOrder(
                    side="BUY",
                    order_type="LIMIT",
                    time_in_force="CLS",
                    quantity=buy_signal.quantity,
                    price=round_price(buy_signal.limit_price, self.config.currency),
                    reason=buy_signal.reason,
                )
            )
        return planned_orders

    def _buy_signals(
        self,
        previous_close: Decimal,
        position: Position,
    ) -> list[BuySignal]:
        signals: list[BuySignal] = []
        if position.exists:
            signals.append(
                BuySignal(
                    quantity=self.config.average_down_buy_quantity,
                    limit_price=position.average_price,
                    reason="종가가 평단가 이하이면 체결되도록 TQQQ 종가 지정가 1주 매수입니다.",
                )
            )

        previous_close_limit = previous_close * self.config.previous_close_multiplier
        signals.append(
            BuySignal(
                quantity=self.config.previous_close_buy_quantity,
                limit_price=previous_close_limit,
                reason=f"종가가 전날 종가의 {self.config.previous_close_multiplier}배 이하이면 체결되도록 TQQQ 종가 지정가 1주 매수입니다.",
            )
        )
        return signals


def round_price(value: Decimal, currency: str) -> Decimal:
    if currency == "KRW":
        return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
    if value < Decimal("1"):
        return value.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    return value.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
