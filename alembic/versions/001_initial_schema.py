"""Initial schema — all core tables.

Revision ID: 001
Revises:
Create Date: 2026-09-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Athletes ──────────────────────────────────────────────────────────
    op.create_table(
        "athletes",
        sa.Column("athlete_id", sa.String(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("division", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), default="T3"),
        sa.Column("generation", sa.Integer(), default=0),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("credential_level", sa.Integer(), default=0),
        sa.Column("trait_manifest", JSON, default=dict),
        sa.Column("constitutional_genome", JSON, default=dict),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_training_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "athlete_traits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("trait_manifest", JSON, nullable=False),
        sa.Column("fitness_score", sa.Float(), default=0.0),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )

    # ─── Programs & Drills ────────────────────────────────────────────────
    op.create_table(
        "gym_programs",
        sa.Column("program_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("required_credential_level", sa.Integer(), default=0),
        sa.Column("drills", JSON, default=list),
        sa.Column("min_score_to_pass", sa.Float(), default=0.7),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "drills",
        sa.Column("drill_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("capability", sa.String(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("expected_steps", JSON, default=list),
        sa.Column("timeout_seconds", sa.Integer(), default=120),
        sa.Column("version", sa.String(), default="1.0.0"),
    )

    op.create_table(
        "drill_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("drill_id", sa.String(), sa.ForeignKey("drills.drill_id"), nullable=False, index=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), default=0.0),
        sa.Column("correctness", sa.Float(), default=0.0),
        sa.Column("hallucination_penalty", sa.Float(), default=0.0),
        sa.Column("instruction_adherence", sa.Float(), default=0.0),
        sa.Column("uncertainty_reporting", sa.Float(), default=0.0),
        sa.Column("tool_use_efficiency", sa.Float(), default=0.0),
        sa.Column("completion_time_ms", sa.Integer(), default=0),
        sa.Column("failure_modes", JSON, default=list),
        sa.Column("recovery_time_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("environment_hash", sa.String(), default=""),
        sa.Column("evaluator_version", sa.String(), default="1.0.0"),
        sa.Column("load_level", sa.Integer(), default=1),
    )

    # ─── Sparring ─────────────────────────────────────────────────────────
    op.create_table(
        "sparring_sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("athlete_ids", JSON, default=list),
        sa.Column("drill_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), default="PENDING"),
        sa.Column("scores", JSON, default=dict),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    # ─── Performance ──────────────────────────────────────────────────────
    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("metric_name", sa.String(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("generation", sa.Integer(), default=0),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
    )

    # ─── Failures ─────────────────────────────────────────────────────────
    op.create_table(
        "failure_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("drill_runs.run_id"), nullable=False, index=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("failure_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), default="low"),
        sa.Column("description", sa.Text(), default=""),
        sa.Column("recovered", sa.Boolean(), default=False),
        sa.Column("recovery_time_ms", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # ─── Credentials ──────────────────────────────────────────────────────
    op.create_table(
        "credentials",
        sa.Column("credential_id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("scope", JSON, default=list),
        sa.Column("maximum_risk", sa.String(), default="none"),
        sa.Column("issued_by", sa.String(), default="system"),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_hash", sa.String(), default=""),
        sa.Column("revocable", sa.Boolean(), default=True),
        sa.Column("revoked", sa.Boolean(), default=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revocation_reason", sa.String(), nullable=True),
    )

    op.create_table(
        "credential_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False, index=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("credential_id", sa.String(), sa.ForeignKey("credentials.credential_id"), nullable=False),
        sa.Column("policy_version", sa.String(), default="1.0.0"),
        sa.Column("environment_hash", sa.String(), default=""),
        sa.Column("provenance_hash", sa.String(), default=""),
    )

    # ─── Generations ─────────────────────────────────────────────────────
    op.create_table(
        "generations",
        sa.Column("generation_id", sa.String(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False, unique=True),
        sa.Column("population_ids", JSON, default=list),
        sa.Column("elite_ids", JSON, default=list),
        sa.Column("diversity_score", sa.Float(), default=0.0),
        sa.Column("avg_fitness", sa.Float(), default=0.0),
        sa.Column("max_fitness", sa.Float(), default=0.0),
        sa.Column("min_fitness", sa.Float(), default=0.0),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "genetic_operations",
        sa.Column("operation_id", sa.String(), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("parent_ids", JSON, default=list),
        sa.Column("child_ids", JSON, default=list),
        sa.Column("parameters", JSON, default=dict),
        sa.Column("constitutional_genome_hash", sa.String(), default=""),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )

    # ─── Evaluation ───────────────────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("drill_runs.run_id"), nullable=False, index=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.athlete_id"), nullable=False, index=True),
        sa.Column("evaluator_type", sa.String(), nullable=False),
        sa.Column("evaluator_id", sa.String(), nullable=False),
        sa.Column("evaluator_version", sa.String(), default="1.0.0"),
        sa.Column("overall_score", sa.Float(), default=0.0),
        sa.Column("objective_metrics", JSON, default=dict),
        sa.Column("confidence_score", sa.Float(), default=0.0),
        sa.Column("requires_human_adjudication", sa.Boolean(), default=False),
        sa.Column("human_adjudicated", sa.Boolean(), default=False),
        sa.Column("human_verdict", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), default=""),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
    )

    # ─── Audit ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("actor", sa.String(), nullable=False, index=True),
        sa.Column("subject", sa.String(), nullable=False, index=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("policy_version", sa.String(), default="1.0.0"),
        sa.Column("environment_hash", sa.String(), default=""),
        sa.Column("provenance_hash", sa.String(), default=""),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("evaluation_runs")
    op.drop_table("genetic_operations")
    op.drop_table("generations")
    op.drop_table("credential_events")
    op.drop_table("credentials")
    op.drop_table("failure_events")
    op.drop_table("performance_metrics")
    op.drop_table("sparring_sessions")
    op.drop_table("drill_runs")
    op.drop_table("drills")
    op.drop_table("gym_programs")
    op.drop_table("athlete_traits")
    op.drop_table("athletes")
