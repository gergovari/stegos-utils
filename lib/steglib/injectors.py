"""Capability injectors for dynamic template modification."""

class InjectorBase:
    """Base class for capability injectors."""
    
    def inject(self, compose_data, cap_manager, exports, final_conf):
        """Injects data into a parsed docker-compose structure.
        
        Args:
            compose_data (dict): The parsed docker-compose structure.
            cap_manager (CapabilityManager): Manager containing all capability providers.
            exports (dict): Resolved export variables from consumers.
            final_conf (dict): Final configuration of the consuming package.
        """
        raise NotImplementedError

class EnvVarInjector(InjectorBase):
    """Injects environment variables based on consumed capabilities."""
    
    def __init__(self, env):
        """Initializes the EnvVarInjector.
        
        Args:
            env (jinja2.Environment): Jinja2 environment for resolving templates.
        """
        self.env = env
        
    def inject(self, compose_data, cap_manager, exports, final_conf):
        """Injects environment variables into the compose services.
        
        Args:
            compose_data (dict): The parsed docker-compose structure.
            cap_manager (CapabilityManager): Manager containing all capability providers.
            exports (dict): Resolved export variables from consumers.
            final_conf (dict): Final configuration of the consuming package.
        """
        enabled_caps = final_conf.get("enabled_capabilities", {})
        injected_env = {}

        for cap_name, selected in enabled_caps.items():
            providers = cap_manager.get_providers(cap_name)
            if not isinstance(selected, list):
                selected = [selected]

            for prov_id in selected:
                if prov_id not in providers:
                    continue
                prov_info = providers[prov_id]
                injectors = prov_info.get("injector", {})
                dc_rules = injectors.get("docker-compose", {})
                for env_key, env_tmpl in dc_rules.get("env", {}).items():
                    tmpl = self.env.from_string(env_tmpl)
                    injected_env[env_key] = tmpl.render(
                        consumer={"config": final_conf, "exports": exports},
                    )

        if not injected_env:
            return

        services = compose_data.get("services", {})
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
                
            env = svc_data.get("environment", {})
            if isinstance(env, list):
                new_env = {}
                for e in env:
                    if "=" in e:
                        k, v = e.split("=", 1)
                        new_env[k] = v
                env = new_env
            
            for k, v in injected_env.items():
                env[k] = str(v)
            svc_data["environment"] = env

class NetworkInjector(InjectorBase):
    """Injects networks based on consumed capabilities."""
    
    def inject(self, compose_data, cap_manager, exports, final_conf):
        """Injects networks into the compose services.
        
        Args:
            compose_data (dict): The parsed docker-compose structure.
            cap_manager (CapabilityManager): Manager containing all capability providers.
            exports (dict): Resolved export variables from consumers.
            final_conf (dict): Final configuration of the consuming package.
        """
        enabled_caps = final_conf.get("enabled_capabilities", {})
        networks = []

        for cap_name, selected in enabled_caps.items():
            providers = cap_manager.get_providers(cap_name)
            if not isinstance(selected, list):
                selected = [selected]

            for prov_id in selected:
                if prov_id not in providers:
                    continue
                prov_info = providers[prov_id]
                dc_rules = prov_info.get("injector", {}).get("docker-compose", {})
                for net in dc_rules.get("networks", []):
                    if net not in networks:
                        networks.append(net)

        if not networks:
            return

        services = compose_data.get("services", {})
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
                
            svc_nets = svc_data.get("networks", [])
            if isinstance(svc_nets, dict):
                svc_nets = list(svc_nets.keys())
            if not isinstance(svc_nets, list):
                svc_nets = []
            
            for net in networks:
                if net not in svc_nets:
                    svc_nets.append(net)
                    
            if "default" not in svc_nets:
                svc_nets.append("default")
                
            svc_data["networks"] = svc_nets

        global_nets = compose_data.get("networks", {})
        if not isinstance(global_nets, dict):
            global_nets = {}
        for net in networks:
            if net not in global_nets:
                global_nets[net] = {"external": True}
        compose_data["networks"] = global_nets
