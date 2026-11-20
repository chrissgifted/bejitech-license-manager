"""Development entry point:  python run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from bejitech.app import main  # noqa: E402

raise SystemExit(main())
