"""Runtime backends for stegOS packages."""

import os
import yaml
from steglib.utils import run_cmd
import hashlib
import logging

logger = logging.getLogger(__name__)

from .constants import DOCKER_CACHE_DIR

class BackendBase:
    """Abstract base class for runtime backends."""
    def __init__(self, pkg: str, pkg_path: str, group_dir: str):
        """Initializes the backend.
        
        Args:
            pkg: The package name or identifier.
            pkg_path: The absolute path to the package's backend directory.
            group_dir: The absolute path to the group's persistent directory.
        """
        self.pkg = pkg
        self.pkg_path = pkg_path
        self.group_dir = group_dir

    @classmethod
    def is_installed(cls, backend_dir: str) -> bool:
        """Checks if this backend is installed in the given directory.
        
        Args:
            backend_dir: Path to the backend directory.
            
        Returns:
            True if installed, False otherwise.
        """
        raise NotImplementedError

    def execute(self, action: str, if_created: bool = False, verbose: bool = False) -> None:
        """Executes a lifecycle action on the backend.
        
        Args:
            action: The lifecycle action (e.g., 'start', 'stop').
            if_created: If True, only perform action if containers are already created.
            verbose: If True, enable verbose logging.
        """
        raise NotImplementedError

class DockerComposeBackend(BackendBase):
    """Docker Compose runtime backend."""
    
    @classmethod
    def is_installed(cls, backend_dir: str) -> bool:
        """Checks if a docker-compose.yml file exists in the backend directory.
        
        Args:
            backend_dir: Path to the backend directory.
            
        Returns:
            True if the compose file exists, False otherwise.
        """
        return os.path.isfile(os.path.join(backend_dir, "docker-compose.yml"))
    
    def _sync_docker_cache(self, compose_file, action):
        """
        Synchronize docker images with the local group cache to allow offline starts.
        
        Args:
            compose_file (str): Path to the docker-compose.yml file.
            action (str): Either 'pre-start' (load) or 'post-start' (save).
        """
        try:
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            print(f"Warning: Failed to read {compose_file} for caching: {e}")
            return
            
        images = []
        services = compose_data.get("services", {})
        if services:
            for svc_name, svc_data in services.items():
                if isinstance(svc_data, dict) and "image" in svc_data:
                    images.append(svc_data["image"])
                
        if not images:
            return
            
        # Use the group directory for caching
        cache_dir = os.path.join(self.group_dir, DOCKER_CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        
        if action == "pre-start":
            for image in images:
                safe_name = hashlib.md5(image.encode()).hexdigest() + ".tar"
                cache_path = os.path.join(cache_dir, safe_name)
                if os.path.isfile(cache_path):
                    check = run_cmd(["docker", "image", "inspect", image], logger=logger, check=False)
                    if check.returncode != 0:
                        print(f"Loading cached image '{image}' from group cache...")
                        run_cmd(["docker", "load", "-i", cache_path], logger=logger, error_msg=f"Failed to load image from cache: {cache_path}", check=True)
        elif action == "post-start":
            for image in images:
                safe_name = hashlib.md5(image.encode()).hexdigest() + ".tar"
                cache_path = os.path.join(cache_dir, safe_name)
                if not os.path.isfile(cache_path):
                    print(f"Caching image '{image}' to group cache...")
                    run_cmd(["docker", "save", "-o", cache_path, image], logger=logger, error_msg=f"Failed to save image {image} to cache", check=True)
                    
    def execute(self, action, if_created=False, verbose=False):
        """
        Handle docker-compose specific actions for a package.
        
        Args:
            action (str): The lifecycle action to perform.
            if_created (bool): If True, skip start if no containers exist.
            verbose (bool): If True, do not capture stdout/stderr.
        """
        compose_file = os.path.join(self.pkg_path, "docker-compose.yml")
        if not os.path.isfile(compose_file) or os.path.getsize(compose_file) == 0:
            print(f"[{self.pkg}] Error: docker-compose.yml missing or empty.")
            return
        
        cmd = ["docker", "compose", "-p", self.pkg, "-f", compose_file]
        if action == "start":
            if if_created:
                # Check if the service has any containers; if not, skip starting
                check_cmd = cmd + ["ps", "-q", "-a"]
                try:
                    result = run_cmd(check_cmd, logger=logger, check=True)
                    if not result.stdout.strip():
                        return
                except Exception:
                    pass
            
            self._sync_docker_cache(compose_file, "pre-start")
            
            # Apply SELinux context so the Docker daemon can access the files
            try:
                run_cmd(["chcon", "-R", "-t", "container_file_t", self.pkg_path], logger=logger, check=False)
            except Exception:
                pass
                
            cmd.extend(["up", "-d", "--remove-orphans"])
        elif action == "stop":
            # Check if the service has any containers; if not, skip stopping
            check_cmd = cmd + ["ps", "-q", "-a"]
            try:
                result = run_cmd(check_cmd, logger=logger, check=True)
                if not result.stdout.strip():
                    # No containers exist, nothing to stop
                    return
            except Exception:
                pass # If check fails, fall through to down just in case
            
            cmd.append("down")
        elif action == "status":
            pass # Status is handled specially below
        elif action == "logs":
            cmd.append("logs")
        else:
            print(f"[{self.pkg}] Unknown action '{action}'")
            return
            
        try:
            if action == "start":
                print(f"[{self.pkg}] Starting package...")
                run_cmd(cmd, logger=logger, error_msg="Docker command failed.", check=True)
                self._sync_docker_cache(compose_file, "post-start")
            elif action == "stop":
                print(f"[{self.pkg}] Stopping package...")
                run_cmd(cmd, logger=logger, error_msg="Docker command failed.", check=True)
            elif action == "status":
                if verbose:
                    run_cmd(cmd + ["ps"], logger=logger, check=True)
                else:
                    all_ctrs = run_cmd(cmd + ["ps", "-q", "-a"], logger=logger, check=False).stdout.splitlines()
                    running_ctrs = run_cmd(cmd + ["ps", "-q", "--status=running"], logger=logger, check=False).stdout.splitlines()
                    
                    if not all_ctrs:
                        print(f"[{self.pkg}] Status: Stopped")
                    elif len(running_ctrs) == len(all_ctrs):
                        print(f"[{self.pkg}] Status: Running ({len(running_ctrs)}/{len(all_ctrs)} containers)")
                    else:
                        print(f"[{self.pkg}] Status: Degraded ({len(running_ctrs)}/{len(all_ctrs)} containers running)")
            else:
                # For logs, we let the output flow to the user
                run_cmd(cmd, logger=logger, capture_output=False, text=False, check=True)
        except Exception as e:
            print(f"[{self.pkg}] Error during {action}: {e}")

BACKENDS = {
    "docker-compose": DockerComposeBackend,
}
