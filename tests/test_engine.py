import unittest
from decimal import Decimal

from toss_roa.engine import StrategySnapshot, format_snapshot
from toss_roa.strategy import Position


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


if __name__ == "__main__":
    unittest.main()
