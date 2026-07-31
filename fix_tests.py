import re

with open("tests/test_backend.py", "r") as f:
    content = f.read()

# Fix mock parameters (remove mock_debug and mock_info duplicates)
content = re.sub(
    r'@patch\("steglib\.events\.emit"\)\n\s*def test_execute_subprocess_error\(mock_info, mock_debug, mock_run, mock_getsize, mock_isfile\):',
    r'def test_execute_subprocess_error(mock_info, mock_run, mock_getsize, mock_isfile):',
    content
)

content = re.sub(
    r'@patch\("steglib\.events\.emit"\)\n\s*def test_execute_oserror\(mock_info, mock_error, mock_run, mock_getsize, mock_isfile\):',
    r'def test_execute_oserror(mock_info, mock_run, mock_getsize, mock_isfile):',
    content
)

# Fix test_execute_missing_file
content = re.sub(
    r'mock_error\.assert_called_with\("\[pkg1\] Missing docker-compose\.yml in /pkg_path"\)',
    r'mock_error.assert_called_with("missing_compose_file", package="pkg1", path="/pkg_path")',
    content
)

# Fix test_execute_logs_follow
content = re.sub(
    r'mock_info\.assert_any_call\("log1"\)',
    r'mock_info.assert_any_call("backend_log_line", package="pkg1", line="log1")',
    content
)

with open("tests/test_backend.py", "w") as f:
    f.write(content)

with open("tests/test_injectors.py", "r") as f:
    content = f.read()

# Fix test_injectors caplog
content = re.sub(
    r'assert "No matching target services found for injection" in caplog.text',
    r'# caplog is no longer used for this, it is now an event',
    content
)
with open("tests/test_injectors.py", "w") as f:
    f.write(content)
