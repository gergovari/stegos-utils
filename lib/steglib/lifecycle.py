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
                    for provs in enabled_caps.values():
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

        # Execute action
        results = {}
        for pkg in packages_to_run:
            inst = Instance(self.group_name, pkg)
            if not inst.is_installed:
                if package_name:
                    logger.warning("[%s] No deployer backend found. Was it installed with stegpkg?", pkg)
                continue

            deployer = inst.deployer
            backend_cls = BACKENDS.get(deployer)
            if backend_cls:
                pkg_path = os.path.join(self.cont_dir, pkg, BACKEND_DIR)
                backend = backend_cls(pkg, pkg_path, self.cont_dir)
                res = backend.execute(action, if_created, follow=follow)
                if res is not None:
                    results[pkg] = res
            else:
                logger.warning("[%s] Warning: Unknown deployer '%s'", pkg, deployer)
        
        return results
