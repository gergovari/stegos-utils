import pytest
from unittest.mock import Mock, patch
from steglib.daemon_api import create_dispatcher

@pytest.fixture
def dispatcher():
    return create_dispatcher()

def test_dispatcher_invalid_action(dispatcher):
    with pytest.raises(ValueError, match="Unknown action prefix"):
        dispatcher.dispatch("invalid", {}, None, None)
        
    with pytest.raises(ValueError, match="Unknown method 'invalid' for prefix 'pkg'"):
        dispatcher.dispatch("pkg.invalid", {}, None, None)

@patch("steglib.daemon_api.PackageManager")
@patch("steglib.daemon_api.PackageEngine")
def test_package_controller_install(mock_pe, mock_pm, dispatcher):
    args = {"packages": ["pkg1"], "repo": "repo1", "group": "g1"}
    interactive_cb = Mock()
    send = Mock()
    
    dispatcher.dispatch("pkg.install", args, interactive_cb, send)
    
    mock_pm.return_value.install.assert_called_once_with(
        ["pkg1"], "repo1", None, False, False, None, interactive_cb
    )

@patch("steglib.daemon_api.LifecycleManager")
def test_lifecycle_controller_execute(mock_lm, dispatcher):
    args = {"ctl_action": "start", "package": "pkg1"}
    interactive_cb = Mock()
    send = Mock()
    
    dispatcher.dispatch("ctl.execute", args, interactive_cb, send)
    mock_lm.return_value.execute.assert_called_once_with("start", "pkg1", False, False)

@patch("steglib.daemon_api.LifecycleManager")
def test_lifecycle_controller_restart(mock_lm, dispatcher):
    args = {"ctl_action": "restart", "package": "pkg1"}
    
    dispatcher.dispatch("ctl.execute", args, None, None)
    mock_lm.return_value.execute.assert_any_call("stop", "pkg1", False, False)
    mock_lm.return_value.execute.assert_any_call("start", "pkg1", False, False)

@patch("steglib.daemon_api.LifecycleManager")
def test_lifecycle_controller_multiple_instances(mock_lm, dispatcher):
    from steglib.lifecycle import MultipleInstancesError
    
    mock_lm.return_value.execute.side_effect = MultipleInstancesError(["inst1", "inst2"])
    
    args = {"ctl_action": "start", "package": "pkg1"}
    interactive_cb = Mock(return_value="inst2")
    
    # We expect execute to be called twice: once which raises, then again for inst2
    # We must patch it so the second call doesn't raise
    mock_lm.return_value.execute.side_effect = [MultipleInstancesError(["inst1", "inst2"]), None]
    
    dispatcher.dispatch("ctl.execute", args, interactive_cb, None)
    
    assert mock_lm.return_value.execute.call_count == 2
    mock_lm.return_value.execute.assert_any_call("start", "inst2", False, False)

@patch("steglib.daemon_api.GroupInitializer")
def test_group_controller_init(mock_gim, dispatcher):
    args = {"label": "label1", "device": "/dev/sda", "interactive": True, "domain": "localhost", "timezone": "UTC", "force": False}
    interactive_cb = Mock()
    
    dispatcher.dispatch("group.init", args, interactive_cb, None)
    mock_gim.return_value.initialize.assert_called_once_with(
        device="/dev/sda", group_name="label1", domain="localhost", timezone="UTC", force=False
    )

@patch("steglib.daemon_api.DriveMapper")
def test_map_controller_mount(mock_sm, dispatcher):
    args = {"map_action": "mount"}
    dispatcher.dispatch("map.execute", args, None, None)
    mock_sm.return_value.mount_all.assert_called_once()

def test_map_controller_invalid(dispatcher):
    args = {"map_action": "invalid"}
    with pytest.raises(ValueError, match="Unknown map action"):
        dispatcher.dispatch("map.execute", args, None, None)
