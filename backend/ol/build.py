"""Build metadata is captured once per process; never infer a running version from Git."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

INFO_PATH = Path(__file__).resolve().parent.parent / "build-info.json"


def make_info(commit="unknown", dirty=False, built_at=None):
    if commit != "unknown" and not re.fullmatch(r"[a-f0-9]{40}(?:[a-f0-9]{24})?", commit):
        raise ValueError("Build commit must be a full Git SHA")
    short = commit[:12] if commit != "unknown" else "unknown"
    return dict(version=short + ("-dirty" if dirty and commit != "unknown" else ""),
                commit=commit, shortCommit=short,
                builtAt=built_at,
                dirty=bool(dirty) if commit != "unknown" else None)


def load_info(path=INFO_PATH):
    try:
        data = json.loads(Path(path).read_text())
        timestamp = data["builtAt"]
        assert datetime.fromisoformat(timestamp.replace("Z", "+00:00")).tzinfo is not None
        assert isinstance(data["dirty"], bool) or data["dirty"] is None
        return make_info(data["commit"], data["dirty"], timestamp)
    except (OSError, ValueError, KeyError, TypeError, AssertionError, AttributeError):
        return make_info()


BUILD_INFO = load_info()

if __name__ == "__main__":
    flag = os.getenv("BUILD_DIRTY", "false")
    if flag not in ("true", "false"):
        raise ValueError("BUILD_DIRTY must be true or false")
    info = make_info(os.getenv("BUILD_COMMIT", "unknown"), flag == "true",
                     datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    INFO_PATH.write_text(json.dumps(info, indent=2) + "\n")
    print("Build version:", info["version"])
