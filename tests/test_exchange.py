"""Tests for exchange adapters and circuit breaker drills."""
import sys
sys.path.insert(0, ".")

import pytest
from apps.treasury.exchange import (
    ExchangeAdapter, ExchangeOrder, ExchangeStatus, OrderStatus, OrderType,
    CircuitBreakerDrillType, DRILL_DEFINITIONS,
)


class TestExchangeAdapter:
    @pytest.mark.asyncio
    async def test_place_market_order(self):
        adapter = ExchangeAdapter()
        order = ExchangeOrder(
            athlete_id="athlete-1",
            asset="BTC",
            side="buy",
            quantity=1.0,
            price=50000,
        )
        result = await adapter.place_order(order)
        assert result.status in [OrderStatus.FILLED, OrderStatus.PARTIAL]
        assert result.filled_quantity > 0

    @pytest.mark.asyncio
    async def test_exchange_outage_drill(self):
        adapter = ExchangeAdapter()
        adapter.apply_drill(CircuitBreakerDrillType.EXCHANGE_OUTAGE)
        assert adapter.status == ExchangeStatus.OUTAGE
        
        order = ExchangeOrder(
            athlete_id="athlete-1",
            asset="BTC",
            side="buy",
            quantity=1.0,
            price=50000,
        )
        result = await adapter.place_order(order)
        assert result.status == OrderStatus.FAILED

    @pytest.mark.asyncio
    async def test_slippage_spike_drill(self):
        adapter = ExchangeAdapter()
        original_spread = adapter.base_spread
        adapter.apply_drill(CircuitBreakerDrillType.SLIPPAGE_SPIKE, severity=0.8)
        assert adapter.base_spread > original_spread * 10

    @pytest.mark.asyncio
    async def test_latency_spike_drill(self):
        adapter = ExchangeAdapter()
        adapter.apply_drill(CircuitBreakerDrillType.LATENCY_SPIKE, severity=1.0)
        assert adapter.base_latency_ms >= 5000

    @pytest.mark.asyncio
    async def test_clear_drill(self):
        adapter = ExchangeAdapter()
        adapter.apply_drill(CircuitBreakerDrillType.EXCHANGE_OUTAGE)
        assert adapter.status == ExchangeStatus.OUTAGE
        adapter.clear_drill()
        assert adapter.status == ExchangeStatus.ONLINE
        assert adapter.base_latency_ms == 50

    def test_drill_definitions_present(self):
        assert len(DRILL_DEFINITIONS) == 8
        for drill_type in CircuitBreakerDrillType:
            assert drill_type.value in DRILL_DEFINITIONS

    @pytest.mark.asyncio
    async def test_flash_crash_drill(self):
        adapter = ExchangeAdapter()
        adapter.apply_drill(CircuitBreakerDrillType.FLASH_CRASH)
        assert adapter.base_spread >= 0.10
        assert adapter.base_latency_ms >= 2000

    @pytest.mark.asyncio
    async def test_liquidity_drop_partial_fill(self):
        adapter = ExchangeAdapter()
        adapter.apply_drill(CircuitBreakerDrillType.LIQUIDITY_DROP, severity=0.95)
        
        order = ExchangeOrder(
            athlete_id="athlete-1",
            asset="BTC",
            side="buy",
            quantity=10.0,
            price=50000,
        )
        result = await adapter.place_order(order)
        # Should get a partial fill or failure
        assert result.status in [OrderStatus.PARTIAL, OrderStatus.FAILED]
        if result.status == OrderStatus.PARTIAL:
            assert result.filled_quantity < 10.0
