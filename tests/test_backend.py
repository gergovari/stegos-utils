import os
import pytest
from unittest.mock import patch, mock_open, MagicMock, call
import subprocess

from steglib.backend import BackendBase, DockerComposeBackend, BACKENDS
from unittest.mock import Mock
import steglib.backend
steglib.backend.ensure_running = Mock(return_value={"DOCKER_HOST": "unix://fake"})
steglib.backend.get_docker_env = Mock(return_value={"DOCKER_HOST": "unix://fake"})

from steglib.exceptions import BackendError, InsufficientSpaceError, PortConflictError, NetworkNotFoundError

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
@patch("steglib.backend.run_cmd")
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
    assert any(call[0][0] == ["docker", "load", "-i", "/group_dir/.docker-cache/403554a5dfea78d1ca4a8ff5830ac2ae.tar"] for call in mock_run.call_args_list)
    
@patch("builtins.open", new_callable=mock_open, read_data="services:\n  web:\n    image: nginx:latest")
@patch("os.makedirs")
@patch("os.path.isfile", return_value=False)
@patch("steglib.backend.run_cmd")
def test_sync_docker_cache_post_start(mock_run, mock_isfile, mock_makedirs, mock_file):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend._sync_docker_cache("compose.yml", "post-start")
    assert any(call[0][0] == ["docker", "save", "-o", "/group_dir/.docker-cache/403554a5dfea78d1ca4a8ff5830ac2ae.tar", "nginx:latest"] for call in mock_run.call_args_list)

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
@patch("steglib.backend.logger.error")
def test_execute_missing_file(mock_error, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("start")
    mock_error.assert_called_with("[pkg1] Missing docker-compose.yml in /pkg_path")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
@patch.object(DockerComposeBackend, "_sync_docker_cache")
def test_execute_start(mock_sync, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("start")
    
    assert any(call[0][0] == ["chcon", "-R", "-t", "container_file_t", "/pkg_path"] for call in mock_run.call_args_list)
    assert any(call[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "up", "-d", "--remove-orphans"] for call in mock_run.call_args_list)
    mock_sync.assert_has_calls([call("/pkg_path/docker-compose.yml", "pre-start"), call("/pkg_path/docker-compose.yml", "post-start")])

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
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
    assert mock_run.call_args[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "ps", "-q", "-a"]
    mock_sync.assert_not_called()

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
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
@patch("steglib.backend.run_cmd")
def test_execute_stop_skip(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_ret = MagicMock()
    mock_ret.stdout = ""
    mock_run.return_value = mock_ret
    
    backend.execute("stop")
    assert mock_run.call_count == 1 # only ps

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
def test_execute_stop_proceed(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        if "ps" in args[0]:
            mock_ret.stdout = "1234\n"
        return mock_ret
    mock_run.side_effect = side_effect
    
    backend.execute("stop")
    assert any(call[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "down"] for call in mock_run.call_args_list)

@patch("os.path.isfile", return_value=True)
@patch("steglib.backend.run_cmd")
def test_execute_status_stopped(mock_run, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    mock_ret = MagicMock()
    mock_ret.stdout = ""
    mock_run.return_value = mock_ret
    
    res = backend.execute("status")
    assert res == {"state": "stopped", "running": 0, "total": 0}

@patch("os.path.isfile", return_value=True)
@patch("steglib.backend.run_cmd")
def test_execute_status_running(mock_run, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        mock_ret = MagicMock()
        mock_ret.stdout = "c1\nc2"
        return mock_ret
    mock_run.side_effect = side_effect
    
    res = backend.execute("status")
    assert res == {"state": "running", "running": 2, "total": 2}

@patch("os.path.isfile", return_value=True)
@patch("steglib.backend.run_cmd")
def test_execute_logs(mock_run, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("logs")
    assert mock_run.call_args[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "logs"]

@patch("os.path.isfile", return_value=True)
@patch("subprocess.Popen")
@patch("steglib.backend.logger.info")
def test_execute_logs_follow(mock_info, mock_popen, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_process = MagicMock()
    mock_process.stdout.readline.side_effect = ["log1\n", "log2\n", ""]
    mock_process.returncode = 0
    mock_popen.return_value = mock_process
    
    backend.execute("logs", follow=True)
    assert mock_popen.call_args[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "logs", "-f"]
    mock_info.assert_any_call("log1")
    mock_info.assert_any_call("log2")

@patch("os.path.isfile", return_value=True)
@patch("steglib.backend.run_cmd")
def test_execute_unknown(mock_run, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    backend.execute("bad_action")
    assert mock_run.call_args[0][0] == ["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose.yml", "bad_action"]

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
@patch("steglib.backend.logger.debug")
@patch("steglib.backend.logger.info")
def test_execute_subprocess_error(mock_info, mock_debug, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd=args[0], stderr="some error")
    mock_run.side_effect = side_effect
    
    with pytest.raises(BackendError):
        backend.execute("logs")
    assert mock_debug.called

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
@patch("shutil.disk_usage")
def test_execute_no_space_error(mock_disk_usage, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd=args[0], stderr="no space left on device")
    mock_run.side_effect = side_effect
    
    mock_usage = MagicMock()
    mock_usage.free = 1024 * 1024 * 50
    mock_disk_usage.return_value = mock_usage
    
    with pytest.raises(InsufficientSpaceError):
        backend.execute("logs")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
def test_execute_port_conflict_error(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd=args[0], stderr="address already in use")
    mock_run.side_effect = side_effect
    
    with pytest.raises(PortConflictError):
        backend.execute("logs")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
def test_execute_network_not_found_error(mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    
    def side_effect(*args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd=args[0], stderr="network not found")
    mock_run.side_effect = side_effect
    
    with pytest.raises(NetworkNotFoundError):
        backend.execute("logs")

@patch("os.path.isfile", return_value=True)
@patch("os.path.getsize", return_value=100)
@patch("steglib.backend.run_cmd")
@patch("steglib.backend.logger.error")
@patch("steglib.backend.logger.info")
def test_execute_oserror(mock_info, mock_error, mock_run, mock_getsize, mock_isfile):
    backend = DockerComposeBackend("pkg1", "/pkg_path", "/group_dir")
    mock_run.side_effect = OSError("os error")
    with pytest.raises(RuntimeError):
        backend.execute("logs")
    mock_error.assert_any_call("[pkg1] Failed to logs: os error")
