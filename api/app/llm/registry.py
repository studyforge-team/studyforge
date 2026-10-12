"""Model registry loaded from config/models.yaml (the only place model IDs live)."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from app.llm.errors import ModelUnavailable

REQUIRED_ROLES = ("router", "solver", "cross_check", "vision")
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "models.yaml"


class ModelSpec(BaseModel):
    id: str | None = None
    input_usd_per_m: float | None = None
    output_usd_per_m: float | None = None


class RoleSpec(BaseModel):
    models: list[str]
    timeout_s: float
    reasoning: bool | None = None  # None: send no thinking flag at all
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class ResolvedModel:
    name: str
    id: str
    input_usd_per_m: float | None
    output_usd_per_m: float | None


class Registry(BaseModel):
    base_url: str
    api_key_env: str
    models: dict[str, ModelSpec]
    roles: dict[str, RoleSpec]

    @model_validator(mode="after")
    def _check_refs(self) -> "Registry":
        for role in REQUIRED_ROLES:
            if role not in self.roles:
                raise ValueError(f"role '{role}' missing from model registry")
        for role, spec in self.roles.items():
            for name in spec.models:
                if name not in self.models:
                    raise ValueError(f"role '{role}' uses undefined model '{name}'")
        return self

    def chain(self, role: str) -> list[ResolvedModel]:
        """Models to try for a role, in order, skipping ones without a confirmed ID."""
        chain = [
            ResolvedModel(name, m.id, m.input_usd_per_m, m.output_usd_per_m)
            for name in self.roles[role].models
            if (m := self.models[name]).id
        ]
        if not chain:
            raise ModelUnavailable(f"no confirmed model for role '{role}'")
        return chain


def load_registry(path: Path | None = None) -> Registry:
    if path is None:
        path = Path(os.environ.get("STUDYFORGE_MODELS_PATH") or DEFAULT_PATH)
    with path.open(encoding="utf-8") as f:
        return Registry.model_validate(yaml.safe_load(f))
