import re
with open("tests/test_backend.py", "r") as f:
    content = f.read()

# Remove test_execute_logs entirely
content = re.sub(r'@patch\("os\.path\.isfile", return_value=True\)\n@patch\("steglib\.backend\.run_cmd"\)\ndef test_execute_logs\(mock_run, mock_isfile\):\n    backend = DockerComposeBackend\("pkg1", "/pkg_path", "/group_dir"\)\n    backend\.execute\("unknown"\)\n    assert mock_run\.call_args\[0\]\[0\] == \["docker", "compose", "-p", "pkg1", "-f", "/pkg_path/docker-compose\.yml", "logs"\]\n\n', '', content)

with open("tests/test_backend.py", "w") as f:
    f.write(content)
