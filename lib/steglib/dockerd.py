import os
import subprocess
import time
import hashlib
import logging

logger = logging.getLogger(__name__)

def _get_network_params(group_dir: str) -> list:
    """Generate unique deterministic networking parameters for this group's dockerd."""
    group_name = os.path.basename(group_dir)
    h = int(hashlib.sha256(group_name.encode()).hexdigest(), 16)
    x = (h % 254) + 1
    
    bip = f"10.{x}.0.1/24"
    pool_base = f"10.{x}.0.0/16"
    
    return [
        f"--bip={bip}",
        "--default-address-pool", f"base={pool_base},size=24"
    ]

def get_docker_env(group_dir: str) -> dict:
    """Returns the environment variables required to interact with this group's dockerd."""
    backend_dir = os.path.join(group_dir, ".backend", "dockerd")
    sock_file = os.path.join(backend_dir, "docker.sock")
    
    env = os.environ.copy()
    env["DOCKER_HOST"] = f"unix://{sock_file}"
    return env

def is_running(group_dir: str) -> bool:
    """Checks if the dockerd is currently running and responding."""
    env = get_docker_env(group_dir)
    try:
        res = subprocess.run(["docker", "info"], env=env, capture_output=True)
        return res.returncode == 0
    except FileNotFoundError:
        return False

import threading
_dockerd_lock = threading.Lock()

def ensure_running(group_dir: str, verbose: bool = False) -> dict:
    """Ensures the isolated docker daemon for this group is running.
    Returns the environment dict with DOCKER_HOST set.
    """
    with _dockerd_lock:
        backend_dir = os.path.join(group_dir, ".backend", "dockerd")
        data_root = os.path.join(backend_dir, "data")
        exec_root = os.path.join(backend_dir, "exec")
        sock_file = os.path.join(backend_dir, "docker.sock")
        pid_file = os.path.join(backend_dir, "docker.pid")
        log_file = os.path.join(backend_dir, "dockerd.log")
        
        os.makedirs(data_root, exist_ok=True)
        os.makedirs(exec_root, exist_ok=True)
        
        # Label the backend directory and its contents so dockerd_t can manage it
        subprocess.run(["chcon", "-R", "-t", "container_file_t", backend_dir], capture_output=True)
        
        env = get_docker_env(group_dir)
        
        # 1. Check if it's already responding
        res = subprocess.run(["docker", "info"], env=env, capture_output=True)
        if res.returncode == 0:
            return env
            
        # 2. If we reach here, daemon is not responding. 
        # Wipe existing state to eliminate corruption, acting like a tmpfs but on disk to prevent OOM
        import shutil
        if os.path.exists(data_root):
            try:
                # We use a subprocess to forcefully remove it in case of permission issues
                subprocess.run(["rm", "-rf", data_root], check=False)
            except Exception:
                pass
        
        os.makedirs(data_root, exist_ok=True)

        # Clean up stale pid/sock files just in case.
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 9)
            except Exception:
                pass
            try:
                os.remove(pid_file)
            except OSError:
                pass
                
        if os.path.exists(sock_file):
            try:
                os.remove(sock_file)
            except OSError:
                pass
                
        # 3. Start the isolated daemon
        if verbose:
            logger.info(f"  └── ⏳ Starting isolated Docker daemon for group: {os.path.basename(group_dir)}...")
        else:
            logger.info("  └── ⏳ Starting backend...")
        
        cmd = [
            "dockerd",
            "--data-root", data_root,
            "--exec-root", exec_root,
            "--pidfile", pid_file,
            "--host", f"unix://{sock_file}",
            "--iptables=true"
        ]
        cmd.extend(_get_network_params(group_dir))
        
        with open(log_file, "w") as f:
            f.write(f"=== Starting isolated dockerd ===\nCommand: {' '.join(cmd)}\n")
            f.flush()
            subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=os.environ, start_new_session=True)
            
        # 5. Wait for it to become responsive
        timeout = 15
        last_err = ""
        for _ in range(timeout):
            time.sleep(1)
            res = subprocess.run(["docker", "info"], env=env, capture_output=True, text=True)
            if res.returncode == 0:
                return env
            last_err = res.stderr.strip()
                
        # If we got here, it timed out
        logger.debug(f"Failed to start isolated Docker daemon. Check logs at {log_file}")
        with open(log_file, "a") as f:
            f.write(f"\n=== docker info failed after {timeout}s ===\n{last_err}\n")
        raise RuntimeError(f"Isolated Docker daemon failed to start for {group_dir}")
