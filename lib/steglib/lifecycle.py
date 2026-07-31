import json
import logging
import os

from steglib.backend import BACKENDS, BackendBase
from steglib.constants import BACKEND_DIR, PERSISTENT_DIR
from steglib.group import GroupManager
from steglib.instance import Instance

logger = logging.getLogger(__name__)

class MultipleInstancesError(Exception):
    """Raised when multiple instances match a requested package name.

    Attributes:
        instances (list): List of matching instance names.
    """
    def __init__(self, instances):
        self.instances = instances
        super().__init__(f"Multiple instances match: {instances}")

class LifecycleManager:
    """Manages the lifecycle (start, stop, etc.) of stegOS packages within a group."""

    def __init__(self, group_prefix=None, interactive_cb=None):
        """Initialize the LifecycleManager with a specific group.

        Args:
            group_prefix (str, optional): The group prefix to resolve.
            interactive_cb: Optional callback for interactive prompts.
        """
        self.group_name = GroupManager.resolve(group_prefix, interactive_cb)
        self.cont_dir = os.path.join(PERSISTENT_DIR, self.group_name)

    def execute(self, action, package_name=None, if_created=False, follow=False):
        """Execute an action on a specific package or all packages in the group.

        Args:
            action (str): The lifecycle action to perform (e.g., start, stop).
            package_name (str, optional): Specific package to target.
            if_created (bool): If True, backend will skip starting uncreated containers.
            follow (bool): If True, follow logs.

        Raises:
            RuntimeError: If the group directory is not found.
            ValueError: If no instance or package matches the given name.
            MultipleInstancesError: If multiple instances match and intervention is needed.
        """
        if not os.path.isdir(self.cont_dir):
            raise RuntimeError(f"Group directory '{self.cont_dir}' not found.")

        # Get all valid packages in the group
        all_pkgs = [d for d in os.listdir(self.cont_dir) if os.path.isdir(os.path.join(self.cont_dir, d, BACKEND_DIR))]

        # Build dependency graph
        graph = {pkg: set() for pkg in all_pkgs}
        for pkg in all_pkgs:
            try:
                conf = Instance(self.group_name, pkg).read_conf()
                if conf:
                    enabled_caps = conf.get("enabled_capabilities", {})
                    cap_meta = conf.get("capability_metadata", {})
                    for cap_name, provs in enabled_caps.items():
                        if not cap_meta.get(cap_name, {}).get("wait_for_start", True):
                            continue
                        if not isinstance(provs, list):
                            provs = [provs]
                        for p in provs:
                            if p in graph and p != pkg:
                                graph[pkg].add(p)
            except (json.JSONDecodeError, OSError, KeyError):
                pass

        # Topological sort
        visited = set()
        temp = set()
        topo_order = []

        def visit(n):
            if n in temp:
                logger.warning("Circular dependency detected involving '%s'", n)
                return
            if n not in visited:
                temp.add(n)
                for dep in sorted(graph.get(n, [])):
                    visit(dep)
                temp.remove(n)
                visited.add(n)
                topo_order.append(n)

        for n in sorted(all_pkgs):
            if n not in visited:
                visit(n)

        # Resolve target package or instances if specified
        if package_name:
            target_instances = []
            if package_name in all_pkgs:
                target_instances = [package_name]
            else:
                for pkg in all_pkgs:
                    try:
                        inst = Instance(self.group_name, pkg)
                        if inst.is_installed and inst.package_name == package_name:
                            target_instances.append(pkg)
                    except Exception:
                        pass

                if not target_instances:
                    raise ValueError(f"No instance or package named '{package_name}' found in group '{self.group_name}'.")

                if len(target_instances) > 1:
                    # Let the caller (CLI/API) decide how to handle multiple instances
                    raise MultipleInstancesError(target_instances)

            if action == "start":
                # For start, target packages and all their transitive dependencies
                target_set = set()
                def collect_deps(n):
                    if n not in target_set:
                        target_set.add(n)
                        for d in graph.get(n, []):
                            collect_deps(d)
                for inst in target_instances:
                    collect_deps(inst)
                packages_to_run = [p for p in topo_order if p in target_set]
            else:
                # For stop, restart, etc., operate on all target instances
                if action in ("stop", "restart"):
                    packages_to_run = [p for p in reversed(topo_order) if p in target_instances]
                else:
                    packages_to_run = [p for p in topo_order if p in target_instances]
        else:
            if action in ("stop", "restart"):
                packages_to_run = list(reversed(topo_order))
            else:
                packages_to_run = topo_order

        # Execute action concurrently honoring dependencies
        import concurrent.futures
        import threading

        if action == "start":
            # Pre-create all explicit external networks sequentially before concurrent startup
            try:
                from steglib.dockerd import ensure_running
                from steglib.utils import run_cmd
                import yaml

                env = ensure_running(self.cont_dir)
                for pkg in packages_to_run:
                    inst = Instance(self.group_name, pkg)
                    if not inst.is_installed:
                        continue
                    compose_file = os.path.join(self.cont_dir, pkg, BACKEND_DIR, "docker-compose.yml")
                    if os.path.isfile(compose_file):
                        try:
                            with open(compose_file, "r") as f:
                                cdata = yaml.safe_load(f)
                            nets = cdata.get("networks", {}) if cdata else {}
                            for n_name, n_data in nets.items():
                                if isinstance(n_data, dict) and n_data.get("external"):
                                    ext_name = n_data.get("name", n_name)
                                    if ext_name and ext_name != "default":
                                        run_cmd(["docker", "network", "create", "--label", f"com.docker.compose.network={ext_name}", ext_name], env=env, logger=logger, check=False, quiet_fail=True)
                        except Exception as e:
                            logger.debug(f"[{pkg}] Failed to parse networks for pre-creation: {e}")
            except Exception as e:
                logger.debug(f"Failed to pre-create networks: {e}")

        # Resolve exact dependencies for the selected subset of packages
        dependencies = {pkg: set() for pkg in packages_to_run}
        
        if action in ("stop", "restart"):
            # A depends on B. A must stop before B stops. So B depends on A stopping.
            for pkg in packages_to_run:
                for dep in graph.get(pkg, []):
                    if dep in packages_to_run:
                        dependencies[dep].add(pkg)
        else:
            # A depends on B. B must start before A starts. So A depends on B starting.
            for pkg in packages_to_run:
                for dep in graph.get(pkg, []):
                    if dep in packages_to_run:
                        dependencies[pkg].add(dep)
        
        results = {}
        lock = threading.Lock()
        condition = threading.Condition(lock)
        completed = set()
        failed = set()
        launched = set()
        
        thread_local = threading.local()
        
        class ThreadBufferFilter(logging.Filter):
            def filter(self, record):
                if getattr(thread_local, 'buffer_logs', False):
                    if not hasattr(thread_local, 'buffered_records'):
                        thread_local.buffered_records = []
                    thread_local.buffered_records.append(record)
                    return False
                return True
                
        root_logger = logging.getLogger()
        buf_filter = ThreadBufferFilter()
        buffer_enabled = not (action == "logs" and follow)
        
        if buffer_enabled:
            for handler in root_logger.handlers:
                handler.addFilter(buf_filter)
        
        def run_pkg(pkg):
            inst = Instance(self.group_name, pkg)
            if not inst.is_installed:
                if package_name:
                    logger.warning("[%s] No deployer backend found. Was it installed with stegpkg?", pkg)
                return None
            deployer = inst.deployer
            backend_cls = BACKENDS.get(deployer)
            if backend_cls:
                pkg_path = os.path.join(self.cont_dir, pkg, BACKEND_DIR)
                backend = backend_cls(pkg, pkg_path, self.cont_dir)
                return backend.execute(action, if_created, follow=follow)
            else:
                logger.warning("[%s] Warning: Unknown deployer '%s'", pkg, deployer)
                return None

        def worker(pkg):
            if buffer_enabled:
                thread_local.buffer_logs = True
                thread_local.buffered_records = []
            try:
                res = run_pkg(pkg)
                with lock:
                    if buffer_enabled:
                        thread_local.buffer_logs = False
                        for record in getattr(thread_local, 'buffered_records', []):
                            for h in root_logger.handlers:
                                if record.levelno >= h.level:
                                    h.handle(record)
                    if res is not None:
                        results[pkg] = res
                    completed.add(pkg)
                    condition.notify_all()
            except Exception as e:
                with lock:
                    if buffer_enabled:
                        thread_local.buffer_logs = False
                        for record in getattr(thread_local, 'buffered_records', []):
                            for h in root_logger.handlers:
                                if record.levelno >= h.level:
                                    h.handle(record)
                    logger.error(f"[{pkg}] Action '{action}' failed: {e}")
                    failed.add(pkg)
                    condition.notify_all()

        max_workers = len(packages_to_run) if packages_to_run else 1
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                while len(completed) + len(failed) < len(packages_to_run):
                    with lock:
                        # Propagate failures
                        for p in packages_to_run:
                            if p not in launched and p not in failed:
                                if any(dep in failed for dep in dependencies[p]):
                                    failed.add(p)
                                    logger.error(f"[{p}] Skipping action '{action}' because dependencies failed.")
                                    condition.notify_all()
                        
                        ready = [
                            p for p in packages_to_run
                            if p not in launched and p not in failed and dependencies[p].issubset(completed)
                        ]
                        
                        import contextvars
                        for p in ready:
                            launched.add(p)
                            ctx = contextvars.copy_context()
                            executor.submit(ctx.run, worker, p)
                        
                        if not ready and len(completed) + len(failed) < len(packages_to_run):
                            condition.wait()
        finally:
            if buffer_enabled:
                for handler in root_logger.handlers:
                    handler.removeFilter(buf_filter)
                        
        if failed:
            raise RuntimeError(f"Action '{action}' failed for packages: {', '.join(failed)}")
        
        return results
