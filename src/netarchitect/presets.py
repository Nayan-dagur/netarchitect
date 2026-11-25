"""Preset and custom JSON loader for NetArchitect."""

import json
from pathlib import Path
from netarchitect.exceptions import ParameterValidationError
from netarchitect.models import NetworkSpecification

PRESET_IDS = ("campus_lan", "metro_man", "global_wan")


def _presets_dir() -> Path:
    # Locate repo-root presets/ directory relative to package src/netarchitect/presets.py
    candidate = Path(__file__).resolve().parents[2] / "presets"
    if candidate.is_dir():
        return candidate
    cwd_candidate = Path.cwd() / "presets"
    if cwd_candidate.is_dir():
        return cwd_candidate
    raise FileNotFoundError("Could not locate 'presets/' directory.")


def list_presets() -> dict[str, NetworkSpecification]:
    """Load and validate all built-in preset profiles."""
    result: dict[str, NetworkSpecification] = {}
    for preset_id in PRESET_IDS:
        result[preset_id] = load_preset(preset_id)
    return result


def load_preset(preset_id: str) -> NetworkSpecification:
    """Load a single preset profile by ID (campus_lan, metro_man, global_wan)."""
    normalized = preset_id.strip().lower().replace("-", "_")
    if normalized not in PRESET_IDS:
        raise ParameterValidationError(
            f"Unknown preset '{preset_id}'. Valid presets: {', '.join(PRESET_IDS)}."
        )
    path = _presets_dir() / f"{normalized}.json"
    return load_spec_from_file(path)


def load_spec_from_file(path: str | Path) -> NetworkSpecification:
    """Load and validate a NetworkSpecification from a JSON file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise ParameterValidationError(f"Input specification file not found: {file_path}")
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        return NetworkSpecification.model_validate(raw)
    except Exception as exc:
        raise ParameterValidationError(f"Failed to parse specification '{file_path}': {exc}") from exc
