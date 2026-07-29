import unittest

from toss_roa.telegram_bot import confirm_keyboard, main_keyboard, normalize_command


class TelegramKeyboardTest(unittest.TestCase):
    def test_main_keyboard_can_be_hidden(self):
        keyboard = main_keyboard()

        self.assertTrue(keyboard["resize_keyboard"])
        self.assertNotIn("is_persistent", keyboard)
        self.assertEqual(
            keyboard["keyboard"],
            [
                [{"text": "상태 조회"}, {"text": "주문 미리보기"}],
                [{"text": "현재 주문"}, {"text": "자동 상태"}],
                [{"text": "자동 ON"}, {"text": "자동 OFF"}],
                [{"text": "실행"}, {"text": "도움말"}],
            ],
        )

    def test_main_buttons_keep_their_commands(self):
        expected_commands = {
            "상태 조회": "/status",
            "주문 미리보기": "/plan",
            "현재 주문": "/orders",
            "자동 상태": "/auto",
            "자동 ON": "/auto_on",
            "자동 OFF": "/auto_off",
            "실행": "/run_confirm",
            "도움말": "/help",
        }

        for button, command in expected_commands.items():
            with self.subTest(button=button):
                self.assertEqual(normalize_command(button), command)

    def test_confirm_keyboard_remains_one_time(self):
        keyboard = confirm_keyboard()

        self.assertTrue(keyboard["resize_keyboard"])
        self.assertTrue(keyboard["one_time_keyboard"])
        self.assertEqual(
            keyboard["keyboard"],
            [
                [{"text": "주문 실행 확인"}, {"text": "취소"}],
                [{"text": "상태 조회"}, {"text": "주문 미리보기"}],
            ],
        )
        self.assertEqual(normalize_command("주문 실행 확인"), "/run")
        self.assertEqual(normalize_command("취소"), "/cancel")


if __name__ == "__main__":
    unittest.main()
