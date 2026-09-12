"""Tests for Treasury simulation service."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.treasury import SimulationAccount, MarketCondition, MarketRegime, AssetClass, TradeExecution, CircuitBreaker


class TestTreasury:
    def test_create_account(self):
        a = SimulationAccount(athlete_id="athlete-1")
        assert a.account_id.startswith("sim-")
        assert a.balance == 100000.0
        assert a.initial_balance == 100000.0

    def test_market_condition_defaults(self):
        m = MarketCondition(name="Bull Market", regime=MarketRegime.BULL)
        assert m.volatility == 0.2
        assert m.trend == 0.0
        assert m.failure_probability == 0.0

    def test_crash_regime(self):
        m = MarketCondition(name="Flash Crash", regime=MarketRegime.CRASH, volatility=0.5, trend=-0.8)
        assert m.regime == MarketRegime.CRASH
        assert m.volatility == 0.5
        assert m.trend == -0.8

    def test_trade_execution(self):
        t = TradeExecution(
            account_id="sim-test",
            athlete_id="athlete-1",
            asset="BTC",
            side="buy",
            quantity=1.0,
            price=50000,
            execution_price=50100,
            slippage=0.002,
        )
        assert t.trade_id.startswith("trade-")
        assert t.execution_price == 50100
        assert t.slippage == 0.002

    def test_circuit_breaker_defaults(self):
        cb = CircuitBreaker(athlete_id="athlete-1")
        assert cb.is_triggered is False
        assert cb.max_daily_loss == 5000.0
        assert cb.max_position_size == 10000.0
        assert cb.max_leverage == 1.0

    def test_circuit_breaker_trigger(self):
        cb = CircuitBreaker(athlete_id="athlete-1")
        cb.is_triggered = True
        cb.trigger_reason = "max_daily_loss_exceeded"
        assert cb.is_triggered is True
