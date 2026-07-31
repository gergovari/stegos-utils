"""Capability injectors for dynamic docker-compose modification."""

import logging

logger = logging.getLogger(__name__)


class DockerComposeInjector:
    """Unified injector that handles all docker-compose field merges.

    Replaces the separate EnvVarInjector and NetworkInjector with a single
    class that handles env, networks, labels, and volumes using per-field
    merge strategies.
    """

    def __init__(self, jinja_env, global_conf, consumes, instance_name, group_name="stegos"):
        """Initializes the DockerComposeInjector.

        Args:
            jinja_env (jinja2.Environment): Jinja2 environment for resolving templates.
            global_conf (dict): Global group configuration.
            consumes (list): Capabilities consumed by this instance.
            instance_name (str): Instance ID of the consumer.
            group_name (str): The group name this instance belongs to.
        """
        self.jinja_env = jinja_env
        self.global_conf = global_conf
        self.instance_name = instance_name
        self.group_name = group_name

        # Build a lookup: {cap_name: consumes_entry_dict}
        self._consumes_map = {}
        if isinstance(consumes, list):
            for entry in consumes:
                if isinstance(entry, dict):
                    name = entry.get("name", "")
                    if name:
                        self._consumes_map[name] = entry
                elif isinstance(entry, str):
                    self._consumes_map[entry] = {}

    def inject(self, compose_data, cap_manager, exports_by_cap, final_conf):
        """Injects capability-provided fields into the compose structure.

        Args:
            compose_data (dict): The parsed docker-compose structure.
            cap_manager: CapabilityManager with registered providers.
            exports_by_cap (dict): ``{cap_name: {export_key: value}}``.
            final_conf (dict): Final configuration of the consuming package.
        """
        enabled_caps = final_conf.get("enabled_capabilities", {})

        for cap_name, selected in enabled_caps.items():
            providers = cap_manager.get_providers(cap_name)
            if not isinstance(selected, list):
                selected = [selected]

            consumes_entry = self._consumes_map.get(cap_name, {})
            target_services = consumes_entry.get("target_services")
            cap_exports = exports_by_cap.get(cap_name, {})

            render_ctx = {
                "consumer": {
                    "config": final_conf,
                    "exports": cap_exports,
                    "instance_name": self.instance_name,
                },
                "global_config": self.global_conf,
            }

            for prov_id in selected:
                if prov_id not in providers:
                    continue
                prov_info = providers[prov_id]
                dc_rules = prov_info.get("injector", {}).get("docker-compose", {})
                if not dc_rules:
                    continue

                self._apply_rules(compose_data, dc_rules, render_ctx, target_services, prov_id)

    def _apply_rules(self, compose_data, dc_rules, render_ctx, target_services, prov_id):
        """Applies all docker-compose injection rules.

        Args:
            compose_data (dict): The parsed docker-compose structure.
            dc_rules (dict): The provider's docker-compose injector rules.
            render_ctx (dict): Jinja2 template rendering context.
            target_services (list or None): Services to target, or None for all.
            prov_id (str): The instance ID of the capability provider.
        """
        services = compose_data.get("services", {})
        targeted = self._resolve_targets(services, target_services)

        if not targeted:
            logger.warning(
                "No matching target services found for injection "
                "(target_services=%s, available=%s).",
                target_services,
                list(services.keys()),
            )
            return

        # --- env (dict → service.environment) ---
        env_rules = dc_rules.get("env", {})
        if env_rules:
            rendered_env = {}
            for env_key, env_tmpl in env_rules.items():
                rendered_env[env_key] = self._render(env_tmpl, render_ctx)
            for svc_name in targeted:
                self._merge_env(services[svc_name], rendered_env)

        # --- networks (list → service.networks + top-level) ---
        network_rules = dc_rules.get("networks", [])
        if network_rules:
            for svc_name in targeted:
                self._merge_networks(services[svc_name], network_rules, self.group_name, prov_id)
            self._ensure_top_level_networks(compose_data, network_rules, self.group_name, prov_id)

        # --- labels (dict → service.labels, template keys AND values) ---
        label_rules = dc_rules.get("labels", {})
        if label_rules:
            rendered_labels = {}
            for label_key, label_val in label_rules.items():
                rk = self._render(label_key, render_ctx)
                rv = self._render(str(label_val), render_ctx)
                rendered_labels[rk] = rv
            for svc_name in targeted:
                self._merge_labels(services[svc_name], rendered_labels)

        # --- volumes (list → service.volumes, append unique) ---
        volume_rules = dc_rules.get("volumes", [])
        if volume_rules:
            rendered_volumes = [self._render(v, render_ctx) for v in volume_rules]
            for svc_name in targeted:
                self._merge_volumes(services[svc_name], rendered_volumes)

    def _resolve_targets(self, services, target_services):
        """Resolves which services should be targeted for injection.

        Args:
            services (dict): The services dict from docker-compose.
            target_services (list or None): Explicit targets, or None for all.

        Returns:
            list: Service names to inject into.
        """
        if target_services is None:
            return list(services.keys())
        return [s for s in target_services if s in services]

    def _render(self, template_str, ctx):
        """Renders a Jinja2 template string with the given context.

        Args:
            template_str (str): The template string.
            ctx (dict): The rendering context.

        Returns:
            str: The rendered string.
        """
        if not isinstance(template_str, str):
            return str(template_str)
        tmpl = self.jinja_env.from_string(template_str)
        return tmpl.render(**ctx)

    # -- Merge strategies ---------------------------------------------------

    @staticmethod
    def _merge_env(svc_data, rendered_env):
        """Merges environment variables into a service.

        Args:
            svc_data (dict): The service's compose definition.
            rendered_env (dict): Key-value pairs to merge.
        """
        env = svc_data.get("environment", {})
        if isinstance(env, list):
            new_env = {}
            for e in env:
                if "=" in e:
                    k, v = e.split("=", 1)
                    new_env[k] = v
            env = new_env

        for k, v in rendered_env.items():
            env[k] = str(v)
        svc_data["environment"] = env

    @staticmethod
    def _merge_networks(svc_data, networks, group_name, prov_id):
        """Merges networks into a service and ensures 'default' is present.

        Args:
            svc_data (dict): The service's compose definition.
            networks (list): Network names to add.
            group_name (str): The group name.
            prov_id (str): The provider instance ID.
        """
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

    @staticmethod
    def _ensure_top_level_networks(compose_data, networks, group_name, prov_id):
        """Ensures injected networks are declared as external at top level.

        Args:
            compose_data (dict): The full docker-compose structure.
            networks (list): Network names to declare.
            group_name (str): The group name.
            prov_id (str): The provider instance ID.
        """
        global_nets = compose_data.get("networks", {})
        if not isinstance(global_nets, dict):
            global_nets = {}
        for net in networks:
            scoped_name = f"{group_name}_{prov_id}_{net}"
            if net not in global_nets:
                global_nets[net] = {
                    "external": True,
                    "name": scoped_name
                }
        compose_data["networks"] = global_nets

    @staticmethod
    def _merge_labels(svc_data, rendered_labels):
        """Merges labels into a service.

        Handles both dict and list label formats in the compose file.

        Args:
            svc_data (dict): The service's compose definition.
            rendered_labels (dict): Key-value label pairs to merge.
        """
        labels = svc_data.get("labels", {})
        if isinstance(labels, list):
            new_labels = {}
            for entry in labels:
                if isinstance(entry, str) and "=" in entry:
                    k, v = entry.split("=", 1)
                    new_labels[k] = v
                elif isinstance(entry, str):
                    new_labels[entry] = ""
            labels = new_labels

        for k, v in rendered_labels.items():
            labels[k] = str(v)
        svc_data["labels"] = labels

    @staticmethod
    def _merge_volumes(svc_data, rendered_volumes):
        """Appends unique volume entries to a service.

        Args:
            svc_data (dict): The service's compose definition.
            rendered_volumes (list): Volume strings to append.
        """
        volumes = svc_data.get("volumes", [])
        if not isinstance(volumes, list):
            volumes = []

        for vol in rendered_volumes:
            if vol not in volumes:
                volumes.append(vol)
        svc_data["volumes"] = volumes
