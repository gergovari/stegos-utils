import os
import pytest
from unittest.mock import Mock, patch, call
import jsonschema

from steglib.engine import PackageEngine, PackageNotFoundError, parse_consumes, load_manifest
from steglib.group import GroupManager

def test_load_manifest_not_found(tmp_path):
    assert load_manifest(str(tmp_path)) is None

def test_load_manifest_valid(tmp_path):
    manifest_path = tmp_path / "manifest.yml"
    manifest_path.write_text("name: mypkg\nsingleton: true\n")
    manifest = load_manifest(str(tmp_path))
    assert manifest is not None
    assert manifest["name"] == "mypkg"
    assert manifest["singleton"] is True

def test_parse_consumes_list():
    manifest = {"capabilities": {"consumes": ["db", {"name": "web", "max": 1}]}}
    res = parse_consumes(manifest)
    assert res == {"db": {}, "web": {"max": 1}}

def test_parse_consumes_dict():
    manifest = {"capabilities": {"consumes": {"db": {}, "web": {"max": 1}}}}
    res = parse_consumes(manifest)
    assert res == {"db": {}, "web": {"max": 1}}

def test_package_engine_init(mock_stegos_root, mocker):
    mocker.patch.object(GroupManager, 'resolve', return_value="default")
    engine = PackageEngine()
    
    assert engine.group_name == "default"
    assert os.path.exists(engine.group_dir)

def test_find_package_dir_not_found(mock_stegos_root, mocker):
    mocker.patch.object(GroupManager, 'resolve', return_value="default")
    engine = PackageEngine()
    os.makedirs(engine.repo_dir)
    
    with pytest.raises(PackageNotFoundError, match="Package 'foo' not found"):
        engine.find_package_dir("foo")

def test_find_package_dir_success(mock_stegos_root, mocker):
    mocker.patch.object(GroupManager, 'resolve', return_value="default")
    engine = PackageEngine()
    
    # Create fake repo structure
    pkg_dir = os.path.join(engine.repo_dir, "repo1", "mypkg")
    os.makedirs(pkg_dir)
    with open(os.path.join(pkg_dir, "manifest.yml"), "w") as f:
        f.write("name: mypkg\n")
        
    found = engine.find_package_dir("mypkg")
    assert found == pkg_dir

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
@patch("steglib.engine.load_manifest")
@patch("steglib.engine.Instance")
@patch("steglib.engine.os.makedirs")
@patch("steglib.engine.Environment")
def test_process_package(mock_env, mock_makedirs, mock_instance, mock_load, mock_cap, mock_resolve, mock_stegos_root):
    mock_load.return_value = {"name": "pkg1", "singleton": False}
    
    mock_inst_obj = Mock()
    mock_inst_obj.read_conf.return_value = {}
    mock_instance.return_value = mock_inst_obj
    
    engine = PackageEngine()
    engine._find_instances_by_package = Mock(return_value=[])
    engine.cap_manager = Mock()
    
    inst_id = engine.process_package("/pkg")
    assert inst_id.startswith("pkg1-")
    mock_inst_obj.write_conf.assert_called_once()

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
@patch("steglib.engine.os.listdir", return_value=[])
@patch("steglib.engine.os.path.isdir", return_value=True)
def test_resolve_instance_isdir(mock_isdir, mock_listdir, mock_cap, mock_resolve, mock_stegos_root):
    engine = PackageEngine()
    assert engine.resolve_instance("inst1") == "inst1"

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
@patch("steglib.engine.os.path.isdir", return_value=False)
def test_resolve_instance_bypkg(mock_isdir, mock_cap, mock_resolve, mock_stegos_root):
    engine = PackageEngine()
    engine._find_instances_by_package = Mock(return_value=["inst1"])
    assert engine.resolve_instance("pkg1") == "inst1"

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
@patch("steglib.engine.os.path.isdir", return_value=False)
def test_resolve_instances(mock_isdir, mock_cap, mock_resolve, mock_stegos_root):
    engine = PackageEngine()
    engine._find_instances_by_package = Mock(side_effect=[["inst1", "inst2"]])
    
    # Non-interactive multiple matches raises by default or adds all
    res = engine.resolve_instances(["pkg1"])
    assert res == ["inst1", "inst2"]

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_instance_name(mock_cap, mock_resolve):
    engine = PackageEngine()
    assert engine._resolve_instance_name("pkg1", "myid", False, False, [], None) == "myid"
    
    with pytest.raises(ValueError, match="is a singleton"):
        engine._resolve_instance_name("pkg1", None, False, True, ["inst1"], None)
        
    assert engine._resolve_instance_name("pkg1", None, True, False, ["inst1"], None) == "inst1"

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_capabilities(mock_cap, mock_resolve):
    engine = PackageEngine()
    engine.cap_manager = Mock()
    engine.cap_manager.get_providers.return_value = {"prov1": {}}
    
    consumes = {"cap1": {}}
    pkg_conf = {}
    
    enabled = engine._resolve_capabilities(consumes, pkg_conf, False, True, None)
    assert enabled == {'cap1': ['prov1']}


