from pathlib import Path

import pytest

from app.llm.errors import ModelUnavailable
from app.llm.registry import Registry, load_registry


def test_repo_config_has_confirmed_ids_and_prices() -> None:
    reg = load_registry()  # repo-root config/models.yaml, filled by G10 (19 Oct)
    assert [m.id for m in reg.chain("solver")] == ["nvidia/nemotron-3-super-120b-a12b"]
    assert [m.name for m in reg.chain("router")] == ["nano", "super"]
    assert [m.name for m in reg.chain("cross_check")] == ["ultra", "super"]
    assert [m.name for m in reg.chain("vision")] == ["vision"]
    # a null price would make SPEND_CAP_USD count the model's calls as $0
    for role in ("router", "solver", "cross_check", "vision"):
        for m in reg.chain(role):
            assert m.input_usd_per_m and m.output_usd_per_m, m.name


def test_role_with_no_confirmed_model_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = Path(__file__).parents[4] / "config" / "models.yaml"
    path = tmp_path / "m.yaml"
    path.write_text(src.read_text().replace("id: nvidia/Nemotron-3.5-Super-VL", "id: null"))
    monkeypatch.setenv("STUDYFORGE_MODELS_PATH", str(path))
    with pytest.raises(ModelUnavailable):
        load_registry().chain("vision")


def test_chain_order_follows_config(registry: Registry) -> None:
    assert [m.id for m in registry.chain("router")] == ["test/nano", "test/super"]


def test_path_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = Path(__file__).parents[4] / "config" / "models.yaml"
    path = tmp_path / "m.yaml"
    path.write_text(src.read_text().replace("timeout_s: 5", "timeout_s: 7"))
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


def test_repo_config_vision_thinks_with_room_to_finish() -> None:
    vision = load_registry().roles["vision"]
    assert vision.reasoning is True
    assert vision.max_tokens is not None and vision.max_tokens >= 12000
    assert vision.timeout_s < 90  # the browser gives the read call 90 s
