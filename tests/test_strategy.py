import unittest
from decimal import Decimal

from toss_roa.strategy import InfiniteBuyPlanner, Position, StrategyConfig


class InfiniteBuyPlannerTest(unittest.TestCase):
    def test_places_three_daily_orders_when_position_exists(self):
        planner = InfiniteBuyPlanner(StrategyConfig())

        orders = planner.plan(
            previous_close=Decimal("100"),
            cash_buying_power=Decimal("1000"),
            position=Position(quantity=Decimal("10"), average_price=Decimal("100")),
        )

        self.assertEqual(len(orders), 3)
        self.assertEqual(orders[0].side, "SELL")
        self.assertEqual(orders[0].order_type, "LIMIT")
        self.assertEqual(orders[0].price, Decimal("110.00"))
        self.assertEqual(orders[0].quantity, Decimal("10"))
        self.assertEqual(orders[1].side, "BUY")
        self.assertEqual(orders[1].order_type, "LIMIT")
        self.assertEqual(orders[1].time_in_force, "CLS")
        self.assertEqual(orders[1].price, Decimal("100.00"))
        self.assertEqual(orders[1].quantity, Decimal("1"))
        self.assertEqual(orders[2].side, "BUY")
        self.assertEqual(orders[2].time_in_force, "CLS")
        self.assertEqual(orders[2].price, Decimal("115.00"))
        self.assertEqual(orders[2].quantity, Decimal("1"))

    def test_places_previous_close_loc_buy_order_without_position(self):
        planner = InfiniteBuyPlanner(StrategyConfig())

        orders = planner.plan(
            previous_close=Decimal("100"),
            cash_buying_power=Decimal("1000"),
            position=Position(quantity=Decimal("0"), average_price=Decimal("0")),
        )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side, "BUY")
        self.assertEqual(orders[0].time_in_force, "CLS")
        self.assertEqual(orders[0].price, Decimal("115.00"))
        self.assertEqual(orders[0].quantity, Decimal("1"))

    def test_places_sell_order_even_before_take_profit(self):
        planner = InfiniteBuyPlanner(StrategyConfig())

        orders = planner.plan(
            previous_close=Decimal("100"),
            cash_buying_power=Decimal("1000"),
            position=Position(quantity=Decimal("5"), average_price=Decimal("100")),
        )

        self.assertEqual(len(orders), 3)
        self.assertEqual(orders[0].side, "SELL")
        self.assertEqual(orders[0].price, Decimal("110.00"))
        self.assertEqual(orders[0].quantity, Decimal("5"))

    def test_keeps_sell_order_even_without_buying_power(self):
        planner = InfiniteBuyPlanner(StrategyConfig(min_cash_buffer=Decimal("100")))

        orders = planner.plan(
            previous_close=Decimal("100"),
            cash_buying_power=Decimal("100"),
            position=Position(quantity=Decimal("5"), average_price=Decimal("100")),
        )

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].side, "SELL")
        self.assertEqual(orders[0].price, Decimal("110.00"))

    def test_respects_cash_buffer(self):
        planner = InfiniteBuyPlanner(
            StrategyConfig(
                min_cash_buffer=Decimal("100"),
            )
        )

        self.assertEqual(
            planner.plan(
                previous_close=Decimal("100"),
                cash_buying_power=Decimal("100"),
                position=Position(quantity=Decimal("0"), average_price=Decimal("0")),
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