# --- Secrets tests ---

@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_first_install(mock_cap, mock_resolve, mock_stegos_root):
    """Secrets are auto-generated on first install (not in pkg_conf)."""
    engine = PackageEngine()
    manifest = {
        "secrets": {
            "admin_pass": {"type": "password", "length": 16},
            "admin_user": {"type": "username", "length": 8},
        }
    }
    result = engine._resolve_secrets(manifest, pkg_conf={}, reconfigure=False,
                                     non_interactive=False, interactive_cb=None)
    assert "admin_pass" in result
    assert "admin_user" in result
    assert len(result["admin_pass"]) > 0
    assert result["admin_user"].startswith("admin-")


@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_preserved_on_non_interactive(mock_cap, mock_resolve, mock_stegos_root):
    """Existing secrets are preserved in non-interactive mode."""
    engine = PackageEngine()
    manifest = {
        "secrets": {
            "admin_pass": {"type": "password", "length": 16},
        }
    }
    pkg_conf = {"admin_pass": "existing-secret-123"}
    result = engine._resolve_secrets(manifest, pkg_conf, reconfigure=False,
                                     non_interactive=True, interactive_cb=None)
    assert result["admin_pass"] == "existing-secret-123"


@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_preserved_on_upgrade(mock_cap, mock_resolve, mock_stegos_root):
    """Existing secrets are preserved on upgrade (non-interactive, no reconfigure)."""
    engine = PackageEngine()
    manifest = {
        "secrets": {
            "admin_pass": {"type": "password", "length": 16},
        }
    }
    pkg_conf = {"admin_pass": "keep-me"}
    result = engine._resolve_secrets(manifest, pkg_conf, reconfigure=False,
                                     non_interactive=True, interactive_cb=None)
    assert result["admin_pass"] == "keep-me"


@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_regenerate_on_reconfigure(mock_cap, mock_resolve, mock_stegos_root):
    """Secrets can be regenerated when user confirms during reconfigure."""
    engine = PackageEngine()
    manifest = {
        "secrets": {
            "admin_pass": {"type": "password", "length": 16},
        }
    }
    pkg_conf = {"admin_pass": "old-secret"}
    cb = Mock(return_value="y")

    result = engine._resolve_secrets(manifest, pkg_conf, reconfigure=True,
                                     non_interactive=False, interactive_cb=cb)
    assert result["admin_pass"] != "old-secret"
    cb.assert_called_once()


@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_keep_on_reconfigure_decline(mock_cap, mock_resolve, mock_stegos_root):
    """Secrets are kept when user declines regeneration during reconfigure."""
    engine = PackageEngine()
    manifest = {
        "secrets": {
            "admin_pass": {"type": "password", "length": 16},
        }
    }
    pkg_conf = {"admin_pass": "keep-me"}
    cb = Mock(return_value="n")

    result = engine._resolve_secrets(manifest, pkg_conf, reconfigure=True,
                                     non_interactive=False, interactive_cb=cb)
    assert result["admin_pass"] == "keep-me"


@patch("steglib.engine.GroupManager.resolve", return_value="default")
@patch("steglib.engine.CapabilityManager")
def test_resolve_secrets_no_secrets_field(mock_cap, mock_resolve, mock_stegos_root):
    """Returns empty dict when manifest has no secrets field."""
    engine = PackageEngine()
    result = engine._resolve_secrets({}, pkg_conf={}, reconfigure=False,
                                     non_interactive=False, interactive_cb=None)
    assert result == {}
