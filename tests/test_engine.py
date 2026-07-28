import unittest
from decimal import Decimal

from toss_roa.engine import StrategySnapshot, format_snapshot, format_submission_results
from toss_roa.strategy import PlannedOrder, Position


def make_snapshot() -> StrategySnapshot:
    return StrategySnapshot(
        symbol="TQQQ",
        currency="USD",
        last_price=Decimal("61.60"),
        previous_close=Decimal("63.40"),
        position=Position(quantity=Decimal("41"), average_price=Decimal("76.804146")),
        cash_buying_power=Decimal("1300.72"),
        open_orders=[],
        planned_orders=[
            PlannedOrder(
                side="SELL",
                order_type="LIMIT",
                quantity=Decimal("41"),
                price=Decimal("84.48"),
                reason="평단가의 1.10배에 도달하면 전량 매도되도록 지정가 매도입니다.",
            ),
            PlannedOrder(
                side="BUY",
                order_type="LIMIT",
                time_in_force="CLS",
                quantity=Decimal("1"),
                price=Decimal("76.80"),
                reason="종가가 평단가 이하이면 체결되도록 TQQQ 종가 지정가 1주 매수입니다.",
            ),
            PlannedOrder(
                side="BUY",
                order_type="LIMIT",
                time_in_force="CLS",
                quantity=Decimal("1"),
                price=Decimal("72.91"),
                reason="종가가 전날 종가의 1.15배 이하이면 체결되도록 TQQQ 종가 지정가 1주 매수입니다.",
            ),
        ],
        market_open=True,
        take_profit_multiplier=Decimal("1.10"),
    )


class FormatSnapshotTest(unittest.TestCase):
    def test_includes_position_performance_when_position_exists(self):
        snapshot = StrategySnapshot(
            symbol="TQQQ",
            currency="USD",
            last_price=Decimal("73.79"),
            previous_close=Decimal("77.46"),
            position=Position(quantity=Decimal("37"), average_price=Decimal("77.072162")),
            cash_buying_power=Decimal("350.52"),
            open_orders=[],
            planned_orders=[],
            market_open=True,
            take_profit_multiplier=Decimal("1.10"),
        )

        text = format_snapshot(snapshot)

        self.assertIn("평단 대비: -4.26%", text)
        self.assertIn("목표 매도가: 84.78 USD", text)
        self.assertIn("목표까지: +14.89%", text)

    def test_omits_position_performance_without_position(self):
        snapshot = StrategySnapshot(
            symbol="TQQQ",
            currency="USD",
            last_price=Decimal("73.79"),
            previous_close=Decimal("77.46"),
            position=Position(quantity=Decimal("0"), average_price=Decimal("0")),
            cash_buying_power=Decimal("350.52"),
            open_orders=[],
            planned_orders=[],
            market_open=True,
            take_profit_multiplier=Decimal("1.10"),
        )

        text = format_snapshot(snapshot)

        self.assertNotIn("평단 대비:", text)
        self.assertNotIn("목표 매도가:", text)
        self.assertNotIn("목표까지:", text)

    def test_formats_order_plan_without_raw_json(self):
        snapshot = make_snapshot()

        text = format_snapshot(snapshot, include_plan=True)

        self.assertIn("구분: 매도", text)
        self.assertIn("주문방식: 지정가", text)
        self.assertIn("수량: 41주", text)
        self.assertIn("가격: 84.48 USD", text)
        self.assertIn("주문방식: 종가 지정가(LOC)", text)
        self.assertNotIn('{"symbol":', text)

    def test_formats_submission_results_without_order_ids(self):
        snapshot = make_snapshot()
        results = [
            {"orderId": "sell-order-id", "clientOrderId": None},
            {"orderId": "buy-order-id", "clientOrderId": None},
            {"orderId": "previous-close-order-id", "clientOrderId": None},
        ]

        text = format_submission_results(snapshot, results)

        self.assertIn("1. 전량 매도 주문 접수 완료", text)
        self.assertIn("2. 평단가 기준 LOC 매수 주문 접수 완료", text)
        self.assertIn("3. 전날 종가 기준 LOC 매수 주문 접수 완료", text)
        self.assertNotIn("sell-order-id", text)
        self.assertNotIn("buy-order-id", text)
        self.assertNotIn("previous-close-order-id", text)
        self.assertNotIn("clientOrderId", text)


if __name__ == "__main__":
    unittest.main()
