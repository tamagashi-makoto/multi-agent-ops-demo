"""Configuration management for Multi-Agent Ops Demo."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Configuration
    llm_mode: Literal["stub", "openai", "ollama"] = Field(
        default="stub",
        description="LLM backend mode: stub (mock), openai, or ollama",
    )
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama server URL"
    )
    ollama_model: str = Field(default="llama3.2", description="Ollama model name")

    # Embedding Configuration
    embedding_mode: Literal["stub", "openai"] = Field(
        default="stub", description="Embedding backend mode"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small", description="Embedding model name"
    )
    embedding_dimension: int = Field(default=1536, description="Embedding vector dimension")

    # Guardrails Configuration
    auto_approve: bool = Field(
        default=False, description="Auto-approve final output without human confirmation"
    )
    max_steps: int = Field(default=20, description="Maximum steps per agent run")
    max_parallel: int = Field(default=3, description="Maximum parallel agent executions")

    # Observability Configuration
    runs_dir: str = Field(default="runs", description="Directory for run outputs")
    trace_enabled: bool = Field(default=True, description="Enable trace logging")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    # PII Masking
    pii_patterns: str = Field(
        default=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b,"
        r"\b\d{3}-\d{4}-\d{4}\b,"
        r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",
        description="Comma-separated regex patterns for PII masking",
    )

    @property
    def runs_path(self) -> Path:
        """Get the runs directory as a Path object."""
        return Path(self.runs_dir)

    @property
    def pii_pattern_list(self) -> list[str]:
        """Get PII patterns as a list."""
        return [p.strip() for p in self.pii_patterns.split(",") if p.strip()]

    def get_llm_config(self) -> dict:
        """Get LLM configuration based on mode."""
        if self.llm_mode == "openai":
            return {
                "provider": "openai",
                "api_key": self.openai_api_key,
                "model": self.openai_model,
            }
        elif self.llm_mode == "ollama":
            return {
                "provider": "ollama",
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
            }
        else:
            return {"provider": "stub"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
