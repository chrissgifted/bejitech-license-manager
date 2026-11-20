from __future__ import annotations

import csv
from pathlib import Path

from bejitech.core.dto import Report


def write_csv(path: Path, report: Report) -> Path:
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel/Numbers read UTF-8
        w = csv.writer(f)
        w.writerow(report.headers)
        w.writerows(report.rows)
        if report.totals:
            w.writerow(report.totals)
    return path
