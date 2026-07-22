"""Single source of truth for the add-on version.

The version lives in `config.yaml` (that is what the Home Assistant store
reads). To stop the UI/API from drifting out of sync with it, we read it back
at runtime instead of hard-coding it in several places. `config.yaml` is copied
into the image at `/app/config.yaml` by the Dockerfile.

If the file is missing/unreadable we fall back to a constant — keep that in sync
with config.yaml as a safety net, but config.yaml remains the real source.
"""
import os
import re

_FALLBACK = "1.6.0-beta4"

# Candidate locations: the copy baked into the image, and the repo layout
# (rootfs/app/app_version.py -> ../../config.yaml) for local runs/tests.
_CANDIDATES = (
    "/app/config.yaml",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.yaml"),
)


def read_version() -> str:
    for path in _CANDIDATES:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r'\s*version:\s*"?([^"\n]+?)"?\s*$', line)
                    if m:
                        return m.group(1).strip()
        except OSError:
            continue
    return _FALLBACK


VERSION = read_version()
