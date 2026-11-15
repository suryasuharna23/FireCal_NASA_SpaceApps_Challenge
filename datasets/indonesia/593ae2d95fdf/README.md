# Indonesia snapshot 593ae2d95fdf

The actual data are included here as ordinary Git binary files. No Git LFS
subscription or separate ZIP transfer is required. Repository access is still
required because this GitHub repository is private.

`dataset.json` pins each piece and each complete archive by SHA-256 and byte
length. The pieces reconstruct the original processed and sources ZIPs exactly.
Each piece is at most 1 MiB, within the repository's existing file-size checks.
The setup command assembles, verifies and extracts them automatically; do not
edit or manually unpack individual `.chunk` files.

| Archive | Bytes | Included pieces |
| --- | ---: | ---: |
| Processed snapshot | 106,674,802 | 102 |
| Original sources and receipts | 187,265,986 | 179 |

The processed snapshot contains 7,716,551 retained Indonesia detections, November
2000 through November 14, 2026. Sources include the original annual CSVs, API
responses and receipts, reference boundary, and acquisition/audit provenance.
The data source is NASA FIRMS (MODIS and VIIRS 375 m).

This is an experimental frozen snapshot. Its reproduced January-October 2026
national bias is -12.20%; only 8/27 eligible provinces meet both accuracy targets.
See the repository's bias-audit report. Newer observations belong in the separate
live workspace and must not replace these audit inputs.

Local `.env` credentials, Python environments, frontend packages, and derived
live updates are not included. GitHub's source ZIP download and a normal clone
both contain these ordinary Git data pieces.
