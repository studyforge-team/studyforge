from pathlib import Path

import pytest

from app.llm.errors import ModelUnavailable
from app.llm.registry import Registry, load_registry


def test_repo_config_loads_and_skips_unconfirmed_models() -> None:
    reg = load_registry()  # repo-root config/models.yaml
    assert [m.id for m in reg.chain("solver")] == ["nvidia/nemotron-3-super-120b-a12b"]
    # nano and ultra are null until G10, so their roles fall through to Super
    assert [m.name for m in reg.chain("router")] == ["super"]
    assert [m.name for m in reg.chain("cross_check")] == ["super"]


def test_role_with_no_confirmed_model_is_unavailable() -> None:
    reg = load_registry()
    with pytest.raises(ModelUnavailable):
        reg.chain("vision")


def test_chain_order_follows_config(registry: Registry) -> None:
    assert [m.id for m in registry.chain("router")] == ["test/nano", "test/super"]


def test_path_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = Path(__file__).parents[4] / "config" / "models.yaml"
    path = tmp_path / "m.yaml"
    path.write_text(src.read_text().replace("timeout_s: 20", "timeout_s: 7"))
    monkeypatch.setenv("STUDYFORGE_MODELS_PATH", str(path))
    assert load_registry().roles["router"].timeout_s == 7


def test_unknown_model_in_role_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        "base_url: x\napi_key_env: K\nmodels: {super: {id: a}}\n"
        "roles:\n"
        "  router: {models: [nano], timeout_s: 1}\n"
        "  solver: {models: [super], timeout_s: 1}\n"
        "  cross_check: {models: [super], timeout_s: 1}\n"
        "  vision: {models: [super], timeout_s: 1}\n"
    )
    with pytest.raises(ValueError, match="nano"):
        load_registry(path)


def test_missing_role_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        "base_url: x\napi_key_env: K\nmodels: {super: {id: a}}\n"
        "roles: {solver: {models: [super], timeout_s: 1}}\n"
    )
    with pytest.raises(ValueError, match="router"):
        load_registry(path)
