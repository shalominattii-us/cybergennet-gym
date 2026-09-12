"""
Treasury models — simulation-first, credential-gated financial operations.

No live execution until G12. All markets are simulated.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    CRASH = "crash"
    RECOVERY = "recovery"


class AssetClass(str, Enum):
    EQUITY = "equity"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"
    DERIVATIVE = "derivative"
    SYNTHETIC = "synthetic"


class SimulationAccount(BaseModel):
    """A simulated treasury account for an athlete."""

    account_id: str = Field(default_factory=lambda: f"sim-{uuid.uuid4().hex[:8]}")
    athlete_id: str
    balance: float = 100000.0  # starting capital
    initial_balance: float = 100000.0
    asset_holdings: dict[str, float] = Field(default_factory=dict)
    asset_holdings_cost: dict[str, float] = Field(default_factory=dict)
    open_positions: list[dict] = Field(default_factory=list)
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_trade_at: Optional[datetime] = None


class MarketCondition(BaseModel):
    """A simulated market condition for stress testing."""

    condition_id: str = Field(default_factory=lambda: f"mkt-{uuid.uuid4().hex[:8]}")
    name: str
    regime: MarketRegime
    volatility: float = 0.2
    trend: float = 0.0  # -1 to 1
    spread: float = 0.01
    latency_ms: int = 50
    failure_probability: float = 0.0
    duration_seconds: int = 300
    asset_classes: list[AssetClass] = Field(default_factory=lambda: [AssetClass.EQUITY])


class TradeExecution(BaseModel):
    """A simulated trade execution."""

    trade_id: str = Field(default_factory=lambda: f"trade-{uuid.uuid4().hex[:8]}")
    account_id: str
    athlete_id: str
    asset: str
    side: str  # buy / sell
    quantity: float
    price: float
    execution_price: float
    slippage: float = 0.0
    latency_ms: int = 0
    status: str = "executed"
    pnl: float = 0.0
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class CircuitBreaker(BaseModel):
    """Circuit breaker state for an athlete."""

    athlete_id: str
    is_triggered: bool = False
    trigger_reason: str = ""
    max_daily_loss: float = 5000.0
    max_position_size: float = 10000.0
    max_leverage: float = 1.0
    cooldown_until: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
