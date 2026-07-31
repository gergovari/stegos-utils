import sys, os
sys.path.insert(0, "/home/ubu/Documents/stegos-workspace/stegos-utils/lib")
import yaml
from steglib.deployer import DockerComposeDeployer
from unittest.mock import Mock

manifest = {
    "capabilities": {
        "consumes": [
            {
                "name": "reverse-proxy",
                "exports": {
                    "subdomain": "{{ config.subdomain }}",
                    "http_port": 80
                }
            }
        ]
    }
}

global_conf = {"base_domain": "stegos.localhost"}
final_conf = {"subdomain": "whoami", "enabled_capabilities": {"reverse-proxy": ["nginx-proxy-abc"]}}

import jinja2
env = jinja2.Environment()

deployer = DockerComposeDeployer(
    name="docker-compose",
    config={"templates": [{"src": "docker-compose.yml.j2", "dest": "docker-compose.yml"}]},
    pkg_dir="/home/ubu/Documents/stegos-workspace/stegos-apps-base/whoami",
    out_dir="/tmp/whoami-test",
    env=env,
    final_conf=final_conf,
    global_conf=global_conf,
    manifest=manifest,
    instance_name="whoami-123",
    group_name="stegos"
)

cap_manager = Mock()
prov_data = {
    "nginx-proxy-abc": {
        "injector": {
            "docker-compose": {
                "networks": ["proxy"],
                "env": {
                    "VIRTUAL_HOST": "{{ consumer.exports.subdomain }}.{{ global_config.base_domain }}",
                    "VIRTUAL_PORT": "{{ consumer.exports.http_port }}",
                    "LETSENCRYPT_HOST": "{{ consumer.exports.subdomain }}.{{ global_config.base_domain }}"
                }
            }
        }
    }
}
cap_manager.get_providers.return_value = prov_data

deployer._render_templates(cap_manager, final_conf)

with open("/tmp/whoami-test/docker-compose.yml", "r") as f:
    print(f.read())
