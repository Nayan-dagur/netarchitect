"""Typer + Rich CLI interface for NetArchitect."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from netarchitect.exceptions import NetArchitectError
from netarchitect.exporters.explainable import format_rationale_markdown
from netarchitect.models import ArchitecturePlan
from netarchitect.planner import generate_architecture_plan
from netarchitect.presets import PRESET_IDS, list_presets, load_preset, load_spec_from_file

app = typer.Typer(
    name="netarchitect",
    help="NetArchitect: Algorithmic Network Planning & Self-Explaining Architecture Engine (CIC-307)",
    no_args_is_help=True,
)
console = Console()


def _render_plan(plan: ArchitecturePlan) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]{plan.profile_name}[/bold cyan]  |  Tier: [yellow]{plan.topology_tier}[/yellow]  |  "
            f"Endpoints: [green]{plan.total_endpoints:,}[/green]\n"
            f"IGP: [bold]{plan.routing_recommendation.igp_protocol}[/bold]  |  "
            f"EGP: [bold]{plan.routing_recommendation.egp_protocol or 'Single AS'}[/bold]  |  "
            f"Root: [magenta]{plan.vlsm_plan.root_prefix}[/magenta] -> [magenta]{plan.vlsm_plan.summary_route_cidr}[/magenta]",
            title="NetArchitect Engineering Summary",
        )
    )

    l1_table = Table(title="Layer 1 Physical Media & Optical Budget", show_lines=True)
    l1_table.add_column("Link", style="cyan")
    l1_table.add_column("Distance", justify="right")
    l1_table.add_column("Selected Media", style="green")
    l1_table.add_column("Transceiver")
    l1_table.add_column("Loss / Budget", justify="right")
    l1_table.add_column("Delay (ms)", justify="right")

    for m in plan.media_recommendations:
        dist = f"{m.distance_m / 1000:.1f} km" if m.distance_m >= 1000 else f"{m.distance_m:.0f} m"
        budget = (
            f"{m.estimated_optical_loss_db:.2f} / {m.optical_budget_db:.1f} dB"
            if m.estimated_optical_loss_db is not None and m.optical_budget_db is not None
            else (f"{m.estimated_optical_loss_db:.2f} dB (DWDM)" if m.estimated_optical_loss_db else "N/A (Copper)")
        )
        l1_table.add_row(
            m.link_name,
            dist,
            m.selected_media,
            m.transceiver,
            budget,
            f"{m.estimated_propagation_ms:.3f}",
        )
    console.print(l1_table)

    vlsm_table = Table(title="Layer 3 Bitwise VLSM Subnet Allocation", show_lines=True)
    vlsm_table.add_column("Subnet", style="cyan")
    vlsm_table.add_column("VLAN", justify="right")
    vlsm_table.add_column("CIDR", style="green")
    vlsm_table.add_column("Wildcard Mask")
    vlsm_table.add_column("Gateway")
    vlsm_table.add_column("Broadcast")
    vlsm_table.add_column("Req / Usable", justify="right")
    vlsm_table.add_column("Util %", justify="right")

    for s in plan.vlsm_plan.subnets:
        vlsm_table.add_row(
            s.name,
            str(s.vlan_id) if s.vlan_id is not None else "P2P",
            s.cidr,
            s.wildcard_mask,
            s.gateway_ip,
            s.broadcast_address,
            f"{s.requested_hosts} / {s.allocated_usable_hosts}",
            f"{s.utilization_pct:.1f}%",
        )
    console.print(vlsm_table)

    rationale_lines = "\n".join(
        f"[bold]{i}.[/bold] {entry}" for i, entry in enumerate(plan.architectural_rationale_log, start=1)
    )
    console.print(Panel(rationale_lines, title="Explainable Decision Engine Log", border_style="blue"))


@app.command()
def presets() -> None:
    """List the 3 built-in enterprise network presets."""
    loaded = list_presets()
    table = Table(title="Available Network Presets", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Tier")
    table.add_column("Root Prefix")
    table.add_column("Description")
    for pid, spec in loaded.items():
        table.add_row(pid, spec.profile_name, spec.topology_tier, spec.root_prefix, spec.description)
    console.print(table)


@app.command()
def plan(
    preset: Optional[str] = typer.Option(None, "--preset", "-p", help="Preset ID: campus_lan, metro_man, global_wan"),
    input_file: Optional[Path] = typer.Option(None, "--input", "-i", help="Path to custom JSON specification"),
    json_out: bool = typer.Option(False, "--json", help="Print full ArchitecturePlan as JSON"),
    cfg_out: Optional[Path] = typer.Option(None, "--cfg-out", help="Write combined Cisco IOS config to path"),
    rationale_out: Optional[Path] = typer.Option(None, "--rationale-out", help="Write Markdown rationale report to path"),
) -> None:
    """Run the NetArchitect planning engine on a preset or custom JSON spec."""
    if not preset and not input_file:
        console.print("[red]Error:[/red] Provide either --preset or --input.")
        raise typer.Exit(code=2)
    if preset and input_file:
        console.print("[red]Error:[/red] Provide only one of --preset or --input.")
        raise typer.Exit(code=2)

    try:
        spec = load_preset(preset) if preset else load_spec_from_file(input_file)  # type: ignore[arg-type]
        result = generate_architecture_plan(spec)
    except NetArchitectError as exc:
        console.print(f"[bold red]{type(exc).__name__}:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if cfg_out:
        cfg_out.parent.mkdir(parents=True, exist_ok=True)
        cfg_out.write_text(result.device_configs.combined_ios_cfg, encoding="utf-8")
        console.print(f"[green]Wrote Cisco IOS config:[/green] {cfg_out}")

    if rationale_out:
        rationale_out.parent.mkdir(parents=True, exist_ok=True)
        rationale_out.write_text(format_rationale_markdown(result), encoding="utf-8")
        console.print(f"[green]Wrote rationale report:[/green] {rationale_out}")

    if json_out:
        typer.echo(result.model_dump_json(indent=2))
    else:
        _render_plan(result)


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="Path to custom JSON specification to validate"),
) -> None:
    """Validate custom network parameters and physical/VLSM boundaries without exporting configs."""
    try:
        spec = load_spec_from_file(input_file)
        generate_architecture_plan(spec)
        console.print(f"[bold green]VALID:[/bold green] '{spec.profile_name}' passed all L1/L2/L3 boundary checks.")
    except NetArchitectError as exc:
        console.print(f"[bold red]INVALID ({type(exc).__name__}):[/bold red] {exc}")
        raise typer.Exit(code=1)


@app.command("export-all")
def export_all(
    out_dir: Path = typer.Option(Path("exports"), "--out-dir", "-o", help="Directory for verification exports"),
) -> None:
    """Generate Cisco IOS configs and Markdown rationale reports for all 3 preset profiles."""
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping = [
        ("campus_lan", "profile1_campus_lan"),
        ("metro_man", "profile2_metro_man"),
        ("global_wan", "profile3_global_wan"),
    ]
    for preset_id, file_stem in mapping:
        spec = load_preset(preset_id)
        result = generate_architecture_plan(spec)
        cfg_path = out_dir / f"{file_stem}.cfg"
        md_path = out_dir / f"{file_stem}_rationale.md"
        cfg_path.write_text(result.device_configs.combined_ios_cfg, encoding="utf-8")
        md_path.write_text(format_rationale_markdown(result), encoding="utf-8")
        console.print(f"[green]Exported[/green] {cfg_path} and {md_path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the FastAPI REST API server (interactive Swagger UI at /docs)."""
    import uvicorn

    uvicorn.run("netarchitect.api:app", host=host, port=port, reload=False)
