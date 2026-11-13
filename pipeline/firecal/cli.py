"""``firecal`` command line interface (Typer)."""

import typer

from firecal import __version__
from firecal.config import get_settings
from firecal.firms import FirmsClient, FirmsError, mask_key

app = typer.Typer(help="FireCal data pipeline.", no_args_is_help=True)

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
def ingest() -> None:
    """Load FIRMS MODIS/VIIRS archive CSVs from data/raw into Parquet."""
    _pending("T-04/T-05")


@app.command()
def nrt(days: int = typer.Option(5, min=1, max=5, help="Days of NRT data to fetch.")) -> None:
    """Fetch near-real-time detections from the FIRMS API."""
    _pending("T-08")


@app.command()
def clean() -> None:
    """Apply confidence filters and drop static heat sources."""
    _pending("T-06")


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
