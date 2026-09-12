"""
SQLAlchemy ORM models — one table per domain entity.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, JSON, Text,
    Enum as SAEnum, ForeignKey,
)
from sqlalchemy.orm import relationship

from core.database import Base
from core.models.athlete import AthleteStatus, AthleteDivision
from core.models.drill import DrillCapability, DrillDifficulty, DrillStatus
from core.models.credential import CredentialLevel, RiskLevel
from core.models.evaluation import EvaluatorType
from core.models.genetic import GeneticOperation


class AthleteORM(Base):
    __tablename__ = "athletes"

    athlete_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    division = Column(SAEnum(AthleteDivision), default=AthleteDivision.CORE, nullable=False)
    tier = Column(String, default="T3")
    generation = Column(Integer, default=0)
    status = Column(SAEnum(AthleteStatus), default=AthleteStatus.REGISTERED, nullable=False)
    credential_level = Column(Integer, default=0)

    # Adaptive genome stored as JSON
    trait_manifest = Column(JSON, default=dict)

    # Constitutional genome stored as JSON (NEVER mutated by genetic engine)
    constitutional_genome = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_training_at = Column(DateTime, nullable=True)

    # Relationships
    credentials = relationship("CredentialORM", back_populates="athlete", lazy="selectin")
    drill_runs = relationship("DrillRunORM", back_populates="athlete", lazy="selectin")


class AthleteTraitORM(Base):
    """Historical snapshot of athlete traits at a point in time."""
    __tablename__ = "athlete_traits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    generation = Column(Integer, nullable=False)
    trait_manifest = Column(JSON, nullable=False)
    fitness_score = Column(Float, default=0.0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class GymProgramORM(Base):
    __tablename__ = "gym_programs"

    program_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    required_credential_level = Column(Integer, default=0)
    drills = Column(JSON, default=list)  # list of drill_ids
    min_score_to_pass = Column(Float, default=0.7)
    created_at = Column(DateTime, default=datetime.utcnow)


class DrillORM(Base):
    __tablename__ = "drills"

    drill_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    capability = Column(SAEnum(DrillCapability), nullable=False)
    difficulty = Column(SAEnum(DrillDifficulty), nullable=False)
    description = Column(Text, default="")
    expected_steps = Column(JSON, default=list)
    timeout_seconds = Column(Integer, default=120)
    version = Column(String, default="1.0.0")


class DrillRunORM(Base):
    __tablename__ = "drill_runs"

    run_id = Column(String, primary_key=True)
    drill_id = Column(String, ForeignKey("drills.drill_id"), nullable=False, index=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    status = Column(SAEnum(DrillStatus), default=DrillStatus.PENDING)
    score = Column(Float, default=0.0)
    correctness = Column(Float, default=0.0)
    hallucination_penalty = Column(Float, default=0.0)
    instruction_adherence = Column(Float, default=0.0)
    uncertainty_reporting = Column(Float, default=0.0)
    tool_use_efficiency = Column(Float, default=0.0)
    completion_time_ms = Column(Integer, default=0)
    failure_modes = Column(JSON, default=list)
    recovery_time_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    environment_hash = Column(String, default="")
    evaluator_version = Column(String, default="1.0.0")
    load_level = Column(Integer, default=1)

    athlete = relationship("AthleteORM", back_populates="drill_runs", lazy="selectin")


class SparringSessionORM(Base):
    __tablename__ = "sparring_sessions"

    session_id = Column(String, primary_key=True)
    athlete_ids = Column(JSON, default=list)
    drill_id = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    scores = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class PerformanceMetricORM(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False)
    generation = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class FailureEventORM(Base):
    __tablename__ = "failure_events"

    event_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("drill_runs.run_id"), nullable=False, index=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    failure_type = Column(String, nullable=False)
    severity = Column(String, default="low")
    description = Column(Text, default="")
    recovered = Column(Boolean, default=False)
    recovery_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class CredentialORM(Base):
    __tablename__ = "credentials"

    credential_id = Column(String, primary_key=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    level = Column(SAEnum(CredentialLevel), default=CredentialLevel.REGISTERED)
    scope = Column(JSON, default=list)
    maximum_risk = Column(SAEnum(RiskLevel), default=RiskLevel.NONE)
    issued_by = Column(String, default="system")
    issued_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    evidence_hash = Column(String, default="")
    revocable = Column(Boolean, default=True)
    revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(String, nullable=True)

    athlete = relationship("AthleteORM", back_populates="credentials", lazy="selectin")


class CredentialEventORM(Base):
    __tablename__ = "credential_events"

    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor = Column(String, nullable=False)
    subject = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    result = Column(String, nullable=False)
    credential_id = Column(String, ForeignKey("credentials.credential_id"), nullable=False)
    policy_version = Column(String, default="1.0.0")
    environment_hash = Column(String, default="")
    provenance_hash = Column(String, default="")


class GenerationORM(Base):
    __tablename__ = "generations"

    generation_id = Column(String, primary_key=True)
    number = Column(Integer, nullable=False, unique=True)
    population_ids = Column(JSON, default=list)
    elite_ids = Column(JSON, default=list)
    diversity_score = Column(Float, default=0.0)
    avg_fitness = Column(Float, default=0.0)
    max_fitness = Column(Float, default=0.0)
    min_fitness = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class GeneticOperationORM(Base):
    __tablename__ = "genetic_operations"

    operation_id = Column(String, primary_key=True)
    generation = Column(Integer, nullable=False)
    operation = Column(SAEnum(GeneticOperation), nullable=False)
    parent_ids = Column(JSON, default=list)
    child_ids = Column(JSON, default=list)
    parameters = Column(JSON, default=dict)
    constitutional_genome_hash = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.utcnow)


class EvaluationRunORM(Base):
    __tablename__ = "evaluation_runs"

    evaluation_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("drill_runs.run_id"), nullable=False, index=True)
    athlete_id = Column(String, ForeignKey("athletes.athlete_id"), nullable=False, index=True)
    evaluator_type = Column(SAEnum(EvaluatorType), default=EvaluatorType.DETERMINISTIC)
    evaluator_id = Column(String, nullable=False)
    evaluator_version = Column(String, default="1.0.0")
    overall_score = Column(Float, default=0.0)
    objective_metrics = Column(JSON, default=dict)
    confidence_score = Column(Float, default=0.0)
    requires_human_adjudication = Column(Boolean, default=False)
    human_adjudicated = Column(Boolean, default=False)
    human_verdict = Column(Float, nullable=True)
    notes = Column(Text, default="")
    evaluated_at = Column(DateTime, default=datetime.utcnow)


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    actor = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    result = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    policy_version = Column(String, default="1.0.0")
    environment_hash = Column(String, default="")
    provenance_hash = Column(String, default="")
