import pytest
import threading
import time
import logging
from unittest.mock import patch, MagicMock

from steglib.lifecycle import LifecycleManager
from steglib.backend import BackendBase

class DummyBackend:
    def __init__(self, pkg, path, cont_dir):
        self.pkg = pkg
        
    def execute(self, action, if_created, follow=False):
        pass

@pytest.fixture
def mock_env():
    with patch("steglib.lifecycle.os.path.isdir", return_value=True), \
         patch("steglib.lifecycle.os.listdir", return_value=["pkgA", "pkgB", "pkgC"]), \
         patch("steglib.lifecycle.GroupManager.resolve", return_value="default"):
        yield

def build_mock_instance(conf_dict, is_installed=True, deployer="dummy"):
    mock_inst = MagicMock()
    mock_inst.read_conf.return_value = conf_dict
    mock_inst.is_installed = is_installed
    mock_inst.deployer = deployer
    return mock_inst

def test_lifecycle_start_dependency_order(mock_env):
    # pkgB depends on pkgA
    # pkgC depends on pkgB
    confs = {
        "pkgA": {"enabled_capabilities": {}},
        "pkgB": {"enabled_capabilities": {"capA": ["pkgA"]}},
        "pkgC": {"enabled_capabilities": {"capB": ["pkgB"]}}
    }
    
    execution_order = []
    lock = threading.Lock()
    
    def fake_execute(self, action, if_created, follow=False):
        # Add slight artificial delay to make sure thread pool would race if dependencies weren't honored
        time.sleep(0.05)
        with lock:
            execution_order.append(self.pkg)
        return "success"
        
    DummyBackend.execute = fake_execute

    with patch("steglib.lifecycle.Instance") as mock_instance, \
         patch.dict("steglib.lifecycle.BACKENDS", {"dummy": DummyBackend}):
         
        mock_instance.side_effect = lambda group, pkg: build_mock_instance(confs[pkg])
        
        lm = LifecycleManager()
        results = lm.execute("start")
        
        assert results == {"pkgA": "success", "pkgB": "success", "pkgC": "success"}
        assert execution_order == ["pkgA", "pkgB", "pkgC"]

def test_lifecycle_stop_reverse_dependency_order(mock_env):
    # pkgB depends on pkgA
    # pkgC depends on pkgB
    confs = {
        "pkgA": {"enabled_capabilities": {}},
        "pkgB": {"enabled_capabilities": {"capA": ["pkgA"]}},
        "pkgC": {"enabled_capabilities": {"capB": ["pkgB"]}}
    }
    
    execution_order = []
    lock = threading.Lock()
    
    def fake_execute(self, action, if_created, follow=False):
        time.sleep(0.05)
        with lock:
            execution_order.append(self.pkg)
        return "success"
        
    DummyBackend.execute = fake_execute

    with patch("steglib.lifecycle.Instance") as mock_instance, \
         patch.dict("steglib.lifecycle.BACKENDS", {"dummy": DummyBackend}):
         
        mock_instance.side_effect = lambda group, pkg: build_mock_instance(confs[pkg])
        
        lm = LifecycleManager()
        results = lm.execute("stop")
        
        assert results == {"pkgA": "success", "pkgB": "success", "pkgC": "success"}
        assert execution_order == ["pkgC", "pkgB", "pkgA"]

def test_lifecycle_wait_for_start_false(mock_env):
    # pkgB consumes capA from pkgA, but wait_for_start is False!
    confs = {
        "pkgA": {"enabled_capabilities": {}},
        "pkgB": {
            "enabled_capabilities": {"capA": ["pkgA"]},
            "capability_metadata": {"capA": {"wait_for_start": False}}
        },
        "pkgC": {}
    }
    
    execution_order = []
    lock = threading.Lock()
    
    def fake_execute(self, action, if_created, follow=False):
        if self.pkg == "pkgA":
            time.sleep(0.1) # A is slow
        with lock:
            execution_order.append(self.pkg)
        return "success"
        
    DummyBackend.execute = fake_execute

    with patch("steglib.lifecycle.Instance") as mock_instance, \
         patch.dict("steglib.lifecycle.BACKENDS", {"dummy": DummyBackend}):
         
        mock_instance.side_effect = lambda group, pkg: build_mock_instance(confs.get(pkg, {}))
        
        lm = LifecycleManager()
        results = lm.execute("start")
        
        # Since wait_for_start is False, pkgB doesn't wait for pkgA. 
        # Since pkgA is slow, pkgB and pkgC should finish first.
        assert execution_order.index("pkgA") > 0

def test_lifecycle_failure_cascading(mock_env):
    # pkgB depends on pkgA
    # pkgC depends on pkgB
    confs = {
        "pkgA": {"enabled_capabilities": {}},
        "pkgB": {"enabled_capabilities": {"capA": ["pkgA"]}},
        "pkgC": {"enabled_capabilities": {"capB": ["pkgB"]}}
    }
    
    execution_order = []
    lock = threading.Lock()
    
    def fake_execute(self, action, if_created, follow=False):
        if self.pkg == "pkgA":
            raise RuntimeError("Backend failed!")
        with lock:
            execution_order.append(self.pkg)
        return "success"
        
    DummyBackend.execute = fake_execute

    with patch("steglib.lifecycle.Instance") as mock_instance, \
         patch.dict("steglib.lifecycle.BACKENDS", {"dummy": DummyBackend}):
         
        mock_instance.side_effect = lambda group, pkg: build_mock_instance(confs[pkg])
        
        lm = LifecycleManager()
        with pytest.raises(RuntimeError, match="Action 'start' failed for packages"):
            lm.execute("start")
            
        # pkgA failed, so pkgB and pkgC were skipped
        assert execution_order == []
