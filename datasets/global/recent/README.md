# Real worldwide NASA observations

This directory contains checksum-pinned normal-Git pieces of the worldwide snapshot
for **15 August–15 November 2026**. `dataset.json` lists the exact version, row count,
archive size and every piece's checksum. Run `uv run firecal bootstrap` or the normal
one-command launcher to assemble and verify it.

Version: `fdc638723260`; **19,071,898 detections**, **231,462,795 archive bytes**, 221 pieces.

The bundle includes raw, uncalibrated MODIS and all three VIIRS platform detections,
hourly globe summaries, metadata and source receipts. S-NPP availability ends on
2 November; the other three products reach 15 November. Source dates remain explicit.

See [the worldwide data guide](../../../docs/GLOBAL-DATA.md) for meaning, limitations,
updates and reproduction. The NASA key is not included.
