"""
G12: Exchange Adapters — governed live integration layer.

Circuit-breaker drills test an athlete's ability to handle:
- Exchange outages
- Price slippage spikes
- Order failures
- Liquidity drops
- Latency spikes
- Regulatory holds

All adapters are simulated until governance clears live execution.
"""
from __future__ import annotations

import random
import time
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExchangeStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    MAINTENANCE = "maintenance"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REJECTED = "rejected"


class CircuitBreakerDrillType(str, Enum):
    EXCHANGE_OUTAGE = "exchange_outage"
    SLIPPAGE_SPIKE = "slippage_spike"
    ORDER_FAILURE = "order_failure"
    LIQUIDITY_DROP = "liquidity_drop"
    LATENCY_SPIKE = "latency_spike"
    REGULATORY_HOLD = "regulatory_hold"
    RECONCILIATION_FAILURE = "reconciliation_failure"
    FLASH_CRASH = "flash_crash"


class ExchangeOrder(BaseModel):
    """A simulated exchange order."""

    order_id: str = ""
    athlete_id: str
    asset: str
    side: str
    order_type: OrderType = OrderType.MARKET
    quantity: float
    price: float
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    latency_ms: int = 0
    slippage: float = 0.0
    failure_reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None


class ExchangeAdapter:
    """
    Base exchange adapter — simulated.
    
    In G12, this is the governed integration point.
    Real exchange adapters (CCXT, REST APIs) plug in here
    once governance clears live execution.
    """

    def __init__(self, name: str = "simulated-exchange"):
        self.name = name
        self.status = ExchangeStatus.ONLINE
        self.base_latency_ms = 50
        self.base_spread = 0.001
        self.liquidity_factor = 1.0
        self.failure_rate = 0.0
        self.consecutive_failures = 0
        self.drill_mode: Optional[CircuitBreakerDrillType] = None

    def apply_drill(self, drill_type: CircuitBreakerDrillType, severity: float = 0.5):
        """Apply a circuit-breaker drill condition."""
        self.drill_mode = drill_type
        
        if drill_type == CircuitBreakerDrillType.EXCHANGE_OUTAGE:
            self.status = ExchangeStatus.OUTAGE
            self.failure_rate = 1.0
        elif drill_type == CircuitBreakerDrillType.SLIPPAGE_SPIKE:
            self.base_spread = 0.05 * (1 + severity)
        elif drill_type == CircuitBreakerDrillType.ORDER_FAILURE:
            self.failure_rate = 0.5 * (1 + severity)
        elif drill_type == CircuitBreakerDrillType.LIQUIDITY_DROP:
            self.liquidity_factor = max(0.01, 1.0 - severity)
        elif drill_type == CircuitBreakerDrillType.LATENCY_SPIKE:
            self.base_latency_ms = int(5000 * (1 + severity))
        elif drill_type == CircuitBreakerDrillType.FLASH_CRASH:
            self.base_spread = 0.10 * (1 + severity)
            self.base_latency_ms = int(2000 * (1 + severity))

    def clear_drill(self):
        """Reset to normal operating conditions."""
        self.drill_mode = None
        self.status = ExchangeStatus.ONLINE
        self.base_latency_ms = 50
        self.base_spread = 0.001
        self.liquidity_factor = 1.0
        self.failure_rate = 0.0
        self.consecutive_failures = 0

    async def place_order(self, order: ExchangeOrder) -> ExchangeOrder:
        """Simulate placing an order through the exchange."""
        # Check exchange status
        if self.status == ExchangeStatus.OUTAGE:
            order.status = OrderStatus.FAILED
            order.failure_reason = f"{self.name}: exchange outage"
            return order

        # Simulate latency
        jitter = random.randint(-20, 20)
        latency = max(1, self.base_latency_ms + jitter)
        time.sleep(latency / 1000)
        order.latency_ms = latency

        # Check for random failure
        if random.random() < self.failure_rate:
            self.consecutive_failures += 1
            order.status = OrderStatus.FAILED
            order.failure_reason = f"{self.name}: order failed (consecutive: {self.consecutive_failures})"
            return order

        self.consecutive_failures = 0

        # Simulate slippage
        slippage = self.base_spread * random.uniform(0.5, 1.5)
        direction = 1 if order.side == "buy" else -1
        execution_price = order.price * (1 + direction * slippage)
        order.slippage = slippage

        # Simulate fill (liquidity factor affects partial fills)
        fill_ratio = min(1.0, self.liquidity_factor * random.uniform(0.8, 1.0))
        
        if fill_ratio >= 1.0:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
        elif fill_ratio > 0:
            order.status = OrderStatus.PARTIAL
            order.filled_quantity = order.quantity * fill_ratio
        else:
            order.status = OrderStatus.FAILED
            order.failure_reason = f"{self.name}: no liquidity"

        order.avg_fill_price = execution_price
        order.filled_at = datetime.utcnow()
        return order


# ─── Circuit Breaker Drills ───────────────────────────────────────────────

DRILL_DEFINITIONS = {
    CircuitBreakerDrillType.EXCHANGE_OUTAGE: {
        "name": "Exchange Outage Drill",
        "description": "Exchange goes offline mid-trade. Athlete must detect, acknowledge, and halt trading.",
        "metrics": ["detection_time", "halt_response_time", "recovery_time"],
    },
    CircuitBreakerDrillType.SLIPPAGE_SPIKE: {
        "name": "Slippage Spike Drill",
        "description": "Spread widens 50x. Athlete must adjust order sizing or switch strategies.",
        "metrics": ["spread_detection", "strategy_adaptation", "pnl_impact"],
    },
    CircuitBreakerDrillType.ORDER_FAILURE: {
        "name": "Order Failure Cascade Drill",
        "description": "Orders start failing consecutively. Athlete must stop, diagnose, and resume.",
        "metrics": ["consecutive_failures_tolerated", "stop_loss_discipline", "recovery"],
    },
    CircuitBreakerDrillType.LIQUIDITY_DROP: {
        "name": "Liquidity Crisis Drill",
        "description": "Market liquidity drops 90%. Athlete must manage partial fills and position sizing.",
        "metrics": ["fill_ratio_management", "position_sizing", "execution_quality"],
    },
    CircuitBreakerDrillType.LATENCY_SPIKE: {
        "name": "Latency Spike Drill",
        "description": "Exchange latency spikes to 5s+. Athlete must avoid stale-quote trading.",
        "metrics": ["latency_detection", "stale_quote_avoidance", "trade_pause"],
    },
    CircuitBreakerDrillType.RECONCILIATION_FAILURE: {
        "name": "Reconciliation Failure Drill",
        "description": "Trade settlement fails. Athlete must identify, report, and reconcile.",
        "metrics": ["detection_time", "reporting_accuracy", "reconciliation_time"],
    },
    CircuitBreakerDrillType.REGULATORY_HOLD: {
        "name": "Regulatory Hold Drill",
        "description": "Regulator freezes assets. Athlete must comply, document, and communicate.",
        "metrics": ["compliance_time", "documentation_quality", "communication_clarity"],
    },
    CircuitBreakerDrillType.FLASH_CRASH: {
        "name": "Flash Crash Drill",
        "description": "Market drops 20% in 2 minutes. Athlete must not panic-sell at the bottom.",
        "metrics": ["panic_response", "circuit_breaker_compliance", "recovery_trade"],
    },
}
