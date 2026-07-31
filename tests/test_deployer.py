import pytest
import yaml
from unittest.mock import Mock, patch, mock_open
from jinja2 import Environment

from steglib.deployer import DockerComposeDeployer

@pytest.fixture
def jinja_env():
    return Environment()

@pytest.fixture
def global_conf():
    return {"group_name": "stegos", "base_domain": "localhost"}

def test_deployer_network_rewrite(jinja_env, global_conf):
    manifest = {
        "capabilities": {
            "provides": [
                {
                    "name": "my_cap",
                    "injectors": {
                        "docker-compose": {
                            "networks": ["proxy"]
                        }
                    }
                }
            ]
        }
    }
    
    deployer = DockerComposeDeployer(
        name="docker-compose",
        config={"templates": [{"src": "docker-compose.yml.j2", "dest": "./docker-compose.yml"}]},
        pkg_dir="/tmp/pkg",
        out_dir="/tmp/out",
        env=jinja_env,
        final_conf={},
        global_conf=global_conf,
        manifest=manifest,
        instance_name="my_inst",
        group_name="stegos"
    )

    cap_manager = Mock()
    cap_manager.get_providers.return_value = {}

    initial_yaml = """
services:
  app:
    networks:
      - proxy
      - other
networks:
  proxy:
    name: proxy
    driver: bridge
  other:
    name: other
"""

    # Mock file I/O
    m_open = mock_open(read_data=initial_yaml)
    with patch("builtins.open", m_open), patch("os.makedirs"), patch("os.path.exists", return_value=True), patch("os.fsync"):
        deployer._render_templates(cap_manager, {})
    
    # We want to check what was written to the file
    # The last call to `write` on the handle should contain the dumped yaml
    write_calls = m_open().write.call_args_list
    written_data = "".join(call[0][0] for call in write_calls)
    
    result = yaml.safe_load(written_data)
    
    # Validate the network was renamed in top-level networks
    assert "networks" in result
    assert "proxy" not in result["networks"]
    assert "stegos_my_inst_proxy" in result["networks"]
    assert result["networks"]["stegos_my_inst_proxy"]["external"] is True
    
    # Validate the network was renamed in the service
    assert "stegos_my_inst_proxy" in result["services"]["app"]["networks"]
    assert "proxy" not in result["services"]["app"]["networks"]
    assert "other" in result["services"]["app"]["networks"]
