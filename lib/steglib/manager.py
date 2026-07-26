import json
import logging
import os
import re
import shutil
import subprocess

from steglib.constants import BACKEND_DIR, GLOBAL_CONF_FILENAME
from steglib.engine import PackageNotFoundError
from steglib.instance import Instance

logger = logging.getLogger(__name__)


class PackageManager:
    """High-level package manager bridging the engine and CLI/API."""

    def __init__(self, engine):
        """Initializes the PackageManager.

        Args:
            engine: The PackageEngine instance to use.
        """
        self.engine = engine

    def install(self, packages, repo=None, config_file=None, reconfigure=False,
                non_interactive=False, instance_id=None, interactive_cb=None):
        """Installs one or more packages."""
        if instance_id and len(packages) > 1:
            raise ValueError("--id cannot be used when installing multiple packages.")

        seen = []
        for pkg in packages:
            if not re.match(r"^[a-zA-Z0-9.\-_]+$", pkg):
                raise ValueError(f"Invalid package name '{pkg}'. Must be alphanumeric, dots, dashes, or underscores.")
            if pkg in seen:
                continue
            seen.append(pkg)

            pkg_dir = self.engine.find_package_dir(pkg, repo)
            cli_conf = {}
            if config_file:
                with open(config_file, "r") as fh:
                    cli_conf = json.load(fh)
            
            inst_id = self.engine.process_package(
                pkg_dir, cli_conf, reconfigure, non_interactive, instance_id, interactive_cb
            )
            display_name = inst_id if inst_id else (instance_id if instance_id else pkg)
            logger.info("Successfully installed %s as %s!", pkg, display_name)

    def reconfigure(self, instance_ids=None, interactive_cb=None):
        """Reconfigures one or more instances."""
        if instance_ids:
            instances = self.engine.resolve_instances(instance_ids, interactive_cb)
        else:
            instances = os.listdir(self.engine.group_dir) if os.path.isdir(self.engine.group_dir) else []

        count = 0
        for instance_id in instances:
            inst = Instance(self.engine.group_name, instance_id)
            if not inst.is_installed:
                continue
            pkg_name = inst.package_name
            if not pkg_name:
                continue
            try:
                pkg_dir = self.engine.find_package_dir(pkg_name)
                is_interactive = bool(instance_ids) and not interactive_cb
                self.engine.process_package(
                    pkg_dir, cli_conf={}, reconfigure=is_interactive,
                    non_interactive=not is_interactive, instance_id=instance_id,
                    interactive_cb=interactive_cb
                )
                count += 1
            except PackageNotFoundError:
                logger.warning("Could not reconfigure '%s' (instance '%s').", pkg_name, instance_id)
        
        logger.info("Successfully reconfigured %d instance(s) in group '%s'.", count, self.engine.group_name)

    def remove(self, instance_ids, purge=False, cascade=False, interactive_cb=None):
        """Removes one or more package instances."""
        real_ids = self.engine.resolve_instances(instance_ids, interactive_cb)

        deps = self._find_dependents(real_ids)
        if deps:
            all_dependents = []
            for provider_id, dependents in deps.items():
                logger.warning("'%s' is used by: %s", provider_id, ", ".join(dependents))
                for d in dependents:
                    if d not in all_dependents:
                        all_dependents.append(d)

            if cascade:
                ans = "y"
            elif interactive_cb:
                ans = interactive_cb(
                    "Reconfigure these instances to remove the integration and restart?",
                    ["y", "n"], default="n"
                )
            else:
                raise ValueError(f"Cannot remove instances with active dependents: {all_dependents}")

            if ans.lower() == "y":
                for dep_id in all_dependents:
                    self._cascade_remove_integration(dep_id, real_ids)
            else:
                raise RuntimeError("Aborting removal due to active dependents.")

        for real_id in real_ids:
            logger.info("Stopping instance '%s'...", real_id)
            try:
                from steglib.lifecycle import LifecycleManager
                lm = LifecycleManager(self.engine.group_name)
                lm.execute("stop", real_id, False, False)
            except Exception:
                logger.warning("Failed to stop instance cleanly. Proceeding with removal...")

            instance_dir = os.path.join(self.engine.group_dir, real_id)

            if purge:
                if os.path.exists(instance_dir):
                    shutil.rmtree(instance_dir)
                logger.info("Removed '%s' and all persistent data.", real_id)
            else:
                backend_dir = os.path.join(instance_dir, BACKEND_DIR)
                for fname in [".stegpkg-state.json", "docker-compose.yml"]:
                    fpath = os.path.join(backend_dir, fname)
                    if os.path.exists(fpath):
                        os.remove(fpath)
                logger.info("Uninstalled '%s'. Config and data preserved.", real_id)

    def upgrade(self, instance_ids=None, interactive_cb=None):
        """Upgrades one or more instances."""
        if instance_ids:
            instances = self.engine.resolve_instances(instance_ids, interactive_cb)
        else:
            instances = os.listdir(self.engine.group_dir) if os.path.isdir(self.engine.group_dir) else []

        count = 0
        for instance_id in instances:
            inst = Instance(self.engine.group_name, instance_id)
            if not inst.is_installed:
                continue
            pkg_name = inst.package_name
            if not pkg_name:
                continue
            try:
                pkg_dir = self.engine.find_package_dir(pkg_name)
                self.engine.process_package(
                    pkg_dir, cli_conf={}, reconfigure=False,
                    non_interactive=True, instance_id=instance_id,
                )
                logger.info("[%s] Ensuring instance is up to date...", instance_id)
                from steglib.lifecycle import LifecycleManager
                lm = LifecycleManager(self.engine.group_name)
                lm.execute("start", instance_id, True, False)
                count += 1
            except Exception as exc:
                logger.warning("Could not upgrade '%s' (instance '%s'): %s", pkg_name, instance_id, exc)
        
        logger.info("Upgraded %d instance(s) in group '%s'.", count, self.engine.group_name)

    def update(self):
        """Updates app repositories via git pull."""
        if not os.path.isdir(self.engine.repo_dir):
            raise FileNotFoundError(f"Repos directory '{self.engine.repo_dir}' does not exist.")

        count = 0
        for name in os.listdir(self.engine.repo_dir):
            repo_path = os.path.join(self.engine.repo_dir, name)
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                logger.info("[%s] Skipping (not a git repository).", name)
                continue
            logger.info("[%s] Pulling from remote...", name)
            try:
                subprocess.run(
                    ["git", "config", "--global", "--add", "safe.directory", repo_path],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "pull", "--rebase", "--autostash"],
                    cwd=repo_path, check=True,
                )
                count += 1
            except subprocess.CalledProcessError:
                logger.warning("Failed to update '%s'.", name)
        logger.info("Updated %d repository(ies).", count)

    def list_packages(self):
        """Lists installed packages."""
        if not os.path.isdir(self.engine.group_dir):
            logger.info("No packages installed in group '%s'.", self.engine.group_name)
            return

        logger.info("Installed packages in group '%s':", self.engine.group_name)
        count = 0
        for instance_id in sorted(os.listdir(self.engine.group_dir)):
            inst = Instance(self.engine.group_name, instance_id)
            if not inst.is_installed:
                continue
            pkg_name = inst.package_name or "unknown"
            logger.info("  - %s (Package: %s)", instance_id, pkg_name)
            count += 1

        if count == 0:
            logger.info("  (none)")

    def clean(self, auto_confirm=False, interactive_cb=None):
        """Removes unmanaged instance directories."""
        if not os.path.isdir(self.engine.group_dir):
            logger.info("Group directory '%s' does not exist.", self.engine.group_dir)
            return

        unmanaged = []
        for name in os.listdir(self.engine.group_dir):
            if name in [GLOBAL_CONF_FILENAME, ".docker-cache"]:
                continue
            path = os.path.join(self.engine.group_dir, name)
            if not os.path.isdir(path):
                continue
            
            if not Instance(self.engine.group_name, name).is_installed:
                unmanaged.append(path)

        if not unmanaged:
            logger.info("No unmanaged directories found in group '%s'.", self.engine.group_name)
            return

        logger.info("Found unmanaged directories:")
        for path in unmanaged:
            logger.info("  - %s", path)

        if auto_confirm:
            ans = "y"
        elif interactive_cb:
            ans = interactive_cb("Delete these directories permanently?", ["y", "n"], default="n")
        else:
            raise ValueError("Auto-confirm not specified and no interactive handler available.")

        if ans.lower() == "y":
            count = 0
            for path in unmanaged:
                try:
                    shutil.rmtree(path)
                    logger.info("Deleted %s", path)
                    count += 1
                except OSError as e:
                    logger.warning("Failed to delete %s: %s", path, e)
            logger.info("Successfully cleaned %d directory(ies).", count)
        else:
            logger.info("Aborted.")

    def _find_dependents(self, target_ids):
        """Find instances that depend on any of target_ids via capabilities."""
        deps = {}
        if not os.path.isdir(self.engine.group_dir):
            return deps

        for d in os.listdir(self.engine.group_dir):
            if d in target_ids:
                continue
            inst = Instance(self.engine.group_name, d)
            if not inst.is_installed:
                continue
            conf = inst.read_conf()
            if not conf:
                continue
            for _cap, provs in conf.get("enabled_capabilities", {}).items():
                if isinstance(provs, list):
                    for p in provs:
                        if p in target_ids:
                            deps.setdefault(p, []).append(d)
                elif provs in target_ids:
                    deps.setdefault(provs, []).append(d)
        return deps

    def _cascade_remove_integration(self, dep_id, removed_ids):
        """Reconfigure a dependent instance to drop integrations to removed IDs."""
        logger.info("[%s] Reconfiguring to remove integrations...", dep_id)
        inst = Instance(self.engine.group_name, dep_id)
        conf = inst.read_conf()
        enabled = conf.get("enabled_capabilities", {})

        for cap, provs in list(enabled.items()):
            if isinstance(provs, list):
                new = [p for p in provs if p not in removed_ids]
                if not new:
                    del enabled[cap]
                else:
                    enabled[cap] = new
            elif provs in removed_ids:
                del enabled[cap]

        inst.write_conf(conf)

        if inst.is_installed:
            pkg_name = inst.package_name
            if pkg_name:
                try:
                    pkg_dir = self.engine.find_package_dir(pkg_name)
                    self.engine.process_package(
                        pkg_dir, cli_conf={}, reconfigure=False,
                        non_interactive=True, instance_id=dep_id,
                    )
                    logger.info("[%s] Restarting...", dep_id)
                    from steglib.lifecycle import LifecycleManager
                    lm = LifecycleManager(self.engine.group_name)
                    lm.execute("start", dep_id, False, False)
                except Exception:
                    logger.warning("Failed to reconfigure '%s'.", dep_id)
