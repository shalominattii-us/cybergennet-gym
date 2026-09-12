from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
import os


class Settings(BaseSettings):
    """Application settings — loaded from env / .env file."""

    app_name: str = "CyberGenetic Gym"
    environment: Literal["development", "testing", "production"] = "development"

    # Database
    database_url: str = Field(
        default="postgresql://cybergen:cybergen@localhost:5432/cybergennet",
        alias="DATABASE_URL",
    )

    # Gym defaults
    default_division: str = "CORE"
    default_tier: str = "T3"
    max_credential_level: int = 6

    # Evaluator
    evaluator_min_confidence: float = 0.7
    require_multi_evaluator: bool = False

    # Genetic engine
    population_size: int = 50
    elite_ratio: float = 0.2
    mutation_rate: float = 0.15
    crossover_rate: float = 0.7
    diversity_pressure: float = 0.15

    # Security
    secret_key: str = Field(default="dev-secret-change-in-production", alias="SECRET_KEY")
    default_deny_network: bool = True
    athlete_workspace_isolation: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
