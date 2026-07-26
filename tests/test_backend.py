import os
import pytest
from unittest.mock import patch, mock_open, MagicMock, call
import subprocess

from steglib.backend import BackendBase, DockerComposeBackend, BACKENDS

def test_backend_base_init():
    base = BackendBase("pkg1", "/pkg_path", "/group_dir")
    assert base.pkg == "pkg1"
    assert base.pkg_path == "/pkg_path"
    assert base.group_dir == "/group_dir"

def test_backend_base_not_implemented():
    base = BackendBase("pkg1", "/pkg_path", "/group_dir")
    with pytest.raises(NotImplementedError):
        BackendBase.is_installed("/pkg_path")
    with pytest.raises(NotImplementedError):
        base.execute("start")

@patch("os.path.isfile")
def test_docker_backend_is_installed(mock_isfile):
    mock_isfile.return_value = True
    assert DockerComposeBackend.is_installed("/test") is True
    mock_isfile.assert_called_with("/test/docker-compose.yml")

@patch("os.path.isfile")
def test_docker_backend_is_installed_false(mock_isfile):
    mock_isfile.return_value = False
    assert DockerComposeBackend.is_installed("/test") is False

@patch("builtins.open", new_callable=mock_open, read_data="services:\n  web:\n    image: nginx:latest\n  db:\n    image: postgres:latest")
@patch("os.makedirs")
@patch("os.path.isfile", side_effect=[True, False]) # pre-start: web is cached, db is not
@patch("subprocess.run")
def test_sync_docker_cache_pre_start(mock_run, mock_isfile, mock_makedirs, mock_file):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    # Mock for checking local image (docker image inspect)
    def run_side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        if "nginx:latest" in args[0]:
            mock_ret.returncode = 1 # Not found locally, should load
        else:
            mock_ret.returncode = 0
        return mock_ret
        
    mock_run.side_effect = run_side_effect
    
    backend._sync_docker_cache("compose.yml", "pre-start")
    
    # It should have called docker load for nginx:latest (which was 'cached' but not local)
    mock_run.assert_any_call(["docker", "load", "-i", "/group_dir/.docker-cache/403554a5dfea78d1ca4a8ff5830ac2ae.tar"])
    
@patch("builtins.open", new_callable=mock_open, read_data="services:\n  web:\n    image: nginx:latest")
@patch("os.makedirs")
@patch("os.path.isfile", return_value=False)
@patch("subprocess.run")
def test_sync_docker_cache_post_start(mock_run, mock_isfile, mock_makedirs, mock_file):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend._sync_docker_cache("compose.yml", "post-start")
    mock_run.assert_any_call(["docker", "save", "-o", "/group_dir/.docker-cache/403554a5dfea78d1ca4a8ff5830ac2ae.tar", "nginx:latest"])

@patch("builtins.open", side_effect=OSError)
def test_sync_docker_cache_bad_file(mock_file):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    # Should not raise
    backend._sync_docker_cache("compose.yml", "pre-start")

@patch("builtins.open", new_callable=mock_open, read_data="invalid yaml: [")
def test_sync_docker_cache_bad_yaml(mock_file):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    # Should not raise
    backend._sync_docker_cache("compose.yml", "pre-start")

@patch("os.path.isfile", return_value=False)
@patch("os.path.getsize", return_value=0)
@patch("builtins.print")
def test_execute_missing_file(mock_print, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("start")
    mock_print.assert_called_with("[pkg1] Error: docker-compose.yml missing or empty.")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch.object(DockerComposeBackend, "_sync_docker_cache")
def test_execute_start(mock_sync, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("start")
    
    mock_run.assert_any_call(["chcon", "-R", "-t", "container_file_t", "/pkg_path"], check=False, capture_output=True)
    mock_run.assert_any_call(["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "up", "-d", "--remove-orphans"], check=True, capture_output=True, text=True)
    mock_sync.assert_has_calls([call("/pkg_path/docker-compose.yml", "pre-start"), call("/pkg_path/docker-compose.yml", "post-start")])

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch.object(DockerComposeBackend, "_sync_docker_cache")
def test_execute_start_if_created_skip(mock_sync, mock_run, mock_getsize, mock_isfile):
    # Test if_created where ps returns nothing
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_ret = MagicMock()
    mock_ret.stdout = ""
    mock_run.return_value = mock_ret
    
    backend.execute("start", if_created=True)
    
    # Should only have called ps, not up
    assert mock_run.call_count == 1
    mock_run.assert_called_with(["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "ps", "-q", "-a"], capture_output=True, text=True, check=True)
    mock_sync.assert_not_called()

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch.object(DockerComposeBackend, "_sync_docker_cache")
def test_execute_start_if_created_proceed(mock_sync, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        if "ps" in args[0]:
            mock_ret.stdout = "1234\n"
        return mock_ret
    mock_run.side_effect = side_effect
    
    backend.execute("start", if_created=True)
    mock_sync.assert_called()

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
def test_execute_stop_skip(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_ret = MagicMock()
    mock_ret.stdout = ""
    mock_run.return_value = mock_ret
    
    backend.execute("stop")
    assert mock_run.call_count == 1 # only ps

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
def test_execute_stop_proceed(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        if "ps" in args[0]:
            mock_ret.stdout = "1234\n"
        return mock_ret
    mock_run.side_effect = side_effect
    
    backend.execute("stop")
    mock_run.assert_any_call(["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "down"], check=True, capture_output=True, text=True)

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch("builtins.print")
def test_execute_status_stopped(mock_print, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    mock_ret = MagicMock()
    mock_ret.stdout = ""
    mock_run.return_value = mock_ret
    
    backend.execute("status")
    mock_print.assert_called_with("[pkg1] Status: Stopped")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch("builtins.print")
def test_execute_status_running(mock_print, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        mock_ret.stdout = "1\n2\n"
        return mock_ret
    mock_run.side_effect = side_effect
    
    backend.execute("status")
    mock_print.assert_called_with("[pkg1] Status: Running (2/2 containers)")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch("builtins.print")
def test_execute_status_degraded(mock_print, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        if "--status=running" in args[0]:
            mock_ret.stdout = "1\n"
        else:
            mock_ret.stdout = "1\n2\n"
        return mock_ret
    mock_run.side_effect = side_effect
    
    backend.execute("status")
    mock_print.assert_called_with("[pkg1] Status: Degraded (1/2 containers running)")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
def test_execute_status_verbose(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("status", verbose=True)
    mock_run.assert_called_with(["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "ps"], check=True)

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
def test_execute_logs(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("logs")
    mock_run.assert_called_with(["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "logs"], check=True)

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("builtins.print")
def test_execute_unknown(mock_print, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("bad_action")
    mock_print.assert_called_with("[pkg1] Unknown action 'bad_action'")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch("builtins.print")
def test_execute_subprocess_error(mock_print, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd=args[0], stderr="some error")
    mock_run.side_effect = side_effect
    
    backend.execute("logs")
    mock_print.assert_any_call("some error")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("subprocess.run")
@patch("builtins.print")
def test_execute_oserror(mock_print, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_run.side_effect = OSError("os error")
    backend.execute("logs")
    mock_print.assert_any_call("[pkg1] Error during logs: os error")
