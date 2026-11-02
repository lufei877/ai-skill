import unittest

from app import subtotal


class SubtotalTests(unittest.TestCase):
    def test_empty_prices(self):
        self.assertEqual(subtotal([]), 0)


if __name__ == "__main__":
    unittest.main()
