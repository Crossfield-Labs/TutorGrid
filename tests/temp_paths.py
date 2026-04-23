from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4


@contextmanager
def workspace_temp_dir(prefix: str = "test-"):
    root = Path(__file__).resolve().parents[1] / "scratch" / "test-temp"
    path = root / f"{prefix}{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
