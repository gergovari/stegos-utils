"""State and configuration file I/O for stegOS package instances.

Each installed package instance stores two JSON files on the persistent drive:

  ``<group>/<instance>/backend/.stegpkg-state.json``
      Deployer metadata written by stegpkg, read by stegctl at runtime.

  ``<group>/<instance>/conf/<instance>.json``
      User-facing configuration values (ports, domains, enabled integrations).
"""

import json
import os

from .constants import PERSISTENT_DIR, BACKEND_DIR, CONF_DIR, STATE_FILENAME


# ---------------------------------------------------------------------------
# State files  (written by stegpkg, read by stegctl)
# ---------------------------------------------------------------------------

def state_path(group, instance):
    """Return the absolute path to an instance's state file."""
    return os.path.join(
        PERSISTENT_DIR, group, instance, BACKEND_DIR, STATE_FILENAME
    )


def read_state(group, instance):
    """Read and return the state dict for an instance.

    Returns:
        The parsed dict, or ``None`` if the file is missing or corrupt.
    """
    path = state_path(group, instance)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def write_state(group, instance, data):
    """Write state data for an instance, creating directories as needed."""
    path = state_path(group, instance)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(path, 0o600)


# ---------------------------------------------------------------------------
# Config files  (user-facing configuration)
# ---------------------------------------------------------------------------

def conf_path(group, instance):
    """Return the absolute path to an instance's config file."""
    return os.path.join(
        PERSISTENT_DIR, group, instance, CONF_DIR, f"{instance}.json"
    )


def read_conf(group, instance):
    """Read and return the config dict for an instance.

    Returns:
        The parsed dict, or an empty dict if the file is missing or corrupt.
    """
    path = conf_path(group, instance)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def write_conf(group, instance, data):
    """Write config data for an instance, creating directories as needed."""
    path = conf_path(group, instance)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(path, 0o600)
