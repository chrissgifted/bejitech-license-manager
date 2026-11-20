"""Business logic must never depend on Qt, so it can be reused by a future server/mobile backend."""
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "bejitech"


def test_no_qt_outside_ui():
    offenders = []
    for pkg in ("core", "db", "security", "services", "pdf", "exports", "config"):
        for f in (SRC / pkg).rglob("*.py"):
            text = f.read_text(encoding="utf-8")
            if "PySide6" in text or "PyQt" in text:
                offenders.append(str(f.relative_to(SRC)))
    assert offenders == []
