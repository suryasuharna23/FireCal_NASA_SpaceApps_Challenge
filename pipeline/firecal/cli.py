"""``firecal`` command line interface (Typer)."""

import logging
from pathlib import Path

import typer

from firecal import __version__
from firecal.config import get_settings
from firecal.firms import FirmsClient, FirmsError, mask_key
from firecal.io import resolve_source

app = typer.Typer(help="FireCal data pipeline.", no_args_is_help=True)


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging.")) -> None:
    level = "DEBUG" if verbose else get_settings().log_level.upper()
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


_PENDING = "Not implemented yet - see FRD ticket {ticket}."


def _pending(ticket: str) -> None:
    typer.secho(_PENDING.format(ticket=ticket), fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the pipeline version."""
    typer.echo(__version__)


@app.command("check-key")
def check_key() -> None:
    """Verify FIRMS_MAP_KEY against the FIRMS API (T-02)."""
    settings = get_settings()
    try:
        with FirmsClient(settings.firms_map_key, settings.firms_api_base) as client:
            status = client.key_status()
    except FirmsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(
        f"MAP_KEY {mask_key(settings.firms_map_key)} OK: "
        f"{status.remaining}/{status.transaction_limit} transactions left "
        f"per {status.transaction_interval}.",
        fg=typer.colors.GREEN,
    )


@app.command()
def cells(
    land: str | None = typer.Option(
        None, help="Land polygons (path or URL). Default: Natural Earth 50m."
    ),
    ecoregions: Path | None = typer.Option(None, help="Ecoregion map with a BIOME_NAME column."),
) -> None:
    """Build the land-cell table with biome classes (T-03)."""
    from firecal.grid import build_cells, read_ecoregions, read_land

    settings = get_settings()
    paths = settings.paths.ensure()
    land_path = resolve_source(land or settings.land_url, paths.reference)
    eco_path = ecoregions or settings.ecoregions_path
    eco = read_ecoregions(eco_path) if eco_path else None
    table = build_cells(settings.grid, read_land(land_path), eco)
    table.to_parquet(paths.cells, index=False)
    typer.echo(
        f"{len(table):,} land cells at {settings.grid.res}° "
        f"({settings.grid.ncols} x {settings.grid.nrows} grid) -> {paths.cells}"
    )


@app.command()
def ingest() -> None:
    """Load FIRMS archive CSVs from data/raw into partitioned Parquet (T-04, T-05)."""
    from firecal.ingest import ingest as run_ingest

    reports = run_ingest(get_settings().paths)
    if not reports:
        typer.secho("No FIRMS CSV files found in data/raw.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    for r in reports:
        status = "OK" if r.years_match else "MISMATCH"
        typer.echo(
            f"{r.sensor}: {len(r.files)} files, {sum(r.written_rows.values()):,} rows, "
            f"{len(r.written_rows)} years, {r.duplicates:,} duplicates removed [{status}]"
        )


@app.command()
def synth(
    out: Path = typer.Option(None, help="Output folder (default: data/raw/synthetic)."),
    bbox: str = typer.Option("95,-11,141,6", help="west,south,east,north"),
    clusters: int = typer.Option(120, min=1, help="Number of fire clusters."),
    start: str = typer.Option("2000-11", help="First month (YYYY-MM)."),
    end: str | None = typer.Option(None, help="Last month (YYYY-MM), default: current."),
    seed: int = typer.Option(42),
) -> None:
    """Generate synthetic FIRMS-format CSVs for local development."""
    from firecal.synth import SynthConfig, generate

    def ym(value: str) -> tuple[int, int]:
        y, m = value.split("-")
        return int(y), int(m)

    cfg = SynthConfig(
        bbox=tuple(float(v) for v in bbox.split(",")),  # type: ignore[arg-type]
        start=ym(start),
        end=ym(end) if end else None,
        clusters=clusters,
        seed=seed,
    )
    target = out or get_settings().paths.raw / "synthetic"
    written = generate(target, cfg)
    typer.echo(f"Wrote {len(written)} files, {sum(written.values()):,} rows -> {target}")


@app.command()
def nrt(days: int = typer.Option(5, min=1, max=5, help="Days of NRT data to fetch.")) -> None:
    """Fetch near-real-time detections from the FIRMS API."""
    _pending("T-08")


@app.command()
def clean() -> None:
    """Apply confidence filters and drop static heat sources (T-06)."""
    from firecal.clean import clean as run_clean

    settings = get_settings()
    report = run_clean(settings.paths, settings.clean_config)
    for sensor, before in report.before.items():
        typer.echo(
            f"{sensor}: {before:,} -> {report.after_confidence.get(sensor, 0):,} (confidence)"
            f" -> {report.after_static.get(sensor, 0):,} (static sources)"
        )
    from firecal.schema import publish_points

    published = publish_points(settings.paths, settings.grid)
    typer.echo(f"Published {published:,} points -> {settings.paths.points}")


@app.command()
def sql(query: str = typer.Argument(..., help="SQL over the pipeline views.")) -> None:
    """Query pipeline tables with DuckDB (views: detections, points, cells, harmonized ...)."""
    from firecal.schema import connect

    typer.echo(connect(get_settings().paths).sql(query).df().to_string(index=False))


@app.command()
def grid() -> None:
    """Aggregate detections to the monthly grid per sensor."""
    _pending("T-09")


@app.command()
def harmonize() -> None:
    """Calibrate VIIRS -> MODIS-equivalent and build the merged series."""
    _pending("T-11/T-12")


@app.command()
def validate() -> None:
    """Compute validation metrics on hold-out years."""
    _pending("T-13")


if __name__ == "__main__":
    app()
