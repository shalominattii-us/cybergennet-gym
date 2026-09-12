"""Arena, Treasury, and SovereignOS tables.

Revision ID: 002
Revises: 001
Create Date: 2026-09-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Arena ─────────────────────────────────────────────────────────────
    op.create_table(
        "arena_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("required_credential_level", sa.Integer(), default=4),
        sa.Column("max_participants", sa.Integer(), default=16),
        sa.Column("min_participants", sa.Integer(), default=2),
        sa.Column("participant_ids", JSON, default=list),
        sa.Column("match_ids", JSON, default=list),
        sa.Column("drill_capabilities", JSON, default=list),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("results", JSON, nullable=True),
    )

    op.create_table(
        "arena_matches",
        sa.Column("match_id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), sa.ForeignKey("arena_events.event_id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("athlete_ids", JSON, default=list),
        sa.Column("drill_id", sa.String(), default=""),
        sa.Column("scores", JSON, default=dict),
        sa.Column("winner_id", sa.String(), nullable=True),
        sa.Column("round_number", sa.Integer(), default=1),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "arena_rankings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.String(), nullable=False, index=True),
        sa.Column("rank", sa.Integer(), default=0),
        sa.Column("elo_rating", sa.Float(), default=1000.0),
        sa.Column("wins", sa.Integer(), default=0),
        sa.Column("losses", sa.Integer(), default=0),
        sa.Column("draws", sa.Integer(), default=0),
        sa.Column("total_matches", sa.Integer(), default=0),
        sa.Column("win_rate", sa.Float(), default=0.0),
        sa.Column("best_event_result", sa.String(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
    )

    # ─── Treasury ──────────────────────────────────────────────────────────
    op.create_table(
        "simulation_accounts",
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), nullable=False, index=True),
        sa.Column("balance", sa.Float(), default=100000.0),
        sa.Column("initial_balance", sa.Float(), default=100000.0),
        sa.Column("asset_holdings", JSON, default=dict),
        sa.Column("open_positions", JSON, default=list),
        sa.Column("trade_count", sa.Integer(), default=0),
        sa.Column("win_count", sa.Integer(), default=0),
        sa.Column("loss_count", sa.Integer(), default=0),
        sa.Column("total_pnl", sa.Float(), default=0.0),
        sa.Column("max_drawdown", sa.Float(), default=0.0),
        sa.Column("sharpe_ratio", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_trade_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "market_conditions",
        sa.Column("condition_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("regime", sa.String(), nullable=False),
        sa.Column("volatility", sa.Float(), default=0.2),
        sa.Column("trend", sa.Float(), default=0.0),
        sa.Column("spread", sa.Float(), default=0.01),
        sa.Column("latency_ms", sa.Integer(), default=50),
        sa.Column("failure_probability", sa.Float(), default=0.0),
        sa.Column("duration_seconds", sa.Integer(), default=300),
        sa.Column("asset_classes", JSON, default=list),
    )

    op.create_table(
        "trade_executions",
        sa.Column("trade_id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), sa.ForeignKey("simulation_accounts.account_id"), nullable=False, index=True),
        sa.Column("athlete_id", sa.String(), nullable=False, index=True),
        sa.Column("asset", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("execution_price", sa.Float(), nullable=False),
        sa.Column("slippage", sa.Float(), default=0.0),
        sa.Column("latency_ms", sa.Integer(), default=0),
        sa.Column("status", sa.String(), default="executed"),
        sa.Column("pnl", sa.Float(), default=0.0),
        sa.Column("executed_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "circuit_breakers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.String(), nullable=False, index=True),
        sa.Column("is_triggered", sa.Boolean(), default=False),
        sa.Column("trigger_reason", sa.String(), default=""),
        sa.Column("max_daily_loss", sa.Float(), default=5000.0),
        sa.Column("max_position_size", sa.Float(), default=10000.0),
        sa.Column("max_leverage", sa.Float(), default=1.0),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), nullable=True),
    )

    # ─── SovereignOS ──────────────────────────────────────────────────────
    op.create_table(
        "sovereign_policies",
        sa.Column("policy_id", sa.String(), primary_key=True),
        sa.Column("domain", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), default=""),
        sa.Column("priority", sa.Integer(), default=100),
        sa.Column("policy_version", sa.String(), default="1.0.0"),
        sa.Column("issued_by", sa.String(), default="sovereign-os"),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), default=True),
    )

    op.create_table(
        "governance_gates",
        sa.Column("gate_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("policy_ids", JSON, default=list),
        sa.Column("required_approvals", sa.Integer(), default=1),
        sa.Column("auto_approve_level", sa.Integer(), default=6),
        sa.Column("audit_all", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "governance_decisions",
        sa.Column("decision_id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), nullable=False, index=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("matched_policy_id", sa.String(), default=""),
        sa.Column("requires_human", sa.Boolean(), default=False),
        sa.Column("human_approved", sa.Boolean(), default=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sovereign_ledger",
        sa.Column("entry_id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("athlete_id", sa.String(), default=""),
        sa.Column("details", JSON, default=dict),
        sa.Column("policy_version", sa.String(), default=""),
        sa.Column("provenance_hash", sa.String(), default=""),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("synced_to_sovereign", sa.Boolean(), default=False),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sovereign_ledger")
    op.drop_table("governance_decisions")
    op.drop_table("governance_gates")
    op.drop_table("sovereign_policies")
    op.drop_table("circuit_breakers")
    op.drop_table("trade_executions")
    op.drop_table("market_conditions")
    op.drop_table("simulation_accounts")
    op.drop_table("arena_rankings")
    op.drop_table("arena_matches")
    op.drop_table("arena_events")
