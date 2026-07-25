"""Shared constants and path conventions for stegOS.

Centralizes all magic strings, directory names, and filesystem paths
so they are defined in exactly one place across the entire toolchain.
"""

import os

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
VERSION = "0.1"

# ---------------------------------------------------------------------------
# Root filesystem layout
# ---------------------------------------------------------------------------
STEGOS_ROOT = os.environ.get("STEGOS_ROOT", "/stegos")
PERSISTENT_DIR = os.path.join(STEGOS_ROOT, "persistent")
REPOS_DIR = os.path.join(STEGOS_ROOT, "repos")

# ---------------------------------------------------------------------------
# Per-instance directory names (relative to <group>/<instance>/)
# ---------------------------------------------------------------------------
BACKEND_DIR = "backend"
CONF_DIR = "conf"

# ---------------------------------------------------------------------------
# Well-known filenames
# ---------------------------------------------------------------------------
STATE_FILENAME = ".stegpkg-state.json"
GLOBAL_CONF_FILENAME = "global.json"

# ---------------------------------------------------------------------------
# Docker integration
# ---------------------------------------------------------------------------
DOCKER_CACHE_DIR = ".docker-cache"

# ---------------------------------------------------------------------------
# Group initialization
# ---------------------------------------------------------------------------
LABEL_PREFIX = "stegos"
TARGET_FOLDERS = ["repos", "persistent"]
