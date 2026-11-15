"""Reproduce a worldwide snapshot; raw downloads remain local and resumable."""

import argparse
from datetime import date
from pathlib import Path

from firecal.config import get_settings
from firecal.firms import FirmsClient
from firecal.global_data import (
    acquire_global,
    build_global,
    package_global,
    package_global_regions,
    three_months_before,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--package", action="store_true", help="Add pinned data pieces to the repo")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    start = args.start or three_months_before(args.end)
    acquisition = root / "data/interim" / f"global-recent-{args.end:%Y%m%d}"
    with FirmsClient(get_settings().firms_map_key, allow_mirror=False, timeout=120) as client:
        acquire_global(client, acquisition, start, args.end)
    output = acquisition / "processed"
    meta = build_global(acquisition, output)
    if args.package:
        package_global(root, output)
        package_global_regions(root, output)
    print(f"Verified {meta['rows']:,} real global detections; version {meta['data_version']}")


if __name__ == "__main__":
    main()
