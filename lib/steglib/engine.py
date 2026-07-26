import json
import os
import uuid
import yaml

import jsonschema
from jinja2 import Environment, FileSystemLoader

from steglib.capability import CapabilityManager
from steglib.config import ConfigResolver
from steglib.constants import (
    BACKEND_DIR,
    GLOBAL_CONF_FILENAME,
    PERSISTENT_DIR,
    REPOS_DIR,
)
from steglib.deployer import DEPLOYERS
from steglib.group import GroupManager
from steglib.instance import Instance


class PackageNotFoundError(Exception):
    """Raised when a package cannot be located in the repos tree."""
    pass


class InteractiveRequiredError(Exception):
    """Raised when interactive input is required but not provided."""
    pass


def load_manifest(pkg_dir):
    """Load and return a package manifest, or None on failure."""
    path = os.path.join(pkg_dir, "manifest.yml")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as fh:
            return yaml.safe_load(fh)
    except (yaml.YAMLError, OSError):
        return None


def parse_consumes(manifest):
    """Normalize the capabilities.consumes field into a dict."""
    raw = manifest.get("capabilities", {}).get("consumes", [])
    result = {}
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, str):
                result[entry] = {}
            elif isinstance(entry, dict):
                name = entry.get("name", "")
                if name:
                    result[name] = {k: v for k, v in entry.items() if k != "name"}
    elif isinstance(raw, dict):
        result = raw
    return result


