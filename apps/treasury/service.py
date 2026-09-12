"""
CyberGenetic Treasury — Simulated market operations for AI-agent stress testing.

In-memory FastAPI service providing simulation accounts, configurable market
conditions, trade execution with realistic regime-based slippage/latency/partial
fills, portfolio tracking, and per-athlete circuit breakers.

All markets are simulated. No live execution until G12.
"""

from __future__ import annotations

import logging
import math
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from core.models.treasury import (
    CircuitBreaker,
    MarketCondition,
    MarketRegime,
    SimulationAccount,
    TradeExecution,
)
from core.events import emit_audit

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("cybergennet.treasury")

# ---------------------------------------------------------------------------
# In-memory stores (MVP — no DB dependency yet)
# ---------------------------------------------------------------------------

_accounts: dict[str, SimulationAccount] = {}  # account_id -> account
_accounts_by_athlete: dict[str, str] = {}  # athlete_id -> account_id
_market_conditions: dict[str, MarketCondition] = {}
_circuit_breakers: dict[str, CircuitBreaker] = {}  # athlete_id -> breaker
_trade_history: dict[str, list[TradeExecution]] = {}  # athlete_id -> trades
_daily_pnl: dict[str, dict[str, float]] = {}  # athlete_id -> {date_str: pnl}
_active_market_condition: Optional[MarketCondition] = None
_cost_basis: dict[str, dict[str, float]] = {}  # account_id -> {asset: avg_entry_cost}

# ---------------------------------------------------------------------------
# Regime defaults (used when creating from regime enum)
# ---------------------------------------------------------------------------

REGIME_DEFAULTS: dict[MarketRegime, dict] = {
    MarketRegime.BULL: {
        "volatility": 0.02,
        "trend": 0.003,
        "spread": 0.005,
        "latency_ms": 30,
        "failure_probability": 0.01,
        "description": "Prices trend up, low volatility — favourable for longs.",
    },
    MarketRegime.BEAR: {
        "volatility": 0.04,
        "trend": -0.003,
        "spread": 0.01,
        "latency_ms": 50,
        "failure_probability": 0.05,
        "description": "Prices trend down, medium volatility — defensive posture.",
    },
    MarketRegime.SIDEWAYS: {
        "volatility": 0.015,
        "trend": 0.0,
        "spread": 0.008,
        "latency_ms": 40,
        "failure_probability": 0.01,
        "description": "No clear trend, low volatility — range-bound.",
    },
    MarketRegime.HIGH_VOLATILITY: {
        "volatility": 0.10,
        "trend": 0.0,
        "spread": 0.03,
        "latency_ms": 80,
        "failure_probability": 0.08,
        "description": "Large swings in both directions — wide spreads.",
    },
    MarketRegime.CRASH: {
        "volatility": 0.12,
        "trend": -0.02,
        "spread": 0.05,
        "latency_ms": 150,
        "failure_probability": 0.20,
        "description": "Rapid decline, high failure probability — near halt.",
    },
    MarketRegime.RECOVERY: {
        "volatility": 0.08,
        "trend": 0.02,
        "spread": 0.025,
        "latency_ms": 60,
        "failure_probability": 0.05,
        "description": "Rapid increase from crash conditions — high volatility recovery.",
    },
}

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def _seed_data() -> None:
    """Create the default BULL market condition on startup."""
    global _active_market_condition
    if _active_market_condition is not None:
        return  # already seeded

    defaults = REGIME_DEFAULTS[MarketRegime.BULL]
    condition = MarketCondition(
        name="Default Bull Market",
        regime=MarketRegime.BULL,
        volatility=defaults["volatility"],
        trend=defaults["trend"],
        spread=defaults["spread"],
        latency_ms=defaults["latency_ms"],
        failure_probability=defaults["failure_probability"],
        duration_seconds=3600,
    )
    _market_conditions[condition.condition_id] = condition
    _active_market_condition = condition

    emit_audit(
        actor="system",
        subject=f"market_condition:{condition.condition_id}",
        action="market_condition.seeded",
        result="success",
        details=(
            f'{{"name": "{condition.name}", "regime": "{condition.regime.value}", '
            f'"condition_id": "{condition.condition_id}"}}'
        ),
    )
    logger.info(
        "Seeded %s market condition %s (%s)",
        condition.regime.value, condition.name, condition.condition_id,
    )


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------


