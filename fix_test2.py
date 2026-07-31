import re

with open("tests/test_backend.py", "r") as f:
    content = f.read()

# Fix test_execute_logs_follow
content = re.sub(
    r'mock_info\.assert_any_call\("log2"\)',
    r'mock_info.assert_any_call("backend_log_line", package="pkg1", line="log2")',
    content
)

# Fix test_execute_subprocess_error signature
content = re.sub(
    r'def test_execute_subprocess_error\(mock_info, mock_run, mock_getsize, mock_isfile\):',
    r'def test_execute_subprocess_error(mock_run, mock_getsize, mock_isfile):',
    content
)

# Fix test_execute_oserror signature
content = re.sub(
    r'def test_execute_oserror\(mock_info, mock_run, mock_getsize, mock_isfile\):',
    r'def test_execute_oserror(mock_run, mock_getsize, mock_isfile):',
    content
)

with open("tests/test_backend.py", "w") as f:
    f.write(content)
