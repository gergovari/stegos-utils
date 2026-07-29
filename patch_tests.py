import re
with open("tests/test_backend.py", "r") as f:
    content = f.read()

patch = """from steglib.backend import BackendBase, DockerComposeBackend, BACKENDS
from unittest.mock import Mock
import steglib.backend
steglib.backend.ensure_running = Mock(return_value={"DOCKER_HOST": "unix://fake"})
steglib.backend.get_docker_env = Mock(return_value={"DOCKER_HOST": "unix://fake"})
"""
content = content.replace("from steglib.backend import BackendBase, DockerComposeBackend, BACKENDS", patch)
with open("tests/test_backend.py", "w") as f:
    f.write(content)
