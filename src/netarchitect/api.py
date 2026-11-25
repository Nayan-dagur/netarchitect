"""FastAPI REST API for NetArchitect (with built-in OpenAPI /docs explorer)."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from netarchitect.exceptions import (
    AddressSpaceExhaustionError,
    NetArchitectError,
    ParameterValidationError,
    PhysicalDistanceViolationError,
)
from netarchitect.exporters.explainable import format_rationale_markdown
from netarchitect.models import ArchitecturePlan, NetworkSpecification
from netarchitect.planner import generate_architecture_plan
from netarchitect.presets import list_presets, load_preset

app = FastAPI(
    title="NetArchitect API",
    description="Algorithmic Network Planning & Self-Explaining Architecture Engine (CIC-307)",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "netarchitect"}


@app.get("/presets")
def get_presets() -> dict[str, NetworkSpecification]:
    return list_presets()


@app.get("/presets/{preset_id}", response_model=NetworkSpecification)
def get_preset(preset_id: str) -> NetworkSpecification:
    try:
        return load_preset(preset_id)
    except ParameterValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/plan", response_model=ArchitecturePlan)
def create_plan(spec: NetworkSpecification) -> ArchitecturePlan:
    try:
        return generate_architecture_plan(spec)
    except (PhysicalDistanceViolationError, AddressSpaceExhaustionError, ParameterValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_type": type(exc).__name__, "message": str(exc)},
        ) from exc
    except NetArchitectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/plan/{preset_id}", response_model=ArchitecturePlan)
def plan_preset(preset_id: str) -> ArchitecturePlan:
    try:
        spec = load_preset(preset_id)
        return generate_architecture_plan(spec)
    except ParameterValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/export/{preset_id}/ios", response_class=PlainTextResponse)
def export_preset_ios(preset_id: str) -> str:
    try:
        spec = load_preset(preset_id)
        return generate_architecture_plan(spec).device_configs.combined_ios_cfg
    except ParameterValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/export/{preset_id}/rationale", response_class=PlainTextResponse)
def export_preset_rationale(preset_id: str) -> str:
    try:
        spec = load_preset(preset_id)
        plan = generate_architecture_plan(spec)
        return format_rationale_markdown(plan)
    except ParameterValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
