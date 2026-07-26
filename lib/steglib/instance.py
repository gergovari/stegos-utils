"""Instance model representing an installed package instance."""

import os
import json
import tempfile

from .constants import PERSISTENT_DIR, BACKEND_DIR, CONF_DIR, GLOBAL_CONF_FILENAME
from .backend import BACKENDS

class Instance:
    """Represents a stegOS package instance and its configuration."""
    
    def __init__(self, group, id):
        """Initializes the Instance.
        
        Args:
            group (str): The stegOS group name.
            id (str): The unique instance ID.
        """
        self.group = group
        self.id = id
        
    @property
    def is_valid(self):
        """Checks if this instance ID is potentially valid.
        
        Returns:
            bool: True if valid, False otherwise.
        """
        return bool(self.id and not self.id.startswith(".") and self.id != GLOBAL_CONF_FILENAME)
        
    @property
    def base_path(self):
        """Absolute path to the instance's persistent backend directory."""
        return os.path.join(PERSISTENT_DIR, self.group, self.id, BACKEND_DIR)
        
    @property
    def conf_path(self):
        """Absolute path to the instance's config file."""
        return os.path.join(PERSISTENT_DIR, self.group, self.id, CONF_DIR, f"{self.id}.json")

    @property
    def deployer(self):
        """Returns the deployer type by inspecting the backend folder.
        
        Returns:
            str: Deployer name (e.g., 'docker-compose') or None if not installed.
        """
        if not self.is_valid or not os.path.isdir(self.base_path):
            return None
        
        for name, backend_cls in BACKENDS.items():
            if backend_cls.is_installed(self.base_path):
                return name
                
        return None

    @property
    def is_installed(self):
        """Checks if the instance is currently installed.
        
        Returns:
            bool: True if installed (deployer found), False otherwise.
        """
        return self.deployer is not None

    @property
    def package_name(self):
        """Extracts the package name from an instance ID.
        
        Instance IDs are formatted as <package_name>-<uuid8>.
        
        Returns:
            str: The package name, or None if invalid.
        """
        if not self.is_valid or "-" not in self.id:
            return None
        return self.id.rsplit("-", 1)[0]
        
    def read_conf(self):
        """Reads and returns the config dict for this instance.
        
        Returns:
            dict: The parsed dict, or an empty dict if the file is missing or corrupt.
        """
        if not os.path.isfile(self.conf_path) or os.path.getsize(self.conf_path) == 0:
            return {}
        try:
            with open(self.conf_path, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
            
    def write_conf(self, data):
        """Writes config data for this instance atomically.
        
        Creates directories as needed and uses a temporary file swap to
        ensure the configuration is not left in an inconsistent state.
        
        Args:
            data (dict): The configuration data to write.
        """
        dirname = os.path.dirname(self.conf_path)
        os.makedirs(dirname, exist_ok=True)
        
        fd, tmp_path = tempfile.mkstemp(dir=dirname, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.conf_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
