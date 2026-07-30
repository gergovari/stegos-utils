import os
import subprocess
import pytest
from unittest.mock import patch, mock_open, call, ANY

from steglib.dockerd import ensure_running, get_docker_env, _get_network_params

def test_get_network_params():
    params = _get_network_params("/some/path/my_group")
    assert any("--bip" in p for p in params)
    assert any("--default-address-pool" in p for p in params)

def test_get_docker_env():
    env = get_docker_env("/some/path/my_group")
    assert env["DOCKER_HOST"] == "unix:///some/path/my_group/backend/dockerd/docker.sock"

@patch("steglib.dockerd.subprocess.run")
@patch("steglib.dockerd.os.makedirs")
@patch("steglib.dockerd.os.path.ismount")
def test_ensure_running_already_running(mock_ismount, mock_makedirs, mock_run):
    mock_ismount.return_value = True
    mock_run.side_effect = [
        subprocess.CompletedProcess(args=[], returncode=0, stdout=b""), # chcon
        subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")  # docker info
    ]
    env = ensure_running("/path/to/group")
    assert env["DOCKER_HOST"] == "unix:///path/to/group/backend/dockerd/docker.sock"
    mock_makedirs.assert_called()

@patch("steglib.dockerd.subprocess.run")
@patch("steglib.dockerd.subprocess.Popen")
@patch("steglib.dockerd.os.makedirs")
@patch("steglib.dockerd.os.path.ismount")
@patch("steglib.dockerd.os.path.exists")
@patch("steglib.dockerd.os.remove")
@patch("steglib.dockerd.os.kill")
@patch("steglib.dockerd.time.sleep")
@patch("builtins.open", new_callable=mock_open, read_data="1234")
def test_ensure_running_starts_daemon(mock_file, mock_sleep, mock_kill, mock_remove, mock_exists, mock_ismount, mock_makedirs, mock_popen, mock_run):
    mock_ismount.return_value = False
    
    # Exists check for pid and sock files
    mock_exists.side_effect = lambda path: path.endswith("docker.pid") or path.endswith("docker.sock")
    
    # First run is chcon, second is docker info (fails), next mount, mount, then loop docker info (succeeds)
    def run_side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[0] == "mount":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"")
        if cmd[0] == "chcon":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"")
        if cmd[0] == "docker" and cmd[1] == "info":
            # first time fail, second time success
            if run_side_effect.docker_info_called:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"")
            run_side_effect.docker_info_called = True
            return subprocess.CompletedProcess(args=cmd, returncode=1, stderr=b"error")
        return subprocess.CompletedProcess(args=cmd, returncode=0)
        
    run_side_effect.docker_info_called = False
    mock_run.side_effect = run_side_effect
    
    env = ensure_running("/path/to/group")
    assert env["DOCKER_HOST"] == "unix:///path/to/group/backend/dockerd/docker.sock"
    
    # Verify tmpfs was mounted
    mount_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "mount"]
    assert len(mount_calls) == 2
    assert "tmpfs" in mount_calls[0][0][0]
    
    # Verify stale cleanup
    mock_kill.assert_called_with(1234, 9)
    assert mock_remove.call_count == 2 # pid and sock

@patch("steglib.dockerd.subprocess.run")
@patch("steglib.dockerd.subprocess.Popen")
@patch("steglib.dockerd.os.makedirs")
@patch("steglib.dockerd.os.path.ismount")
@patch("steglib.dockerd.os.path.exists")
@patch("steglib.dockerd.time.sleep")
@patch("builtins.open", new_callable=mock_open)
def test_ensure_running_timeout(mock_file, mock_sleep, mock_exists, mock_ismount, mock_makedirs, mock_popen, mock_run):
    mock_ismount.return_value = True
    mock_exists.return_value = False
    
    def run_side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[0] == "chcon":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"")
        if cmd[0] == "docker" and cmd[1] == "info":
            return subprocess.CompletedProcess(args=cmd, returncode=1, stderr=b"error")
        return subprocess.CompletedProcess(args=cmd, returncode=0)
        
    mock_run.side_effect = run_side_effect
    
    with pytest.raises(RuntimeError, match="Isolated Docker daemon failed to start"):
        ensure_running("/path/to/group")
