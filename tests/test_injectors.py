import pytest
import logging
from unittest.mock import Mock, patch
from jinja2 import Environment

from steglib.injectors import DockerComposeInjector


@pytest.fixture
def jinja_env():
    return Environment()


@pytest.fixture
def global_conf():
    return {"db_host": "db.example.com", "port": 5432}


def get_cap_manager(providers_dict):
    cap_manager = Mock()
    cap_manager.get_providers = lambda cap_name: providers_dict.get(cap_name, {})
    return cap_manager


def test_env_injection(jinja_env, global_conf):
    consumes = ["db_cap"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {
        "services": {
            "svc_list": {
                "environment": ["EXISTING=1"]
            },
            "svc_dict": {
                "environment": {"EXISTING": "2"}
            }
        }
    }
    
    providers = {
        "db_cap": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {
                            "NEW_VAR": "new_val",
                            "DB_HOST": "{{ global_config.db_host }}"
                        }
                    }
                }
            }
        }
    }
    cap_manager = get_cap_manager(providers)
    
    exports = {}
    final_conf = {"enabled_capabilities": {"db_cap": ["prov1"]}}
    
    injector.inject(compose_data, cap_manager, exports, final_conf)
    
    # check svc_list (which is converted to dict during merge)
    assert isinstance(compose_data["services"]["svc_list"]["environment"], dict)
    assert compose_data["services"]["svc_list"]["environment"]["EXISTING"] == "1"
    assert compose_data["services"]["svc_list"]["environment"]["NEW_VAR"] == "new_val"
    assert compose_data["services"]["svc_list"]["environment"]["DB_HOST"] == "db.example.com"

    # check svc_dict
    assert compose_data["services"]["svc_dict"]["environment"]["EXISTING"] == "2"
    assert compose_data["services"]["svc_dict"]["environment"]["NEW_VAR"] == "new_val"
    assert compose_data["services"]["svc_dict"]["environment"]["DB_HOST"] == "db.example.com"


def test_network_injection(jinja_env, global_conf):
    consumes = ["net_cap"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {
        "services": {
            "svc1": {},
            "svc2": {"networks": ["existing_net"]}
        }
    }
    
    providers = {
        "net_cap": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "networks": ["injected_net1", "injected_net2"]
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"net_cap": ["prov1"]}})
    
    assert "injected_net1" in compose_data["services"]["svc1"]["networks"]
    assert "injected_net2" in compose_data["services"]["svc1"]["networks"]
    assert "default" in compose_data["services"]["svc1"]["networks"]
    
    assert "existing_net" in compose_data["services"]["svc2"]["networks"]
    assert "injected_net1" in compose_data["services"]["svc2"]["networks"]
    assert "default" in compose_data["services"]["svc2"]["networks"]
    
    # Top level networks
    assert "networks" in compose_data
    assert "injected_net1" in compose_data["networks"]
    assert compose_data["networks"]["injected_net1"]["external"] is True
    assert compose_data["networks"]["injected_net1"]["name"] == "stegos_prov1_injected_net1"


def test_labels_injection(jinja_env, global_conf):
    consumes = ["label_cap"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {
        "services": {
            "svc_list": {
                "labels": ["org.example.label1=val1", "org.example.label2"]
            },
            "svc_dict": {
                "labels": {"org.example.label3": "val3"}
            }
        }
    }
    
    providers = {
        "label_cap": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "labels": {
                            "traefik.http.routers.{{ consumer.instance_name }}.rule": "Host(`{{ global_config.db_host }}`)",
                            "static_key": "static_val"
                        }
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"label_cap": ["prov1"]}})
    
    svc_list_labels = compose_data["services"]["svc_list"]["labels"]
    assert isinstance(svc_list_labels, dict)
    assert svc_list_labels["org.example.label1"] == "val1"
    assert svc_list_labels["org.example.label2"] == ""
    assert svc_list_labels["static_key"] == "static_val"
    assert svc_list_labels["traefik.http.routers.my_instance.rule"] == "Host(`db.example.com`)"

    svc_dict_labels = compose_data["services"]["svc_dict"]["labels"]
    assert svc_dict_labels["org.example.label3"] == "val3"
    assert svc_dict_labels["static_key"] == "static_val"
    assert svc_dict_labels["traefik.http.routers.my_instance.rule"] == "Host(`db.example.com`)"


def test_volumes_injection(jinja_env, global_conf):
    consumes = ["vol_cap"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {
        "services": {
            "svc1": {
                "volumes": ["./local:/container"]
            }
        }
    }
    
    providers = {
        "vol_cap": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "volumes": [
                            "/shared/data:/data",
                            "./local:/container"  # duplicate
                        ]
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"vol_cap": ["prov1"]}})
    
    volumes = compose_data["services"]["svc1"]["volumes"]
    assert len(volumes) == 2
    assert "./local:/container" in volumes
    assert "/shared/data:/data" in volumes


