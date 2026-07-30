"""Runtime backends for stegOS packages."""

import os
import shutil
import yaml
from steglib.utils import run_cmd
from steglib.exceptions import BackendError, InsufficientSpaceError, PortConflictError, NetworkNotFoundError
import subprocess
import hashlib
import logging

logger = logging.getLogger(__name__)

import json
from .constants import DOCKER_CACHE_DIR
from .dockerd import ensure_running, get_docker_env

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

    def execute(self, action: str, if_created: bool = False, verbose: bool = False, follow: bool = False) -> dict | None:
        """Executes a lifecycle action on the backend.
        
        Args:
            action: The lifecycle action (e.g., 'start', 'stop', 'status', 'logs').
            if_created: If True, only perform action if containers are already created.
            verbose: If True, enable verbose logging.
            follow: If True, stream logs indefinitely.
            
        Returns:
            A dictionary of state data if action is 'status', otherwise None.
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
    
    def _get_needed_download_size(self, compose_file: str, verbose: bool = False) -> str | None:
        """Attempts to calculate the total compressed size of all images in the compose file."""
        try:
            # 1. Parse docker-compose config
            res = run_cmd(["docker", "compose", "-f", compose_file, "config", "--format", "json"], logger, capture_output=True, text=True, check=True)
            config = json.loads(res.stdout)
            
            images = []
            for svc in config.get("services", {}).values():
                if "image" in svc:
                    images.append(svc["image"])
                    
            if not images:
                return None
            
            logger.info("  └── ⚠️  Disk space exhausted. ⏳ Calculating estimated download size (Press Ctrl+C to skip)...")
                
            total_bytes = 0
            try:
                env = ensure_running(self.group_dir, verbose)
            except Exception as e:
                logger.error(f"Failed to ensure isolated dockerd is running: {e}")
                env = dict(os.environ)
                
            env["DOCKER_CLI_EXPERIMENTAL"] = "enabled"
            
            for image in images:
                # 2. Get manifest
                m_res = run_cmd(["docker", "manifest", "inspect", "-v", image], logger, env=env, capture_output=True, text=True, check=False, quiet_fail=True)
                if m_res.returncode == 0:
                    try:
                        data = json.loads(m_res.stdout)
                        
                        def get_any_layers_size(obj):
                            if isinstance(obj, dict):
                                if "layers" in obj and isinstance(obj["layers"], list):
                                    size = sum(l.get("Size", l.get("size", 0)) for l in obj["layers"])
                                    if size > 0:
                                        return size
                                for v in obj.values():
                                    size = get_any_layers_size(v)
                                    if size > 0:
                                        return size
                            elif isinstance(obj, list):
                                for item in obj:
                                    size = get_any_layers_size(item)
                                    if size > 0:
                                        return size
                            return 0

                        total_bytes += get_any_layers_size(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse manifest JSON for {image}: {e}")
                else:
                    logger.error(f"docker manifest inspect failed for {image}: {m_res.stderr}")
            
            if total_bytes > 0:
                return f"{total_bytes / (1024 * 1024):.2f} MB"
            else:
                logger.error("total_bytes was 0 after parsing manifests")
        except Exception as e:
            logger.error(f"_get_needed_download_size exception: {e}")
        return None

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
        
        env = get_docker_env(self.group_dir)
        
        if action == "pre-start":
            for image in images:
                safe_name = hashlib.md5(image.encode()).hexdigest() + ".tar"
                cache_path = os.path.join(cache_dir, safe_name)
                if os.path.isfile(cache_path):
                    check = run_cmd(["docker", "image", "inspect", image], env=env, logger=logger, check=False, quiet_fail=True)
                    if check.returncode != 0:
                        print(f"Loading cached image '{image}' from group cache...")
                        run_cmd(["docker", "load", "-i", cache_path], env=env, logger=logger, error_msg=f"Failed to load image from cache: {cache_path}", check=True)
        elif action == "post-start":
            for image in images:
                safe_name = hashlib.md5(image.encode()).hexdigest() + ".tar"
                cache_path = os.path.join(cache_dir, safe_name)
                if not os.path.isfile(cache_path):
                    print(f"Caching image '{image}' to group cache...")
                    run_cmd(["docker", "save", "-o", cache_path, image], env=env, logger=logger, error_msg=f"Failed to save image {image} to cache", check=True)
                    
    def execute(self, action, if_created=False, verbose=False, follow=False):
        """Execute a docker-compose command (e.g. start, stop, restart, logs, down)."""
        compose_file = os.path.join(self.pkg_path, "docker-compose.yml")
        if not os.path.isfile(compose_file):
            logger.error(f"[{self.pkg}] Missing docker-compose.yml in {self.pkg_path}")
            return
        # Ensure isolated daemon is running
        try:
            env = ensure_running(self.group_dir, verbose)
        except Exception as e:
            logger.error(f"[{self.pkg}] {e}")
            return
            
        cmd = ["docker", "compose", "-p", self.pkg, "-f", compose_file]
        if action == "start":
            if if_created:
                # Check if the service has any containers; if not, skip starting
                check_cmd = cmd + ["ps", "-q", "-a"]
                try:
                    result = run_cmd(check_cmd, logger=logger, check=True, quiet_fail=True)
                    if not result.stdout.strip():
                        return
                except Exception:
                    pass
            
            self._sync_docker_cache(compose_file, "pre-start")
            
            # Pre-create external networks to prevent race conditions during concurrent start
            try:
                import yaml
                with open(compose_file, 'r') as f:
                    cdata = yaml.safe_load(f)
                
                nets = cdata.get("networks", {}) if cdata else {}
                for n_name, n_data in nets.items():
                    if isinstance(n_data, dict) and n_data.get("external"):
                        ext_name = n_data.get("name", n_name)
                        run_cmd(["docker", "network", "create", ext_name], env=env, logger=logger, check=False, quiet_fail=True)
            except Exception as e:
                logger.debug(f"[{self.pkg}] Failed to pre-create external networks: {e}")
            
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
                result = run_cmd(check_cmd, logger=logger, check=True, quiet_fail=True)
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
            if follow:
                cmd.append("-f")
        else:
            cmd.append(action)
            
        try:
            if action == "start":
                logger.info(f"[{self.pkg}] Starting package...")
                run_cmd(cmd, env=env, logger=logger, error_msg="Docker command failed.", check=True)
                self._sync_docker_cache(compose_file, "post-start")
            elif action == "stop":
                logger.info(f"[{self.pkg}] Stopping package...")
                run_cmd(cmd, env=env, logger=logger, error_msg="Docker command failed.", check=True)
            elif action == "status":
                all_ctrs = run_cmd(cmd + ["ps", "-q", "-a"], env=env, logger=logger, check=False).stdout.splitlines()
                running_ctrs = run_cmd(cmd + ["ps", "-q", "--status=running"], env=env, logger=logger, check=False).stdout.splitlines()
                total = len(all_ctrs)
                running = len(running_ctrs)
                
                if total == 0:
                    state = "stopped"
                elif running == total:
                    state = "running"
                elif running == 0:
                    state = "stopped"
                else:
                    state = "degraded"
                
                return {"state": state, "running": running, "total": total}
            else:
                # For logs, we must capture the output so the daemon sends it to the client
                if action == "logs" and follow:
                    process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in iter(process.stdout.readline, ''):
                        logger.info(line.rstrip('\n'))
                    process.wait()
                    if process.returncode != 0:
                        logger.error(f"[{self.pkg}] Logs command exited with {process.returncode}")
                else:
                    res = run_cmd(cmd, env=env, logger=logger, capture_output=True, text=True, check=True)
                    if res.stdout:
                        logger.info(res.stdout.strip())
                    if res.stderr:
                        logger.error(res.stderr.strip())
        except subprocess.CalledProcessError as e:
            details = (e.stderr or e.output or "No output.").strip()
            details_lower = details.lower()
            
            friendly_msg = None
            exc_class = BackendError
            
            if action == "start" and "no such container" in details_lower:
                logger.info(f"[{self.pkg}] Detected corrupted Docker state. Attempting recovery...")
                down_cmd = ["docker", "compose", "-p", self.pkg, "-f", compose_file, "down"]
                try:
                    run_cmd(down_cmd, env=env, logger=logger, check=False)
                except Exception:
                    pass
                try:
                    run_cmd(cmd, env=env, logger=logger, error_msg="Docker command failed after recovery attempt.", check=True)
                    self._sync_docker_cache(compose_file, "post-start")
                    return
                except subprocess.CalledProcessError as retry_e:
                    details = (retry_e.stderr or retry_e.output or "No output.").strip()
                    details_lower = details.lower()

            if "no space left on device" in details_lower:
                try:
                    usage = shutil.disk_usage(self.group_dir)
                    free_mb = usage.free / (1024 * 1024)
                    
                    import re
                    needed_match = re.search(r'needed\s+(\d+\s*[a-zA-Z]*)', details_lower)
                    if needed_match:
                        needed = needed_match.group(1)
                        friendly_msg = f"Insufficient disk space. Available on group storage: {free_mb:.2f} MB. Needed: {needed}."
                    else:
                        download_needed = self._get_needed_download_size(compose_file, verbose)
                        if download_needed:
                            friendly_msg = f"Insufficient disk space. Available on group storage: {free_mb:.2f} MB. Estimated download size: {download_needed}."
                        else:
                            friendly_msg = f"Insufficient disk space. Available on group storage: {free_mb:.2f} MB."
                except Exception:
                    friendly_msg = "Insufficient disk space on device."
                exc_class = InsufficientSpaceError
            elif "address already in use" in details_lower or "port is already allocated" in details_lower:
                friendly_msg = "A required port is already in use by another service on the host."
                exc_class = PortConflictError
            elif "network not found" in details_lower:
                friendly_msg = "A required docker network was not found."
                exc_class = NetworkNotFoundError
                
            if friendly_msg:
                err_msg = f"[{self.pkg}] Failed to {action}: {friendly_msg}"
            else:
                err_msg = f"[{self.pkg}] Failed to {action}: Docker command failed with exit code {e.returncode}."
            
            # Note: We do NOT append details to the message here. The daemon/backend should only provide the structured error.
            # The client dictates representation based on args.verbose.
            logger.debug(f"Backend error details: {details}")
            raise exc_class(err_msg, details=details)
        except Exception as e:
            err_msg = f"[{self.pkg}] Failed to {action}: {e}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

BACKENDS = {
    "docker-compose": DockerComposeBackend,
}