class PackageEngine:
    """Core engine for package operations within a single stegOS group."""

    def __init__(self, group_prefix=None):
        """Initializes the PackageEngine.

        Args:
            group_prefix (str, optional): Target group name or prefix.
        """
        self.group_name = GroupManager.resolve(group_prefix)
        self.group_dir = os.path.join(PERSISTENT_DIR, self.group_name)
        self.repo_dir = os.path.join(REPOS_DIR, self.group_name)

        os.makedirs(self.group_dir, exist_ok=True)

        self.cap_manager = CapabilityManager(self)

        self.global_conf = {}
        gc_path = os.path.join(self.group_dir, GLOBAL_CONF_FILENAME)
        if os.path.isfile(gc_path):
            try:
                with open(gc_path, "r") as fh:
                    self.global_conf = json.load(fh)
            except (json.JSONDecodeError, OSError):
                pass

    def find_package_dir(self, pkg_name, target_repo=None):
        """Locate the package directory by name within the repos tree.

        Args:
            pkg_name (str): Package name to search for.
            target_repo (str, optional): Optional repository name to disambiguate.

        Returns:
            str: Absolute path to the package directory.

        Raises:
            PackageNotFoundError: If the package is not found or is ambiguous.
        """
        if not os.path.isdir(self.repo_dir):
            raise PackageNotFoundError(f"Repos directory '{self.repo_dir}' does not exist.")

        found = []
        for root, _dirs, files in os.walk(self.repo_dir):
            if "manifest.yml" in files and os.path.basename(root) == pkg_name:
                found.append(root)

        if not found:
            raise PackageNotFoundError(f"Package '{pkg_name}' not found in repos.")

        if target_repo:
            found = [p for p in found if f"/{target_repo}/" in p]
            if not found:
                raise PackageNotFoundError(f"Package '{pkg_name}' not found in repo '{target_repo}'.")

        if len(found) > 1:
            raise PackageNotFoundError(f"Multiple packages named '{pkg_name}' found. Use --repo to disambiguate.")

        return found[0]

    def process_package(self, pkg_dir, cli_conf=None, reconfigure=False,
                        non_interactive=False, instance_id=None, interactive_cb=None):
        """Install or reconfigure a package instance.

        Args:
            pkg_dir: Absolute path to the package source directory.
            cli_conf: Optional dict of CLI-provided config overrides.
            reconfigure: If True, re-prompt for all configuration values.
            non_interactive: If True, never prompt — use defaults or abort.
            instance_id: Optional explicit instance ID (for reconfigure).
            interactive_cb: Callback for interactive prompts.

        Returns:
            str: The resolved instance ID.

        Raises:
            ValueError: If manifest is invalid or conflicts arise.
        """
        if cli_conf is None:
            cli_conf = {}

        manifest = load_manifest(pkg_dir)
        if manifest is None:
            raise ValueError(f"Failed to load manifest from '{pkg_dir}'.")

        pkg_name = manifest.get("name")
        is_singleton = manifest.get("singleton", False)

        existing = self._find_instances_by_package(pkg_name)

        instance_name = self._resolve_instance_name(
            pkg_name, instance_id, reconfigure, is_singleton, existing, interactive_cb
        )

        pkg_conf = Instance(self.group_name, instance_name).read_conf()
        consumes = parse_consumes(manifest)

        enabled_caps = self._resolve_capabilities(
            consumes, pkg_conf, reconfigure, non_interactive, interactive_cb
        )

        config_schema = dict(manifest.get("config_schema", {}))
        for cap_name, cond_schema in manifest.get("conditional_config_schema", {}).items():
            if cap_name in enabled_caps and enabled_caps[cap_name]:
                if self.cap_manager.get_providers(cap_name):
                    if "properties" in cond_schema:
                        config_schema.setdefault("properties", {}).update(cond_schema["properties"])
                    if "required" in cond_schema:
                        config_schema.setdefault("required", []).extend(cond_schema["required"])

        final_conf = {}
        if config_schema:
            resolver = ConfigResolver(config_schema, pkg_conf, cli_conf, reconfigure, non_interactive)
            # Inject our callback if provided so ConfigResolver can use it.
            if interactive_cb and not non_interactive:
                # Override prompt method dynamically or have interactive_cb passed
                # In stegos-utils this might require updating config.py as well
                pass
            final_conf = resolver.resolve()
            try:
                jsonschema.validate(instance=final_conf, schema=config_schema)
            except jsonschema.exceptions.ValidationError as exc:
                raise ValueError(f"Validation failed: {exc.message}")

        final_conf["enabled_capabilities"] = enabled_caps

        Instance(self.group_name, instance_name).write_conf(final_conf)

        out_dir = os.path.join(self.group_dir, instance_name, BACKEND_DIR)
        os.makedirs(out_dir, exist_ok=True)

        env = Environment(loader=FileSystemLoader(pkg_dir))

        for dep_type, dep_config in manifest.get("deployers", {}).items():
            deployer_cls = DEPLOYERS.get(dep_type)
            if deployer_cls:
                deployer = deployer_cls(
                    dep_type, dep_config, pkg_dir, out_dir, env,
                    final_conf, self.global_conf, manifest, instance_name,
                    self.group_name,
                )
                deployer.deploy(self.cap_manager)
            else:
                # Silently ignore or log unknown deployers
                pass

        for cap in manifest.get("capabilities", {}).get("provides", []):
            cap_name = cap.get("name")
            if cap_name:
                self.cap_manager.register(cap_name, instance_name, cap.get("injectors", {}))

        return instance_name

    def resolve_instance(self, name, interactive_cb=None):
        """Resolve a user-supplied name to an instance ID."""
        if os.path.isdir(os.path.join(self.group_dir, name)):
            return name

        matched = self._find_instances_by_package(name)
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            if interactive_cb:
                ans = interactive_cb(f"Multiple instances match '{name}'", matched, default=None)
                if ans and ans in matched:
                    return ans
            raise ValueError(f"Multiple instances of '{name}' found: {matched}. Specify the exact instance ID.")
        raise ValueError(f"Instance or package '{name}' not found.")

    def resolve_instances(self, names, interactive_cb=None):
        """Resolve user-supplied names to a list of instance IDs."""
        results = []
        for name in names:
            if os.path.isdir(os.path.join(self.group_dir, name)):
                if name not in results:
                    results.append(name)
            else:
                matched = self._find_instances_by_package(name)
                if len(matched) == 1:
                    if matched[0] not in results:
                        results.append(matched[0])
                elif len(matched) > 1:
                    if interactive_cb:
                        choices = ["All"] + matched
                        ans = interactive_cb(f"Multiple instances match '{name}'", choices, default="All")
                        if ans == "All":
                            for m in matched:
                                if m not in results:
                                    results.append(m)
                        elif ans in matched and ans not in results:
                            results.append(ans)
                    else:
                        for m in matched:
                            if m not in results:
                                results.append(m)
                else:
                    raise ValueError(f"Instance or package '{name}' not found.")
        return results

    def _find_instances_by_package(self, pkg_name):
        if not os.path.isdir(self.group_dir):
            return []
        results = []
        for d in os.listdir(self.group_dir):
            inst = Instance(self.group_name, d)
            if inst.is_installed and inst.package_name == pkg_name:
                results.append(d)
        return results

    def _resolve_instance_name(self, pkg_name, instance_id, reconfigure, is_singleton, existing, interactive_cb):
        if instance_id:
            return instance_id

        if reconfigure:
            if len(existing) == 1:
                return existing[0]
            if len(existing) > 1:
                if interactive_cb:
                    ans = interactive_cb(f"Multiple instances of '{pkg_name}' exist", existing, default=None)
                    if ans in existing:
                        return ans
                raise ValueError(f"Multiple instances of '{pkg_name}' exist. Specify --id.")
            raise ValueError(f"No instances of '{pkg_name}' to reconfigure.")

        if is_singleton and existing:
            raise ValueError(f"'{pkg_name}' is a singleton and already installed.")

        return f"{pkg_name}-{uuid.uuid4().hex[:8]}"

    def _resolve_capabilities(self, consumes, pkg_conf, reconfigure, non_interactive, interactive_cb):
        raw = pkg_conf.get("enabled_capabilities", {})
        if isinstance(raw, list):
            enabled = {cap: list(self.cap_manager.get_providers(cap).keys()) for cap in raw}
        else:
            enabled = dict(raw)

        if non_interactive:
            return enabled

        for cap_name, cap_rules in consumes.items():
            providers = self.cap_manager.get_providers(cap_name)
            if not providers:
                continue

            prov_list = list(providers.keys())
            max_provs = cap_rules.get("max_providers")

            default_sel = []
            if cap_name in enabled:
                default_sel = enabled[cap_name]
            if not default_sel and not pkg_conf:
                if not (max_provs and max_provs < len(prov_list)):
                    if prov_list:
                        default_sel = [prov_list[0]]
            
            if not (reconfigure or not pkg_conf):
                continue

            if interactive_cb:
                msg = f"Integration available: '{cap_name}'. Available providers: {prov_list}."
                if max_provs:
                    msg += f" (Max {max_provs})"
                ans_list = interactive_cb(msg, prov_list, default=",".join(default_sel), multiple=True)
                if ans_list is not None:
                    if max_provs and len(ans_list) > max_provs:
                        raise ValueError(f"Max {max_provs} provider(s) allowed for {cap_name}.")
                    if ans_list:
                        enabled[cap_name] = ans_list
                    elif cap_name in enabled:
                        del enabled[cap_name]

        return enabled