def test_target_services(jinja_env, global_conf, caplog):
    consumes = [{"name": "cap_target", "target_services": ["svc2"]}]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {
        "services": {
            "svc1": {},
            "svc2": {}
        }
    }
    
    providers = {
        "cap_target": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"TARGETED": "yes"}
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    
    with caplog.at_level(logging.WARNING):
        injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"cap_target": ["prov1"]}})
    
    assert "environment" not in compose_data["services"]["svc1"]
    assert compose_data["services"]["svc2"]["environment"]["TARGETED"] == "yes"
    
    # Test warning when no match
    consumes_nomatch = [{"name": "cap_nomatch", "target_services": ["svc3"]}]
    injector_nomatch = DockerComposeInjector(jinja_env, global_conf, consumes_nomatch, "my_instance")
    providers_nomatch = {
        "cap_nomatch": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"TARGETED": "yes"}
                    }
                }
            }
        }
    }
    cap_manager_nomatch = get_cap_manager(providers_nomatch)
    
    with caplog.at_level(logging.WARNING):
        injector_nomatch.inject(compose_data, cap_manager_nomatch, {}, {"enabled_capabilities": {"cap_nomatch": ["prov1"]}})
    
    assert "No matching target services found for injection" in caplog.text


def test_global_config_accessible(jinja_env, global_conf):
    # Already partially tested in env and labels, but we can do a dedicated test
    consumes = ["cap1"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {"services": {"svc1": {}}}
    
    providers = {
        "cap1": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"PORT": "{{ global_config.port }}"}
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"cap1": ["prov1"]}})
    
    assert compose_data["services"]["svc1"]["environment"]["PORT"] == "5432"


def test_consumer_instance_name_accessible(jinja_env, global_conf):
    consumes = ["cap1"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_awesome_instance")
    
    compose_data = {"services": {"svc1": {}}}
    
    providers = {
        "cap1": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"INSTANCE": "{{ consumer.instance_name }}"}
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {"cap1": ["prov1"]}})
    
    assert compose_data["services"]["svc1"]["environment"]["INSTANCE"] == "my_awesome_instance"


def test_namespaced_exports(jinja_env, global_conf):
    consumes = ["cap_a", "cap_b"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {"services": {"svc1": {}}}
    
    providers = {
        "cap_a": {
            "prov_a": {
                "injector": {
                    "docker-compose": {
                        "env": {"A_VAL": "{{ consumer.exports.a_key | default('miss') }}"}
                    }
                }
            }
        },
        "cap_b": {
            "prov_b": {
                "injector": {
                    "docker-compose": {
                        "env": {"B_VAL": "{{ consumer.exports.b_key | default('miss') }}"}
                    }
                }
            }
        }
    }
    
    exports_by_cap = {
        "cap_a": {"a_key": "val_a"},
        "cap_b": {"b_key": "val_b"}
    }
    
    cap_manager = get_cap_manager(providers)
    injector.inject(compose_data, cap_manager, exports_by_cap, {
        "enabled_capabilities": {"cap_a": ["prov_a"], "cap_b": ["prov_b"]}
    })
    
    # Cap A's provider sees its exports but shouldn't see Cap B's in `consumer.exports.b_key`
    # Well, `consumer.exports` maps to exports_by_cap.get(cap_name, {}) in the code.
    env = compose_data["services"]["svc1"]["environment"]
    assert env["A_VAL"] == "val_a"
    assert env["B_VAL"] == "val_b"


def test_multiple_capabilities(jinja_env, global_conf):
    consumes = ["cap1", "cap2"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {"services": {"svc1": {}}}
    
    providers = {
        "cap1": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"VAR1": "val1"}
                    }
                }
            }
        },
        "cap2": {
            "prov2": {
                "injector": {
                    "docker-compose": {
                        "env": {"VAR2": "val2"}
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    injector.inject(compose_data, cap_manager, {}, {
        "enabled_capabilities": {"cap1": ["prov1"], "cap2": ["prov2"]}
    })
    
    env = compose_data["services"]["svc1"]["environment"]
    assert env["VAR1"] == "val1"
    assert env["VAR2"] == "val2"


def test_noop_when_no_enabled_capabilities(jinja_env, global_conf):
    consumes = ["cap1"]
    injector = DockerComposeInjector(jinja_env, global_conf, consumes, "my_instance")
    
    compose_data = {"services": {"svc1": {"environment": {"EXISTING": "val"}}}}
    original_compose_data = {"services": {"svc1": {"environment": {"EXISTING": "val"}}}}
    
    providers = {
        "cap1": {
            "prov1": {
                "injector": {
                    "docker-compose": {
                        "env": {"SHOULD_NOT_EXIST": "val"}
                    }
                }
            }
        }
    }
    
    cap_manager = get_cap_manager(providers)
    
    # Empty enabled_capabilities
    injector.inject(compose_data, cap_manager, {}, {"enabled_capabilities": {}})
    
    assert compose_data == original_compose_data
