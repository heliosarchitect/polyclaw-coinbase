import unittest

from lib.safety import PreTradeRequest, SafetyConfig, run_pretrade_checks


def _cfg(**overrides):
    base = SafetyConfig(
        trading_enabled=True,
        max_trade_usd=25.0,
        min_market_liquidity_usd=1000.0,
        max_implied_slippage=0.15,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _req(**overrides):
    base = PreTradeRequest(
        market_id="m1",
        position="YES",
        amount_usd=10.0,
        usdc_balance=100.0,
        approvals_ok=True,
        market_active=True,
        market_closed=False,
        market_resolved=False,
        market_liquidity=5000.0,
        wanted_price=0.53,
        unwanted_price=0.47,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


class SafetyChecksTest(unittest.TestCase):
    def test_pretrade_happy_path_passes(self):
        result = run_pretrade_checks(_req(), _cfg())
        self.assertTrue(result.ok)
        self.assertEqual(result.reasons, [])

    def test_pretrade_blocks_when_killswitch_disabled(self):
        result = run_pretrade_checks(_req(), _cfg(trading_enabled=False))
        self.assertFalse(result.ok)
        self.assertTrue(any("kill-switch" in r for r in result.reasons))

    def test_pretrade_blocks_over_max_trade_size(self):
        result = run_pretrade_checks(_req(amount_usd=30.0), _cfg(max_trade_usd=25.0))
        self.assertFalse(result.ok)
        self.assertTrue(any("exceeds max" in r for r in result.reasons))

    def test_pretrade_blocks_missing_approvals(self):
        result = run_pretrade_checks(_req(approvals_ok=False), _cfg())
        self.assertFalse(result.ok)
        self.assertTrue(any("approvals" in r for r in result.reasons))

    def test_pretrade_blocks_low_liquidity_and_high_slippage(self):
        result = run_pretrade_checks(
            _req(market_liquidity=50.0, wanted_price=0.80, unwanted_price=0.35),
            _cfg(min_market_liquidity_usd=1000.0, max_implied_slippage=0.10),
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("liquidity" in r for r in result.reasons))
        self.assertTrue(any("implied slippage" in r for r in result.reasons))


if __name__ == "__main__":
    unittest.main()
