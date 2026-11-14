"""Download missing 2026 and NOAA-21 data without mixing it into the baseline.

Run from the repository root. Raw API responses cover the configured bbox and
must be country-filtered before use. No credential-bearing URLs are persisted.
"""

import argparse
import logging
from datetime import date, timedelta

from firecal.acquire import download_windows, plan_windows
from firecal.config import get_settings
from firecal.firms import FirmsClient, FirmsError
from firecal.io import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default="2026-11-14", help="Inclusive UTC date")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--reuse-availability", action="store_true")
    parser.add_argument("--source", action="append", help="Run only a named source; repeatable")
    parser.add_argument("--workers", type=int, default=3, choices=range(1, 5))
    args = parser.parse_args()
    date.fromisoformat(args.end)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    root = settings.paths.interim / "api-acquisition"
    root.mkdir(parents=True, exist_ok=True)
    cached = read_json(root / "availability.json")
    # The backup rejected this key while the primary accepted it. Stay on the
    # validated primary instead of treating mirror disagreement as an invalid key.
    with FirmsClient(
        settings.firms_map_key,
        settings.firms_api_base,
        timeout=120,
        allow_mirror=False,
    ) as client:
        try:
            status = client.key_status()
            print(
                f"Quota: {status.current_transactions}/{status.transaction_limit} used", flush=True
            )
            available = (
                cached["sources"] if args.reuse_availability and cached else client.availability()
            )
            write_json(root / "availability.json", {"sources": available})
            by_source = {row["data_id"]: row for row in available}
            plan = []
            # Existing annual files already cover the other platforms through 2025.
            sources = [
                "MODIS_SP",
                "VIIRS_NOAA20_SP",
                "VIIRS_SNPP_SP",
                "VIIRS_NOAA21_SP",
                "MODIS_NRT",
                "VIIRS_NOAA20_NRT",
                "VIIRS_SNPP_NRT",
                "VIIRS_NOAA21_NRT",
            ]
            if args.source and not set(args.source).issubset(sources):
                raise ValueError("Unsupported acquisition source")
            for source in sources:
                if args.source and source not in args.source:
                    continue
                start = "2023-03-01" if source == "VIIRS_NOAA21_SP" else "2026-01-01"
                if source.endswith("_NRT"):
                    sp = by_source.get(source.replace("_NRT", "_SP"))
                    if sp:
                        start = max(
                            start,
                            (date.fromisoformat(sp["max_date"]) + timedelta(days=1)).isoformat(),
                        )
                jobs = plan_windows(source, start, args.end, available)
                plan.append(
                    {
                        "source": source,
                        "requested_start": start,
                        "requested_end": args.end,
                        "windows": len(jobs),
                        "available": by_source.get(source),
                    }
                )
            write_json(root / "plan.json", {"bbox": list(settings.bbox), "sources": plan})
            print("Planned requests:", sum(item["windows"] for item in plan), flush=True)
            for item in plan:
                print(item, flush=True)
            if args.plan_only:
                return
            summaries = []
            for item in plan:
                source = item["source"]
                jobs = plan_windows(source, item["requested_start"], args.end, available)
                result = download_windows(
                    client,
                    jobs,
                    settings.bbox,
                    root / "responses" / source,
                    workers=args.workers,
                )
                summaries.append(
                    {
                        "source": source,
                        "complete": result["complete"],
                        "windows": len(jobs),
                        "rows": result["rows"],
                    }
                )
                write_json(root / "progress.json", {"sources": summaries})
            write_json(root / "progress.json", {"complete": True, "sources": summaries})
            print("All requested API responses downloaded. Country filtering is still required.")
        except (FirmsError, ValueError) as exc:
            # The client removes credentials from provider errors. Defensive redaction also
            # covers errors from parsing an unexpected provider payload.
            message = str(exc).replace(settings.firms_map_key, "[REDACTED]")
            write_json(root / "last_error.json", {"error": type(exc).__name__, "message": message})
            print(
                f"Acquisition stopped: {message}. Existing checkpoints are preserved.", flush=True
            )
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
