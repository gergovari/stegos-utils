import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin')))

@pytest.fixture(autouse=True)
def mock_stegos_root(monkeypatch, tmp_path):
    """Automatically mock STEGOS_ROOT for all tests to use a temporary directory."""
    mock_root = tmp_path / "stegos_root"
    mock_root.mkdir()
    monkeypatch.setenv("STEGOS_ROOT", str(mock_root))
    
    monkeypatch.setattr('steglib.constants.STEGOS_ROOT', str(mock_root))
    monkeypatch.setattr('steglib.constants.PERSISTENT_DIR', os.path.join(str(mock_root), "persistent"))
    monkeypatch.setattr('steglib.constants.REPOS_DIR', os.path.join(str(mock_root), "repos"))
    
    import steglib.engine
    monkeypatch.setattr('steglib.engine.PERSISTENT_DIR', os.path.join(str(mock_root), "persistent"))
    monkeypatch.setattr('steglib.engine.REPOS_DIR', os.path.join(str(mock_root), "repos"))
    
    return str(mock_root)

@pytest.fixture
def mock_subprocess(mocker):
    """Fixture to easily mock subprocess.run."""
    return mocker.patch('subprocess.run')

@pytest.fixture
def temp_dir(tmp_path):
    """Returns a temporary directory for testing."""
    return tmp_path
