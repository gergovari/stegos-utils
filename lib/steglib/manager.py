import json
from steglib import events
import os
import re
import shutil
import subprocess
from steglib.utils import run_cmd

from steglib.constants import BACKEND_DIR, GLOBAL_CONF_FILENAME
from steglib.engine import PackageNotFoundError
from steglib.instance import Instance



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

        from steglib.engine import load_manifest
        
        seen = []
        plan = []
        for pkg in packages:
            if not re.match(r"^[a-zA-Z0-9.\-_]+$", pkg):
                raise ValueError(f"Invalid package name '{pkg}'. Must be alphanumeric, dots, dashes, or underscores.")
            if pkg in seen:
                continue
            seen.append(pkg)

            pkg_dir = self.engine.find_package_dir(pkg, repo)
            manifest = load_manifest(pkg_dir)
            if not manifest:
                raise ValueError(f"Failed to load manifest from '{pkg_dir}'.")
                
            pkg_name = manifest.get("name")
            is_singleton = manifest.get("singleton", False)
            existing = self.engine._find_instances_by_package(pkg_name)
            
            resolved_id = self.engine._resolve_instance_name(
                pkg_name, instance_id, reconfigure, is_singleton, existing, interactive_cb
            )
            
            for cap in manifest.get("capabilities", {}).get("provides", []):
                cap_name = cap.get("name")
                if cap_name:
                    self.engine.cap_manager.register(cap_name, resolved_id, cap.get("injectors", {}))
                    
            plan.append((pkg, pkg_dir, resolved_id))

        new_provided_caps = set()
        for pkg, pkg_dir, resolved_id in plan:
            cli_conf = {}
            if config_file:
                with open(config_file, "r") as fh:
                    cli_conf = json.load(fh)
            
            inst_id = self.engine.process_package(
                pkg_dir, cli_conf, reconfigure, non_interactive, resolved_id, interactive_cb
            )
            display_name = inst_id if inst_id else (resolved_id if resolved_id else pkg)
            events.emit("package_installed", package=pkg, instance_id=display_name)
            
            manifest = load_manifest(pkg_dir)
            if manifest:
                for cap in manifest.get("capabilities", {}).get("provides", []):
                    cap_name = cap.get("name")
                    if cap_name:
                        new_provided_caps.add(cap_name)

        if new_provided_caps:
            if os.path.isdir(self.engine.group_dir):
                from steglib.constants import BACKEND_DIR
                from steglib.utils import hash_dir
                import hashlib
                from steglib.lifecycle import LifecycleManager
                from steglib.engine import parse_consumes

                def get_instance_hash(i_id, conf_path):
                    h = hashlib.md5()
                    b_dir = os.path.join(self.engine.group_dir, i_id, BACKEND_DIR)
                    h.update(hash_dir(b_dir).encode("utf-8"))
                    if os.path.exists(conf_path):
                        with open(conf_path, "rb") as f:
                            h.update(f.read())
                    return h.hexdigest()

                for dep_id in os.listdir(self.engine.group_dir):
                    if any(dep_id == p[2] for p in plan):
                        continue
                        
                    inst = Instance(self.engine.group_name, dep_id)
                    if not inst.is_installed:
                        continue
                        
                    pkg_name = inst.package_name
                    if not pkg_name:
                        continue
                        
                    try:
                        pkg_dir = self.engine.find_package_dir(pkg_name)
                        manifest = load_manifest(pkg_dir)
                        if not manifest:
                            continue
                        consumes = parse_consumes(manifest)
                        if any(cap in consumes for cap in new_provided_caps):
                            before_hash = get_instance_hash(dep_id, inst.conf_path)
                            self.engine.process_package(
                                pkg_dir, cli_conf={}, reconfigure=False,
                                non_interactive=non_interactive, instance_id=dep_id,
                                interactive_cb=interactive_cb
                            )
                            after_hash = get_instance_hash(dep_id, inst.conf_path)
                            if before_hash != after_hash:
                                lm = LifecycleManager(self.engine.group_name)
                                status_res = lm.execute("status", dep_id)
                                if status_res and dep_id in status_res and status_res[dep_id].get("state") == "running":
                                    events.emit("dependent_restarted", instance_id=dep_id)
                                    lm.execute("start", dep_id, False, False)
                                else:
                                    events.emit("dependent_reconfigured", instance_id=dep_id)
                    except Exception as e:
                        events.emit("cascade_reconfigure_failed", instance_id=dep_id, error=str(e))

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
                is_interactive = bool(interactive_cb)
                self.engine.process_package(
                    pkg_dir, cli_conf={}, reconfigure=True,
                    non_interactive=not is_interactive, instance_id=instance_id,
                    interactive_cb=interactive_cb
                )
                count += 1
            except PackageNotFoundError:
                events.emit("reconfigure_failed", package=pkg_name, instance_id=instance_id)
        
        events.emit("reconfigured", count=count, group=self.engine.group_name)

    def remove(self, instance_ids, purge=False, cascade=False, interactive_cb=None, verbose=False):
        """Removes one or more package instances."""
        real_ids = self.engine.resolve_instances(instance_ids, interactive_cb)

        for real_id in real_ids:
            self.engine.cap_manager.unregister_instance(real_id)

        deps = self._find_dependents(real_ids)
        if deps:
            all_dependents = []
            for provider_id, dependents in deps.items():
                events.emit("dependents_found", provider=provider_id, dependents=dependents)
                for d in dependents:
                    if d not in all_dependents:
                        all_dependents.append(d)

            if cascade:
                ans = "y"
            elif interactive_cb:
                ans = interactive_cb(
                    "Reconfigure these instances to remove the integration and restart?",
                    prompt_type="confirm", choices=["y", "n"], default="n"
                )
            else:
                raise ValueError(f"Cannot remove instances with active dependents: {all_dependents}")

            if ans.lower() == "y":
                for dep_id in all_dependents:
                    self._cascade_remove_integration(dep_id, real_ids, verbose=verbose)
            else:
                raise RuntimeError("Aborting removal due to active dependents.")

        for real_id in real_ids:
            events.emit("stopping_instance", instance_id=real_id)
            try:
                from steglib.lifecycle import LifecycleManager
                lm = LifecycleManager(self.engine.group_name)
                lm.execute("stop", real_id, False, verbose)
            except Exception:
                events.emit("stop_failed", instance_id=real_id)

            events.emit("removing_instance", instance_id=real_id)

            instance_dir = os.path.join(self.engine.group_dir, real_id)

            if purge:
                if os.path.exists(instance_dir):
                    shutil.rmtree(instance_dir)
                events.emit("instance_purged", instance_id=real_id)
            else:
                backend_dir = os.path.join(instance_dir, BACKEND_DIR)
                for fname in [".stegpkg-state.json", "docker-compose.yml"]:
                    fpath = os.path.join(backend_dir, fname)
                    if os.path.exists(fpath):
                        os.remove(fpath)
                events.emit("instance_uninstalled", instance_id=real_id)

    def upgrade(self, instance_ids=None, interactive_cb=None, verbose=False):
        """Upgrades one or more instances."""
        if instance_ids:
            instances = self.engine.resolve_instances(instance_ids, interactive_cb)
        else:
            instances = os.listdir(self.engine.group_dir) if os.path.isdir(self.engine.group_dir) else []

        upgraded_instances = []
        for instance_id in instances:
            inst = Instance(self.engine.group_name, instance_id)
            if not inst.is_installed:
                continue
            pkg_name = inst.package_name
            if not pkg_name:
                continue
            try:
                from steglib.constants import BACKEND_DIR
                from steglib.utils import hash_dir
                
                backend_dir = os.path.join(self.engine.group_dir, instance_id, BACKEND_DIR)
                conf_path = inst.conf_path
                
                def get_instance_hash():
                    import hashlib
                    h = hashlib.md5()
                    h.update(hash_dir(backend_dir).encode("utf-8"))
                    if os.path.exists(conf_path):
                        with open(conf_path, "rb") as f:
                            h.update(f.read())
                    return h.hexdigest()

                before_hash = get_instance_hash()
                
                was_running = False
                try:
                    from steglib.lifecycle import LifecycleManager
                    lm = LifecycleManager(self.engine.group_name)
                    status_res = lm.execute("status", instance_id)
                    if status_res and instance_id in status_res:
                        was_running = status_res[instance_id].get("state") == "running"
                except Exception:
                    pass
                
                pkg_dir = self.engine.find_package_dir(pkg_name)
                is_interactive = bool(interactive_cb)
                
                events.emit("checking_upgrades", instance_id=instance_id)
                self.engine.process_package(
                    pkg_dir, cli_conf={}, reconfigure=False,
                    non_interactive=not is_interactive, instance_id=instance_id,
                    interactive_cb=interactive_cb
                )
                
                after_hash = get_instance_hash()
                
                if before_hash != after_hash:
                    if was_running:
                        events.emit("upgrading_and_restarting", instance_id=instance_id)
                        from steglib.lifecycle import LifecycleManager
                        lm = LifecycleManager(self.engine.group_name)
                        lm.execute("start", instance_id, True, verbose)
                    else:
                        events.emit("instance_upgraded", instance_id=instance_id)
                    upgraded_instances.append(instance_id)
                else:
                    events.emit("instance_up_to_date", instance_id=instance_id)
            except Exception as exc:
                events.emit("upgrade_failed", package=pkg_name, instance_id=instance_id, error=str(exc))

        if upgraded_instances:
            # Cascade reconfigure dependents
            all_dependents = set()
            for u in upgraded_instances:
                deps = self._find_dependents([u])
                for dependent_list in deps.values():
                    all_dependents.update(dependent_list)
                    
            for dep_id in all_dependents:
                if dep_id in upgraded_instances:
                    continue
                events.emit("cascade_reconfiguring", instance_id=dep_id)
                inst = Instance(self.engine.group_name, dep_id)
                if inst.is_installed:
                    pkg_name = inst.package_name
                    if pkg_name:
                        try:
                            pkg_dir = self.engine.find_package_dir(pkg_name)
                            self.engine.process_package(
                                pkg_dir, cli_conf={}, reconfigure=False,
                                non_interactive=True, instance_id=dep_id
                            )
                            from steglib.lifecycle import LifecycleManager
                            lm = LifecycleManager(self.engine.group_name)
                            status_res = lm.execute("status", dep_id)
                            if status_res and dep_id in status_res and status_res[dep_id].get("state") == "running":
                                events.emit("restarting_dependent", instance_id=dep_id)
                                lm.execute("start", dep_id, False, verbose)
                        except Exception as e:
                            events.emit("cascade_reconfigure_failed", instance_id=dep_id, error=str(e))
                            
            events.emit("group_upgraded", group=self.engine.group_name, instances=upgraded_instances)
        else:
            events.emit("no_instances_upgraded", group=self.engine.group_name)

    def update(self):
        """Updates app repositories via git pull."""
        if not os.path.isdir(self.engine.repo_dir):
            raise FileNotFoundError(f"Repos directory '{self.engine.repo_dir}' does not exist.")

        updated_repos = []
        for name in os.listdir(self.engine.repo_dir):
            repo_path = os.path.join(self.engine.repo_dir, name)
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                events.emit("skipping_repo", repo=name)
                continue
            events.emit("checking_updates", repo=name)
            try:
                res = run_cmd(
                    ["git", "-c", f"safe.directory={repo_path}", "pull", "--rebase", "--autostash"], cwd=repo_path, error_msg=f"Failed to update '{name}'.", check=True
                )
                if "Already up to date." not in (res.stdout or ""):
                    events.emit("repo_updated", repo=name)
                    updated_repos.append(name)
                else:
                    events.emit("repo_up_to_date", repo=name)
            except Exception:
                pass
                
        if updated_repos:
            events.emit("repos_updated", repos=updated_repos)
        else:
            events.emit("all_repos_up_to_date")

    def list_packages(self):
        """Lists installed packages."""
        if not os.path.isdir(self.engine.group_dir):
            events.emit("no_packages_installed", group=self.engine.group_name)
            return

        events.emit("installed_packages_header", group=self.engine.group_name)
        count = 0
        for instance_id in sorted(os.listdir(self.engine.group_dir)):
            inst = Instance(self.engine.group_name, instance_id)
            if not inst.is_installed:
                continue
            pkg_name = inst.package_name or "unknown"
            events.emit("package_listed", instance_id=instance_id, package=pkg_name)
            count += 1

        if count == 0:
            events.emit("no_packages")

    def clean(self, auto_confirm=False, interactive_cb=None):
        """Removes unmanaged instance directories."""
        if not os.path.isdir(self.engine.group_dir):
            events.emit("group_not_found", group=self.engine.group_dir)
            return

        unmanaged = []
        for name in os.listdir(self.engine.group_dir):
            if name == GLOBAL_CONF_FILENAME or name.startswith('.'):
                continue
            path = os.path.join(self.engine.group_dir, name)
            if not os.path.isdir(path):
                continue
            
            if not Instance(self.engine.group_name, name).is_installed:
                unmanaged.append(path)

        if not unmanaged:
            events.emit("no_unmanaged_directories", group=self.engine.group_name)
            return

        events.emit("unmanaged_directories_header")
        for path in unmanaged:
            events.emit("unmanaged_directory", path=path)

        if auto_confirm:
            ans = "y"
        elif interactive_cb:
            ans = interactive_cb("Delete these directories permanently?", prompt_type="confirm", choices=["y", "n"], default="n")
        else:
            raise ValueError("Auto-confirm not specified and no interactive handler available.")

        if ans.lower() == "y":
            count = 0
            for path in unmanaged:
                try:
                    shutil.rmtree(path)
                    events.emit("directory_deleted", path=path)
                    count += 1
                except OSError as e:
                    events.emit("directory_delete_failed", path=path, error=str(e))
            events.emit("cleaned_directories", count=count)
        else:
            events.emit("clean_aborted")

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

    def _cascade_remove_integration(self, dep_id, removed_ids, verbose=False):
        """Reconfigure a dependent instance to drop integrations to removed IDs."""
        events.emit("cascade_removing_integrations", instance_id=dep_id)
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
                    from steglib.lifecycle import LifecycleManager
                    lm = LifecycleManager(self.engine.group_name)
                    status_res = lm.execute("status", dep_id)
                    if status_res and dep_id in status_res and status_res[dep_id].get("state") == "running":
                        events.emit("dependent_restarted", instance_id=dep_id)
                        lm.execute("start", dep_id, False, verbose)
                    else:
                        events.emit("dependent_reconfigured", instance_id=dep_id)
                except Exception:
                    events.emit("reconfigure_failed", instance_id=dep_id)
