import os
import pytest
import shutil
import json
from unittest.mock import Mock, patch, mock_open, call
from steglib.manager import PackageManager
from steglib.engine import PackageNotFoundError

@patch("steglib.engine.load_manifest")
def test_manager_install(mock_load_manifest, mocker):
    mock_load_manifest.return_value = {"name": "mypkg"}
    engine_mock = Mock()
    engine_mock.find_package_dir.return_value = "/path/to/pkg"
    engine_mock._resolve_instance_name.return_value = "mypkg-1234"
    engine_mock.process_package.return_value = "mypkg-1234"
    
    manager = PackageManager(engine_mock)
    manager.install(["mypkg"])
    
    engine_mock.find_package_dir.assert_called_once_with("mypkg", None)
    engine_mock.process_package.assert_called_once()

@patch("steglib.engine.load_manifest")
def test_manager_install_with_config(mock_load_manifest, mocker):
    mock_load_manifest.return_value = {"name": "mypkg"}
    engine_mock = Mock()
    engine_mock.find_package_dir.return_value = "/path/to/pkg"
    engine_mock._resolve_instance_name.return_value = "mypkg-1234"
    engine_mock.process_package.return_value = "mypkg-1234"
    
    manager = PackageManager(engine_mock)
    with patch("builtins.open", mock_open(read_data='{"a": 1}')):
        manager.install(["mypkg"], config_file="conf.json")
    
    engine_mock.process_package.assert_called_once()
    assert engine_mock.process_package.call_args[0][1] == {"a": 1}

@patch("steglib.engine.load_manifest")
def test_manager_install_pre_registers_capabilities(mock_load_manifest, mocker):
    def fake_load_manifest(pkg_dir):
        if "whoami" in pkg_dir:
            return {"name": "whoami"}
        if "nginx-proxy" in pkg_dir:
            return {
                "name": "nginx-proxy",
                "capabilities": {
                    "provides": [{"name": "reverse-proxy"}]
                }
            }
        return {"name": "other"}
    
    mock_load_manifest.side_effect = fake_load_manifest
    engine_mock = Mock()
    engine_mock.group_dir = "/fake/group/dir"
    engine_mock.group_name = "fake_group"
    engine_mock.find_package_dir.side_effect = lambda pkg, repo: f"/path/to/{pkg}"
    engine_mock._resolve_instance_name.side_effect = lambda pkg, *args: f"{pkg}-123"
    
    manager = PackageManager(engine_mock)
    manager.install(["whoami", "nginx-proxy"])
    
    # Assert register was called for reverse-proxy from nginx-proxy-123
    engine_mock.cap_manager.register.assert_called_once_with("reverse-proxy", "nginx-proxy-123", {})
    
    # Verify the order of calls
    calls = engine_mock.mock_calls
    register_idx = next(i for i, c in enumerate(calls) if "register" in c[0])
    process_whoami_idx = next(i for i, c in enumerate(calls) if "process_package" in c[0] and c[1][4] == "whoami-123")
    
    assert register_idx < process_whoami_idx, "Capabilities must be registered before packages are processed"

def test_manager_install_invalid_name():
    manager = PackageManager(Mock())
    with pytest.raises(ValueError, match="Invalid package name"):
        manager.install(["invalid name!"])

def test_manager_install_multiple_with_id():
    manager = PackageManager(Mock())
    with pytest.raises(ValueError, match="--id cannot be used"):
        manager.install(["pkg1", "pkg2"], instance_id="custom-id")

def test_manager_clean_no_group_dir(tmp_path, mocker):
    engine_mock = Mock()
    engine_mock.group_dir = str(tmp_path / "nonexistent")
    manager = PackageManager(engine_mock)
    
    # Should just return without errors
    manager.clean(auto_confirm=True)

def test_manager_clean_removes_unmanaged(tmp_path, mocker):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = str(tmp_path)
    manager = PackageManager(engine_mock)
    
    # Create an unmanaged directory
    unmanaged_dir = tmp_path / "unmanaged-inst"
    unmanaged_dir.mkdir()
    
    # Mock Instance to say it's not installed
    mocker.patch('steglib.manager.Instance.is_installed', False)
    
    manager.clean(auto_confirm=True)
    assert not os.path.exists(unmanaged_dir)

@patch("steglib.manager.os.listdir")
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
def test_reconfigure(mock_instance, mock_isdir, mock_listdir):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    engine_mock.find_package_dir.return_value = "/pkg"
    mock_listdir.return_value = ["inst1"]
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg1"
    mock_instance.return_value = mock_inst_obj
    
    manager = PackageManager(engine_mock)
    manager.reconfigure()
    
    engine_mock.process_package.assert_called_once()

@patch("steglib.lifecycle.LifecycleManager")
@patch("steglib.manager.os.path.exists", return_value=True)
@patch("steglib.manager.os.remove")
def test_remove(mock_remove, mock_exists, mock_lm):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    engine_mock.resolve_instances.return_value = ["inst1"]
    
    manager = PackageManager(engine_mock)
    manager._find_dependents = Mock(return_value={})
    
    manager.remove(["inst1"])
    mock_lm.return_value.execute.assert_called_once_with("stop", "inst1", False, False)
    mock_remove.assert_has_calls([
        call("/group/inst1/backend/.stegpkg-state.json"),
        call("/group/inst1/backend/docker-compose.yml")
    ], any_order=True)

@patch("steglib.lifecycle.LifecycleManager")
@patch("steglib.manager.os.path.exists", return_value=True)
@patch("steglib.manager.shutil.rmtree")
def test_remove_purge(mock_rmtree, mock_exists, mock_lm):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    engine_mock.resolve_instances.return_value = ["inst1"]
    
    manager = PackageManager(engine_mock)
    manager._find_dependents = Mock(return_value={})
    
    manager.remove(["inst1"], purge=True)
    mock_rmtree.assert_called_once_with("/group/inst1")