def _get_active_condition() -> MarketCondition:
    """Return the active market condition, falling back to defaults."""
    if _active_market_condition is not None:
        return _active_market_condition
    # Synthesise a neutral condition
    return MarketCondition(
        name="Fallback",
        regime=MarketRegime.SIDEWAYS,
        volatility=0.02,
        trend=0.0,
        spread=0.01,
        latency_ms=50,
        failure_probability=0.02,
    )


def _simulate_price_movement(
    current_price: float,
    condition: MarketCondition,
    time_horizon: float = 1.0,
) -> float:
    """Apply a regime-based geometric Brownian motion step to a price.

    Parameters
    ----------
    current_price : float
        The base price before movement.
    condition : MarketCondition
        The active market parameters.
    time_horizon : float
        Fractional time step (default 1.0 = one unit).

    Returns
    -------
    float
        The new price after drift + shock.
    """
    dt = time_horizon
    drift = condition.trend * dt
    shock = random.gauss(0, 1) * condition.volatility * math.sqrt(dt)
    return current_price * math.exp(drift + shock)


def _compute_slippage(
    quantity: float,
    price: float,
    condition: MarketCondition,
) -> tuple[float, float]:
    """Simulate market-impact slippage.

    Returns
    -------
    (slippage_ratio, effective_price)
        slippage_ratio is the fraction (0.0+) of price added/subtracted.
    """
    base_spread = condition.spread
    # Larger orders incur more slippage
    size_impact = min(0.10, math.log10(max(1.0, quantity)) * 0.005)
    # Random noise
    noise = random.gauss(0, condition.volatility * 0.3)
    total_slippage = base_spread + size_impact + abs(noise)
    return total_slippage, price * (1.0 + total_slippage)


