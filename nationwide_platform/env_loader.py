import os
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILES = (
    ROOT / ".env.market_gelsin_api.local",
    ROOT / ".env.supabase.local",
    ROOT / ".env.firebase.local",
)


def _parse_env_lines(lines: Iterable[str]):
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        yield key, os.path.expandvars(value)


def load_local_env_files() -> None:
    for env_path in DEFAULT_ENV_FILES:
        if not env_path.exists():
            continue
        for key, value in _parse_env_lines(env_path.read_text(encoding="utf-8").splitlines()):
            os.environ.setdefault(key, value)