@patch("steglib.utils.hash_dir", side_effect=["hash1", "hash2"])
@patch("steglib.manager.os.listdir")
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
@patch("steglib.lifecycle.LifecycleManager")
def test_upgrade(mock_lm, mock_instance, mock_isdir, mock_listdir, mock_hash):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    mock_listdir.return_value = ["inst1"]
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg1"
    mock_inst_obj.conf_path = "/mock/conf.json"
    mock_instance.return_value = mock_inst_obj
    
    # Mock status as running
    mock_lm.return_value.execute.return_value = {"inst1": {"state": "running", "running": 1, "total": 1}}
    
    manager = PackageManager(engine_mock)
    manager._find_dependents = Mock(return_value={})
    manager.upgrade()
    
    engine_mock.process_package.assert_called_once()
    mock_lm.return_value.execute.assert_has_calls([call("status", "inst1"), call("start", "inst1", True, False)], any_order=False)

@patch("steglib.utils.hash_dir", side_effect=["hash1", "hash2"])
@patch("steglib.manager.os.listdir")
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
@patch("steglib.lifecycle.LifecycleManager")
def test_upgrade_stopped(mock_lm, mock_instance, mock_isdir, mock_listdir, mock_hash):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    mock_listdir.return_value = ["inst1"]
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg1"
    mock_inst_obj.conf_path = "/mock/conf.json"
    mock_instance.return_value = mock_inst_obj
    
    # Mock status as stopped
    mock_lm.return_value.execute.return_value = {"inst1": {"state": "stopped", "running": 0, "total": 1}}
    
    manager = PackageManager(engine_mock)
    manager._find_dependents = Mock(return_value={})
    manager.upgrade()
    
    engine_mock.process_package.assert_called_once()
    # It should not call start because it was stopped
    mock_lm.return_value.execute.assert_called_once_with("status", "inst1")

@patch("steglib.utils.hash_dir", side_effect=["hash1", "hash2"])
@patch("steglib.manager.os.listdir")
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
@patch("steglib.lifecycle.LifecycleManager")
def test_upgrade_cascade(mock_lm, mock_instance, mock_isdir, mock_listdir, mock_hash):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.group_dir = "/group"
    mock_listdir.return_value = ["inst1"]
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg1"
    mock_inst_obj.conf_path = "/mock/conf.json"
    mock_instance.return_value = mock_inst_obj
    
    # Mock status as running
    mock_lm.return_value.execute.return_value = {"inst1": {"state": "running", "running": 1, "total": 1}, "dep1": {"state": "running", "running": 1, "total": 1}}
    
    manager = PackageManager(engine_mock)
    manager._find_dependents = Mock(return_value={"inst1": ["dep1"]})
    manager.upgrade()
    
    # 1 for inst1, 1 for dep1
    assert engine_mock.process_package.call_count == 2
    mock_lm.return_value.execute.assert_any_call("start", "dep1", False, False)

@patch("steglib.manager.os.listdir", return_value=["repo1"])
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.run_cmd")
def test_update(mock_run, mock_isdir, mock_listdir):
    engine_mock = Mock()
    engine_mock.repo_dir = "/repos"
    
    manager = PackageManager(engine_mock)
    manager.update()
    
    assert mock_run.call_count == 1

@patch("steglib.manager.os.listdir", return_value=["inst1", "inst2"])
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
def test_list_packages(mock_instance, mock_isdir, mock_listdir):
    engine_mock = Mock()
    engine_mock.group_dir = "/group"
    engine_mock.group_name = "default"
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg1"
    mock_instance.return_value = mock_inst_obj
    
    manager = PackageManager(engine_mock)
    manager.list_packages()
    assert mock_instance.call_count == 2

@patch("steglib.manager.os.listdir", return_value=["inst2"])
@patch("steglib.manager.os.path.isdir", return_value=True)
@patch("steglib.manager.Instance")
def test_find_dependents(mock_instance, mock_isdir, mock_listdir):
    engine_mock = Mock()
    engine_mock.group_dir = "/group"
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.read_conf.return_value = {"enabled_capabilities": {"cap1": ["inst1"]}}
    mock_instance.return_value = mock_inst_obj
    
    manager = PackageManager(engine_mock)
    deps = manager._find_dependents(["inst1"])
    assert deps == {"inst1": ["inst2"]}

@patch("steglib.manager.Instance")
@patch("steglib.lifecycle.LifecycleManager")
def test_cascade_remove(mock_lm, mock_instance):
    engine_mock = Mock()
    engine_mock.group_name = "default"
    engine_mock.find_package_dir.return_value = "/pkg"
    
    mock_inst_obj = Mock()
    mock_inst_obj.is_installed = True
    mock_inst_obj.package_name = "pkg2"
    mock_inst_obj.read_conf.return_value = {"enabled_capabilities": {"cap1": ["inst1", "inst3"]}}
    mock_instance.return_value = mock_inst_obj
    
    # Mock status as running for inst2
    mock_lm.return_value.execute.return_value = {"inst2": {"state": "running", "running": 1, "total": 1}}
    
    manager = PackageManager(engine_mock)
    manager._cascade_remove_integration("inst2", ["inst1"])
    
    mock_inst_obj.write_conf.assert_called_once_with({"enabled_capabilities": {"cap1": ["inst3"]}})
    engine_mock.process_package.assert_called_once()
    mock_lm.return_value.execute.assert_has_calls([call("status", "inst2"), call("start", "inst2", False, False)], any_order=False)
