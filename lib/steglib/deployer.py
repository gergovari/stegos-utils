"""Deployer models for stegOS packages."""

import os
import shutil
import yaml

from .injectors import DockerComposeInjector

class DeployerBase:
    """Abstract base class for package deployers.
    
    Deployers are responsible for preparing a package instance's backend
    directory, which typically involves copying templates, resolving variables,
    and rendering configuration files (like docker-compose.yml).
    """

    def __init__(self, name, config, pkg_dir, out_dir, env,
                 final_conf, global_conf, manifest, instance_name,
                 group_name=None):
        """Initializes the Deployer.
        
        Args:
            name (str): Name of the deployer type (e.g., 'docker-compose').
            config (dict): Deployer-specific configuration from the manifest.
            pkg_dir (str): Absolute path to the package source directory.
            out_dir (str): Absolute path to the instance's backend output directory.
            env (jinja2.Environment): Jinja2 environment configured for the package.
            final_conf (dict): Final resolved configuration for the instance.
            global_conf (dict): Global group configuration.
            manifest (dict): The complete package manifest.
            instance_name (str): The unique ID of the instance.
            group_name (str, optional): The name of the stegOS group.
        """
        self.name = name
        self.config = config
        self.pkg_dir = pkg_dir
        self.out_dir = out_dir
        self.env = env
        self.final_conf = final_conf
        self.global_conf = global_conf
        self.manifest = manifest
        self.instance_name = instance_name
        self.group_name = group_name or os.path.basename(
            os.path.dirname(os.path.dirname(os.path.normpath(out_dir)))
        )

    def deploy(self, cap_manager):
        """Deploys the package instance. Subclasses must implement this.
        
        Args:
            cap_manager (CapabilityManager): The capability manager used to resolve integrations.
        """
        raise NotImplementedError

    def _process_skeleton(self, skeletons):
        """Copies skeleton directory trees into the output directory.
        
        Args:
            skeletons (list): List of skeleton dicts specifying 'src' and 'dest'.
        """
        for skel in skeletons:
            src = skel.get("src")
            dest = skel.get("dest", "./")
            if not src:
                continue
            src_path = os.path.join(self.pkg_dir, src)
            if not os.path.isdir(src_path):
                print(f"Warning: Skeleton source '{src}' not found.")
                continue
            dest_base = os.path.normpath(os.path.join(self.out_dir, dest))
            if not dest_base.startswith(self.out_dir):
                continue
            for root, _dirs, files in os.walk(src_path):
                rel_dir = os.path.relpath(root, src_path)
                target_dir = dest_base if rel_dir == "." else os.path.join(dest_base, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                for fname in files:
                    target_file = os.path.join(target_dir, fname)
                    if not os.path.exists(target_file):
                        shutil.copy2(os.path.join(root, fname), target_file)


class DockerComposeDeployer(DeployerBase):
    """Deploys packages via docker-compose template rendering."""

    def deploy(self, cap_manager):
        """Renders templates, copies files, and injects capabilities.
        
        Args:
            cap_manager (CapabilityManager): The capability manager to resolve integrations.
        """
        # Process skeletons first.
        skeletons = self.config.get("skeleton", [])
        if skeletons:
            self._process_skeleton(skeletons)

        # Resolve exports.
        exports = self._resolve_exports()

        # Render templates and inject capabilities.
        self._render_templates(cap_manager, exports)

        # Copy static files.
        self._copy_files()

    def _resolve_exports(self):
        """Resolves configuration exports from consumed capabilities.

        Returns a dict-of-dicts keyed by capability name so that provider
        injector templates can reference their own capability's exports
        without collision.

        Returns:
            dict: ``{cap_name: {export_key: resolved_value}}``.
        """
        exports_by_cap = {}
        consumes = self.manifest.get("capabilities", {}).get("consumes", [])
        for entry in consumes:
            if not isinstance(entry, dict):
                continue
            cap_name = entry.get("name", "")
            if not cap_name:
                continue
            cap_exports = {}
            for key, value in entry.get("exports", {}).items():
                if isinstance(value, str):
                    tmpl = self.env.from_string(value)
                    stegos_env = {
                        "group_name": self.group_name,
                        "docker_sock": f"/stegos/persistent/{self.group_name}/backend/dockerd/docker.sock"
                    }
                    cap_exports[key] = tmpl.render(
                        config=self.final_conf,
                        global_config=self.global_conf,
                        stegos=stegos_env,
                    )
                else:
                    cap_exports[key] = value
            exports_by_cap[cap_name] = cap_exports
        return exports_by_cap

    def _render_templates(self, cap_manager, exports_by_cap):
        """Renders Jinja2 templates and writes them to the output directory.

        Args:
            cap_manager (CapabilityManager): The capability manager.
            exports_by_cap (dict): ``{cap_name: {export_key: value}}``.
        """
        templates = self.config.get("templates", [
            {"src": "docker-compose.yml.j2", "dest": "docker-compose.yml"},
        ])

        consumes = self.manifest.get("capabilities", {}).get("consumes", [])
        injector = DockerComposeInjector(
            self.env, self.global_conf, consumes, self.instance_name,
        )

        for entry in templates:
            src = entry.get("src")
            dest = entry.get("dest")
            if not (src and dest):
                continue
            src_path = os.path.join(self.pkg_dir, src)
            if not os.path.exists(src_path):
                print(f"Warning: Template '{src}' not found in package.")
                continue

            with open(src_path, "r") as fh:
                content = fh.read()

            tmpl = self.env.from_string(content)
            stegos_env = {
                "group_name": self.group_name,
                "docker_sock": f"/stegos/persistent/{self.group_name}/backend/dockerd/docker.sock"
            }
            rendered = tmpl.render(
                config=self.final_conf,
                global_config=self.global_conf,
                stegos=stegos_env,
            )

            if dest == "docker-compose.yml":
                try:
                    compose_data = yaml.safe_load(rendered)
                    if not isinstance(compose_data, dict):
                        compose_data = {}

                    injector.inject(
                        compose_data, cap_manager, exports_by_cap, self.final_conf,
                    )

                    # Rewrite provider networks to be scoped and external to avoid naming conflicts
                    for cap in self.manifest.get("capabilities", {}).get("provides", []):
                        for net_name in cap.get("injectors", {}).get("docker-compose", {}).get("networks", []):
                            if "networks" in compose_data and net_name in compose_data["networks"]:
                                scoped_name = f"{self.group_name}_{self.instance_name}_{net_name}"
                                compose_data["networks"][net_name] = {
                                    "external": True,
                                    "name": scoped_name
                                }

                    rendered = yaml.dump(compose_data, default_flow_style=False, sort_keys=False)
                except Exception as e:
                    print(f"Warning: Failed to dynamically inject capabilities into {dest}: {e}")

            dest_path = os.path.join(self.out_dir, os.path.normpath(dest))
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "w") as fh:
                fh.write(rendered)
                fh.flush()
                os.fsync(fh.fileno())

    def _copy_files(self):
        """Copies static files from the package directory to the output directory."""
        for entry in self.config.get("files", []):
            src = entry.get("src")
            dest = entry.get("dest")
            if not (src and dest):
                continue
            src_path = os.path.join(self.pkg_dir, src)
            if not os.path.exists(src_path):
                print(f"Warning: File '{src}' not found in package.")
                continue
            dest_path = os.path.join(self.out_dir, os.path.normpath(dest))
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            shutil.copy2(src_path, dest_path)

DEPLOYERS = {
    "docker-compose": DockerComposeDeployer,
}
