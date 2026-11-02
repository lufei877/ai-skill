import unittest

from pricing import quote


class PricingTests(unittest.TestCase):
    def test_large_order(self):
        self.assertEqual(quote(15000), 15000)
