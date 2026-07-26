import subprocess
import os
import pytest

# Find the bin directory
BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../bin'))

@pytest.mark.parametrize("script_name", [
    "stegctl",
    "steggroup",
    "stegmap",
    "stegpkg"
])
def test_cli_help(script_name):
    """Test that all CLI scripts can run and show help."""
    script_path = os.path.join(BIN_DIR, script_name)
    
    # Run the script with --help
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.join(BIN_DIR, '../lib'))
    result = subprocess.run([script_path, "--help"], capture_output=True, text=True, env=env)
    
    # It should succeed and print usage information
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