def _compute_latency(condition: MarketCondition) -> int:
    """Simulate execution latency in ms with jitter."""
    base = condition.latency_ms
    jitter = random.randint(-base // 2, base // 2)
    return max(1, base + jitter)


def _compute_partial_fill(
    quantity: float,
    condition: MarketCondition,
) -> tuple[float, str]:
    """Determine fill fraction and status based on failure probability.

    Returns
    -------
    (filled_quantity, status)
    """
    roll = random.random()
    if roll < condition.failure_probability:
        # Partial fill or total failure
        if roll < condition.failure_probability * 0.3:
            return 0.0, "failed"
        fill_ratio = random.uniform(0.3, 0.8)
        return quantity * fill_ratio, "partial_fill"
    return quantity, "executed"


# ---------------------------------------------------------------------------
# Circuit breaker logic
# ---------------------------------------------------------------------------


def _get_or_create_breaker(athlete_id: str) -> CircuitBreaker:
    """Get or initialise a circuit breaker for an athlete."""
    if athlete_id not in _circuit_breakers:
        _circuit_breakers[athlete_id] = CircuitBreaker(
            athlete_id=athlete_id,
            max_daily_loss=5000.0,
            max_position_size=10000.0,
            max_leverage=1.0,
        )
    return _circuit_breakers[athlete_id]


def _check_daily_loss(athlete_id: str, breaker: CircuitBreaker) -> Optional[str]:
    """Check if the athlete has exceeded the max daily loss."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_pnl = _daily_pnl.get(athlete_id, {}).get(today, 0.0)
    if day_pnl <= -breaker.max_daily_loss:
        return f"Daily loss limit exceeded: {day_pnl:.2f} (limit {breaker.max_daily_loss:.2f})"
    return None


def _check_position_size(athlete_id: str, trade_amount: float, breaker: CircuitBreaker) -> Optional[str]:
    """Check if the trade exceeds the max position size."""
    if trade_amount > breaker.max_position_size:
        return f"Position size {trade_amount:.2f} exceeds max {breaker.max_position_size:.2f}"
    return None


def _check_cooldown(breaker: CircuitBreaker) -> Optional[str]:
    """Check if the circuit breaker is in cooldown."""
    if breaker.is_triggered and breaker.cooldown_until:
        now = datetime.now(timezone.utc)
        if now < breaker.cooldown_until:
            remaining = (breaker.cooldown_until - now).total_seconds()
            return f"Circuit breaker active — cooldown {remaining:.0f}s remaining ({breaker.trigger_reason})"
        else:
            # Cooldown expired — auto-reset
            breaker.is_triggered = False
            breaker.trigger_reason = ""
            breaker.cooldown_until = None
            breaker.triggered_at = None
    return None


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateAccountRequest(BaseModel):
    athlete_id: str = Field(..., min_length=1, max_length=128)
    initial_balance: float = Field(default=100000.0, gt=0)


class CreateMarketConditionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    regime: MarketRegime
    volatility: float = Field(default=0.02, ge=0.001, le=1.0)
    trend: float = Field(default=0.0, ge=-0.1, le=0.1)
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class ExecuteTradeRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    athlete_id: str = Field(..., min_length=1)
    asset: str = Field(..., min_length=1, max_length=64)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


class PortfolioSummary(BaseModel):
    athlete_id: str
    account_id: str
    balance: float
    initial_balance: float
    total_pnl: float
    total_pnl_percent: float
    unrealized_pnl: float
    portfolio_value: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    open_positions_count: int
    asset_holdings: dict[str, float]


class PerformanceMetrics(BaseModel):
    athlete_id: str
    account_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    average_pnl_per_trade: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    largest_win: float
    largest_loss: float
    average_win: float
    average_loss: float


class OpenPosition(BaseModel):
    asset: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _seed_data()
    yield


app = FastAPI(
    title="CyberGenetic Treasury",
    description="Simulated market operations for AI-agent stress testing.",
    version="0.1.0",
    lifespan=lifespan,
)


# =========================== ACCOUNT ENDPOINTS =============================


@app.get("/health")
def health_check():
    """Simple health probe."""
    return {
        "status": "ok",
        "accounts": len(_accounts),
        "market_conditions": len(_market_conditions),
        "active_regime": _active_market_condition.regime.value if _active_market_condition else None,
    }


@app.post("/accounts", status_code=http_status.HTTP_201_CREATED)
def create_account(body: CreateAccountRequest):
    """Create a new simulation account for an athlete."""
    athlete_id = body.athlete_id

    if athlete_id in _accounts_by_athlete:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Athlete {athlete_id} already has an account",
        )

    account = SimulationAccount(
        athlete_id=athlete_id,
        balance=body.initial_balance,
        initial_balance=body.initial_balance,
    )
    # Initialise cost-basis tracking
    _cost_basis[account.account_id] = {}

    _accounts[account.account_id] = account
    _accounts_by_athlete[athlete_id] = account.account_id
    _trade_history[athlete_id] = []
    _daily_pnl[athlete_id] = {}
    _get_or_create_breaker(athlete_id)

    emit_audit(
        actor="system",
        subject=f"sim_account:{account.account_id}",
        action="account.created",
        result="success",
        details=(
            f'{{"athlete_id": "{athlete_id}", '
            f'"initial_balance": {body.initial_balance}}}'
        ),
    )
    logger.info(
        "Created simulation account %s for athlete %s (bal=%.2f)",
        account.account_id, athlete_id, body.initial_balance,
    )
    return account


@app.get("/accounts/{athlete_id}")
def get_account(athlete_id: str):
    """Retrieve a simulation account by athlete ID."""
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No account found for athlete {athlete_id}",
        )
    account = _accounts.get(account_id)
    if not account:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found (data inconsistency)",
        )
    return account


@app.get("/accounts/{athlete_id}/balance")
def get_account_balance(athlete_id: str):
    """Get the current cash balance for an athlete."""
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No account found for athlete {athlete_id}",
        )
    account = _accounts.get(account_id)
    return {
        "athlete_id": athlete_id,
        "account_id": account_id,
        "balance": round(account.balance, 2),
        "initial_balance": round(account.initial_balance, 2),
    }


# ======================= MARKET CONDITION ENDPOINTS ========================


@app.post("/market/conditions", status_code=http_status.HTTP_201_CREATED)
def create_market_condition(body: CreateMarketConditionRequest):
    """Create a new market condition for stress testing."""
    condition = MarketCondition(
        name=body.name,
        regime=body.regime,
        volatility=body.volatility,
        trend=body.trend,
        failure_probability=body.failure_probability,
    )
    _market_conditions[condition.condition_id] = condition

    emit_audit(
        actor="system",
        subject=f"market_condition:{condition.condition_id}",
        action="market_condition.created",
        result="success",
        details=(
            f'{{"name": "{condition.name}", "regime": "{condition.regime.value}", '
            f'"volatility": {condition.volatility}, "trend": {condition.trend}}}'
        ),
    )
    logger.info(
        "Created market condition %s (%s, regime=%s)",
        condition.name, condition.condition_id, condition.regime.value,
    )
    return condition


@app.get("/market/conditions")
def list_market_conditions():
    """List all available market conditions."""
    return list(_market_conditions.values())


@app.post("/market/apply/{condition_id}")
def apply_market_condition(condition_id: str):
    """Set the active market regime for trade simulation."""
    global _active_market_condition

    condition = _market_conditions.get(condition_id)
    if not condition:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Market condition {condition_id} not found",
        )

    previous = _active_market_condition
    _active_market_condition = condition

    emit_audit(
        actor="system",
        subject=f"market_condition:{condition_id}",
        action="market_condition.applied",
        result="success",
        details=(
            f'{{"condition": "{condition.name}", "regime": "{condition.regime.value}", '
            f'"previous_regime": "{previous.regime.value if previous else "none"}"}}'
        ),
    )
    logger.info(
        "Applied market condition %s (%s) — regime %s active",
        condition.name, condition_id, condition.regime.value,
    )
    return {
        "status": "applied",
        "active_condition": condition.name,
        "regime": condition.regime.value,
    }


# ========================== TRADE ENDPOINTS ================================


@app.post("/trades", status_code=http_status.HTTP_201_CREATED)
def execute_trade(body: ExecuteTradeRequest):
    """Execute a simulated trade against the active market conditions.

    Simulates slippage, latency, and partial fills based on the current
    market regime. Enforces circuit breaker limits.
    """
    account = _accounts.get(body.account_id)
    if not account:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Account {body.account_id} not found",
        )

    athlete_id = body.athlete_id

    # ── Circuit breaker checks ──────────────────────────────────────────
    breaker = _get_or_create_breaker(athlete_id)
    trade_amount = body.quantity * body.price

    reason = _check_cooldown(breaker)
    if reason:
        raise HTTPException(status_code=http_status.HTTP_429_TOO_MANY_REQUESTS, detail=reason)

    reason = _check_daily_loss(athlete_id, breaker)
    if reason:
        _trigger_breaker(breaker, reason)
        raise HTTPException(status_code=http_status.HTTP_429_TOO_MANY_REQUESTS, detail=reason)

    reason = _check_position_size(athlete_id, trade_amount, breaker)
    if reason:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # ── Sufficient balance check ─────────────────────────────────────────
    if body.side == "buy" and trade_amount > account.balance:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient balance: {account.balance:.2f} needed "
                f"{trade_amount:.2f}"
            ),
        )

    if body.side == "sell":
        current_holding = account.asset_holdings.get(body.asset, 0.0)
        if body.quantity > current_holding:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient {body.asset} holdings: {current_holding} "
                    f"tried to sell {body.quantity}"
                ),
            )

    # ── Simulate execution ────────────────────────────────────────────────
    condition = _get_active_condition()

    # Slippage
    slippage_ratio, execution_price = _compute_slippage(
        body.quantity, body.price, condition,
    )

    # Latency
    latency_ms = _compute_latency(condition)

    # Partial fill
    filled_qty, fill_status = _compute_partial_fill(body.quantity, condition)

    # If total failure, return a failed trade
    if filled_qty <= 0:
        trade = TradeExecution(
            account_id=body.account_id,
            athlete_id=athlete_id,
            asset=body.asset,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            execution_price=execution_price,
            slippage=round(slippage_ratio, 6),
            latency_ms=latency_ms,
            status="failed",
            pnl=0.0,
        )
        _trade_history.setdefault(athlete_id, []).append(trade)
        logger.info(
            "Trade FAILED: %s %s %.4f @ %.2f — athlete=%s",
            body.side, body.asset, body.quantity, body.price, athlete_id,
        )
        return trade

    # ── Update account state ──────────────────────────────────────────────
    executed_cost = filled_qty * execution_price

    if body.side == "buy":
        account.balance -= executed_cost
        account.asset_holdings[body.asset] = (
            account.asset_holdings.get(body.asset, 0.0) + filled_qty
        )
        # Track cost basis for holdings
        old_qty = account.asset_holdings.get(body.asset, 0.0) - filled_qty
        old_cost = _cost_basis[account.account_id].get(body.asset, 0.0)
        new_avg_cost = (old_cost + executed_cost) / (old_qty + filled_qty) if (old_qty + filled_qty) > 0 else execution_price
        _cost_basis[account.account_id][body.asset] = new_avg_cost

        # Add open position entry
        account.open_positions.append({
            "asset": body.asset,
            "quantity": filled_qty,
            "avg_entry_price": execution_price,
            "current_price": execution_price,
        })

        trade_pnl = 0.0  # Realised only on close

    else:  # sell
        old_qty = account.asset_holdings.get(body.asset, 0.0)
        avg_cost = _cost_basis.get(account.account_id, {}).get(body.asset, execution_price)
        trade_pnl = (execution_price - avg_cost) * filled_qty

        account.balance += executed_cost
        account.asset_holdings[body.asset] = old_qty - filled_qty

        if account.asset_holdings[body.asset] <= 0:
            del account.asset_holdings[body.asset]
            _cost_basis.get(account.account_id, {}).pop(body.asset, None)
            # Remove closed positions
            account.open_positions = [
                p for p in account.open_positions if p.get("asset") != body.asset
            ]
        else:
            # Reduce position
            for pos in account.open_positions:
                if pos.get("asset") == body.asset:
                    pos["quantity"] -= filled_qty
                    if pos["quantity"] <= 0:
                        account.open_positions = [
                            p for p in account.open_positions
                            if p.get("asset") != body.asset or p.get("quantity", 0) > 0
                        ]
                    break

    # Update trade counts
    account.trade_count += 1
    if trade_pnl > 0:
        account.win_count += 1
    elif trade_pnl < 0:
        account.loss_count += 1

    account.total_pnl += trade_pnl
    account.last_trade_at = datetime.now(timezone.utc)

    # Track daily PnL
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _daily_pnl.setdefault(athlete_id, {})
    _daily_pnl[athlete_id][today] = _daily_pnl[athlete_id].get(today, 0.0) + trade_pnl

    # Build the trade record
    trade = TradeExecution(
        account_id=body.account_id,
        athlete_id=athlete_id,
        asset=body.asset,
        side=body.side,
        quantity=body.quantity,
        price=body.price,
        execution_price=round(execution_price, 6),
        slippage=round(slippage_ratio, 6),
        latency_ms=latency_ms,
        status=fill_status,
        pnl=round(trade_pnl, 2),
    )
    _trade_history.setdefault(athlete_id, []).append(trade)

    emit_audit(
        actor="system",
        subject=f"trade:{trade.trade_id}",
        action="trade.executed",
        result=fill_status,
        details=(
            f'{{"athlete_id": "{athlete_id}", "asset": "{body.asset}", '
            f'"side": "{body.side}", "qty": {body.quantity}, '
            f'"price": {body.price}, "exec_price": {execution_price:.2f}, '
            f'"filled": {filled_qty}, "pnl": {trade_pnl:.2f}, '
            f'"slippage": {slippage_ratio:.4f}, "latency": {latency_ms}}}'
        ),
    )

    logger.info(
        "Trade %s: %s %s %.4f @ %.2f (filled=%.4f, slippage=%.4f, lat=%dms, pnl=%.2f) — %s",
        trade.trade_id, body.side, body.asset, body.quantity, body.price,
        filled_qty, slippage_ratio, latency_ms, trade_pnl, athlete_id,
    )
    return trade


@app.get("/trades/{athlete_id}")
def get_trade_history(athlete_id: str):
    """Retrieve trade history for an athlete, most recent first."""
    trades = _trade_history.get(athlete_id, [])
    trades = sorted(trades, key=lambda t: t.executed_at, reverse=True)
    return trades


@app.get("/positions/{athlete_id}")
def get_open_positions(athlete_id: str):
    """Get all open positions for an athlete with mark-to-market pricing."""
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No account found for athlete {athlete_id}",
        )
    account = _accounts.get(account_id)
    if not account:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    condition = _get_active_condition()
    positions: list[OpenPosition] = []

    for pos in account.open_positions:
        asset = pos["asset"]
        qty = pos["quantity"]
        entry_price = pos["avg_entry_price"]

        # Simulate current price movement since entry
        current_price = _simulate_price_movement(entry_price, condition, time_horizon=random.uniform(0.1, 1.0))
        pos["current_price"] = round(current_price, 6)

        unrealized_pnl = (current_price - entry_price) * qty
        unrealized_pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0

        positions.append(OpenPosition(
            asset=asset,
            quantity=qty,
            avg_entry_price=round(entry_price, 6),
            current_price=round(current_price, 6),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_percent=round(unrealized_pnl_pct, 4),
        ))

    return positions


# ======================= PORTFOLIO ENDPOINTS ===============================


@app.get("/portfolio/{athlete_id}")
def get_portfolio_summary(athlete_id: str):
    """Get a comprehensive portfolio summary for an athlete."""
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No account found for athlete {athlete_id}",
        )
    account = _accounts.get(account_id)
    if not account:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    condition = _get_active_condition()

    # Calculate unrealized PnL from open positions
    unrealized_pnl = 0.0
    portfolio_value = account.balance
    for pos in account.open_positions:
        asset = pos["asset"]
        qty = pos["quantity"]
        entry = pos["avg_entry_price"]
        current = _simulate_price_movement(entry, condition, time_horizon=random.uniform(0.1, 0.5))
        pos["current_price"] = round(current, 6)
        position_value = current * qty
        portfolio_value += position_value
        unrealized_pnl += (current - entry) * qty

    # Calculate drawdown
    max_dd = calculate_max_drawdown(athlete_id)
    peak_value = account.initial_balance
    current_dd_pct = ((peak_value - portfolio_value) / peak_value * 100) if peak_value > 0 else 0.0

    # Win rate
    total_closed = account.win_count + account.loss_count
    win_rate = (account.win_count / total_closed * 100) if total_closed > 0 else 0.0

    return PortfolioSummary(
        athlete_id=athlete_id,
        account_id=account_id,
        balance=round(account.balance, 2),
        initial_balance=round(account.initial_balance, 2),
        total_pnl=round(account.total_pnl, 2),
        total_pnl_percent=round(
            (account.total_pnl / account.initial_balance * 100) if account.initial_balance > 0 else 0.0, 4,
        ),
        unrealized_pnl=round(unrealized_pnl, 2),
        portfolio_value=round(portfolio_value, 2),
        max_drawdown=round(max_dd, 4),
        current_drawdown=round(max(0.0, current_dd_pct), 4),
        sharpe_ratio=round(account.sharpe_ratio, 4),
        win_rate=round(win_rate, 2),
        trade_count=account.trade_count,
        open_positions_count=len(account.open_positions),
        asset_holdings=account.asset_holdings,
    )


@app.get("/portfolio/{athlete_id}/metrics")
def get_performance_metrics(athlete_id: str):
    """Get detailed performance metrics for an athlete."""
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No account found for athlete {athlete_id}",
        )
    account = _accounts.get(account_id)
    if not account:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )

    trades = _trade_history.get(athlete_id, [])
    executed_trades = [t for t in trades if t.status != "failed"]

    total_trades = len(executed_trades)
    winning_trades = [t for t in executed_trades if t.pnl > 0]
    losing_trades = [t for t in executed_trades if t.pnl < 0]
    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

    pnls = [t.pnl for t in executed_trades]
    total_pnl = sum(pnls) if pnls else 0.0
    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

    winning_pnls = [t.pnl for t in winning_trades]
    losing_pnls = [t.pnl for t in losing_trades]

    largest_win = max(winning_pnls) if winning_pnls else 0.0
    largest_loss = min(losing_pnls) if losing_pnls else 0.0
    avg_win = sum(winning_pnls) / win_count if win_count > 0 else 0.0
    avg_loss = sum(losing_pnls) / loss_count if loss_count > 0 else 0.0

    # Profit factor = gross profit / gross loss
    gross_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0.0
    gross_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 1.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    max_dd = calculate_max_drawdown(athlete_id)
    sharpe = _calculate_sharpe(pnls)

    return PerformanceMetrics(
        athlete_id=athlete_id,
        account_id=account_id,
        total_trades=total_trades,
        winning_trades=win_count,
        losing_trades=loss_count,
        win_rate=round(win_rate, 2),
        total_pnl=round(total_pnl, 2),
        average_pnl_per_trade=round(avg_pnl, 2),
        max_drawdown=round(max_dd, 4),
        sharpe_ratio=round(sharpe, 4),
        profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else None,
        largest_win=round(largest_win, 2),
        largest_loss=round(largest_loss, 2),
        average_win=round(avg_win, 2),
        average_loss=round(avg_loss, 2),
    )


# =========================== CALCULATION HELPERS ============================


def calculate_max_drawdown(athlete_id: str) -> float:
    """Calculate the maximum peak-to-trough drawdown for an athlete's account.

    Uses trade history to reconstruct the equity curve and find the worst
    peak-to-trough decline.
    """
    account_id = _accounts_by_athlete.get(athlete_id)
    if not account_id:
        return 0.0
    account = _accounts.get(account_id)
    if not account:
        return 0.0

    trades = _trade_history.get(athlete_id, [])
    executed = [t for t in trades if t.status != "failed"]

    if not executed:
        return 0.0

    # Reconstruct equity curve from trades
    equity = account.initial_balance
    equity_curve = [equity]
    for t in sorted(executed, key=lambda x: x.executed_at):
        equity += t.pnl
        equity_curve.append(equity)

    peak = equity_curve[0]
    max_dd = 0.0

    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return max_dd


def _calculate_sharpe(pnls: list[float], risk_free_rate: float = 0.02) -> float:
    """Calculate the annualised Sharpe ratio from a series of trade PnLs.

    Uses the trade PnLs as return proxy, annualises assuming ~252 trading days
    per 100 trades as a rough heuristic.
    """
    if len(pnls) < 2:
        return 0.0

    mean_return = sum(pnls) / len(pnls)
    variance = sum((r - mean_return) ** 2 for r in pnls) / (len(pnls) - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 1e-10

    # Scale: assume ~252 periods per year per ~100 trades
    scale = math.sqrt(252 * len(pnls) / 100) if len(pnls) > 0 else 1.0
    excess = mean_return - (risk_free_rate / 252)

    return (excess / std_dev) * scale if std_dev > 0 else 0.0


def _trigger_breaker(breaker: CircuitBreaker, reason: str) -> None:
    """Trigger a circuit breaker with a cooldown period."""
    breaker.is_triggered = True
    breaker.trigger_reason = reason
    breaker.triggered_at = datetime.now(timezone.utc)
    breaker.cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=5)

    logger.warning(
        "Circuit breaker triggered for %s: %s (cooldown until %s)",
        breaker.athlete_id, reason, breaker.cooldown_until.isoformat(),
    )


# ======================= CIRCUIT BREAKER ENDPOINTS ==========================


@app.get("/circuit-breaker/{athlete_id}")
def get_circuit_breaker(athlete_id: str):
    """Get the current circuit breaker state for an athlete."""
    breaker = _get_or_create_breaker(athlete_id)
    return breaker


@app.post("/circuit-breaker/{athlete_id}/check")
def check_circuit_breaker(athlete_id: str, trade_amount: float = Query(..., gt=0)):
    """Check if a trade of the given amount would be allowed by circuit breakers.

    Returns True if the trade is permitted, False if blocked.
    """
    breaker = _get_or_create_breaker(athlete_id)

    # Check cooldown
    reason = _check_cooldown(breaker)
    if reason:
        return {"allowed": False, "reason": reason}

    # Check daily loss
    reason = _check_daily_loss(athlete_id, breaker)
    if reason:
        return {"allowed": False, "reason": reason}

    # Check position size
    reason = _check_position_size(athlete_id, trade_amount, breaker)
    if reason:
        return {"allowed": False, "reason": reason}

    return {"allowed": True, "reason": ""}


@app.post("/circuit-breaker/{athlete_id}/reset")
def reset_circuit_breaker(athlete_id: str):
    """Manually reset the circuit breaker for an athlete."""
    breaker = _get_or_create_breaker(athlete_id)
    breaker.is_triggered = False
    breaker.trigger_reason = ""
    breaker.cooldown_until = None
    breaker.triggered_at = None

    emit_audit(
        actor="system",
        subject=f"circuit_breaker:{athlete_id}",
        action="circuit_breaker.reset",
        result="success",
        details=f'{{"athlete_id": "{athlete_id}"}}',
    )
    logger.info("Circuit breaker manually reset for athlete %s", athlete_id)
    return {"status": "reset", "athlete_id": athlete_id}

# ═══════════════════════════════════════════════════════════════════════════
# G12: Exchange Adapter & Circuit Breaker Drills
# ═══════════════════════════════════════════════════════════════════════════

from apps.treasury.exchange import (
    ExchangeAdapter, ExchangeOrder, ExchangeStatus, OrderType, OrderStatus,
    CircuitBreakerDrillType, DRILL_DEFINITIONS,
)

# Global exchange instance (one adapter shared across all athletes for now)
_exchange = ExchangeAdapter()


@app.get("/exchange/status")
async def get_exchange_status():
    """Get current exchange adapter status and drill mode."""
    return {
        "exchange": _exchange.name,
        "status": _exchange.status.value,
        "drill_mode": _exchange.drill_mode.value if _exchange.drill_mode else None,
        "base_latency_ms": _exchange.base_latency_ms,
        "base_spread": _exchange.base_spread,
        "liquidity_factor": _exchange.liquidity_factor,
        "failure_rate": _exchange.failure_rate,
        "consecutive_failures": _exchange.consecutive_failures,
    }


class ApplyDrillRequest(BaseModel):
    drill_type: CircuitBreakerDrillType
    severity: float = 0.5


@app.post("/exchange/drill/apply")
async def apply_exchange_drill(req: ApplyDrillRequest):
    """Apply a circuit-breaker drill to the exchange adapter."""
    _exchange.apply_drill(req.drill_type, req.severity)
    emit_audit(
        actor="system",
        subject="exchange",
        action="drill.applied",
        result="success",
        details=f"Drill: {req.drill_type.value}, Severity: {req.severity}",
    )
    return {
        "drill_applied": req.drill_type.value,
        "severity": req.severity,
        "exchange_status": _exchange.status.value,
    }


@app.post("/exchange/drill/clear")
async def clear_exchange_drill():
    """Clear the active drill and reset exchange to normal."""
    _exchange.clear_drill()
    emit_audit(
        actor="system",
        subject="exchange",
        action="drill.cleared",
        result="success",
    )
    return {"drill_cleared": True, "exchange_status": _exchange.status.value}


@app.get("/exchange/drills")
async def list_drills():
    """List all available circuit-breaker drills."""
    return [
        {
            "id": k.value,
            "name": v["name"],
            "description": v["description"],
            "metrics": v["metrics"],
        }
        for k, v in DRILL_DEFINITIONS.items()
    ]


class PlaceDrillOrderRequest(BaseModel):
    athlete_id: str
    asset: str
    side: str
    quantity: float
    price: float
    order_type: OrderType = OrderType.MARKET


@app.post("/exchange/orders", status_code=201)
async def place_exchange_order(req: PlaceDrillOrderRequest):
    """Place an order through the exchange adapter (under current drill conditions)."""
    order = ExchangeOrder(
        athlete_id=req.athlete_id,
        asset=req.asset,
        side=req.side,
        quantity=req.quantity,
        price=req.price,
        order_type=req.order_type,
    )
    result = await _exchange.place_order(order)
    
    emit_audit(
        actor=req.athlete_id,
        subject=f"order:{result.order_id}",
        action="exchange.order.placed",
        result=result.status.value,
        details=f"Asset: {req.asset}, Side: {req.side}, Qty: {req.quantity}, Drill: {_exchange.drill_mode}",
    )
    
    return result


@app.get("/exchange/orders/{order_id}")
async def get_exchange_order(order_id: str):
    """Get order details (stub — real impl would query exchange)."""
    return {"order_id": order_id, "note": "Order history available in production"}


# Register this app for G12 gate check
G12_GATE_PASSED: bool = False

@app.post("/exchange/g12-gate/pass")
async def pass_g12_gate():
    """Simulate governance clearing live execution (G12 milestone)."""
    global G12_GATE_PASSED
    G12_GATE_PASSED = True
    emit_audit(
        actor="sovereign-os",
        subject="g12-gate",
        action="g12_gate.passed",
        result="success",
        details="Governance cleared live execution — exchange adapter activated",
    )
    return {"g12_gate_passed": True}


@app.get("/exchange/g12-gate/status")
async def g12_gate_status():
    return {
        "g12_gate_passed": G12_GATE_PASSED,
        "exchange_online": _exchange.status == ExchangeStatus.ONLINE,
        "active_drill": _exchange.drill_mode.value if _exchange.drill_mode else None,
    }
