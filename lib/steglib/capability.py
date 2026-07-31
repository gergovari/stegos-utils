import os
import yaml

from steglib.constants import PERSISTENT_DIR
from steglib.instance import Instance

class CapabilityManager:
    """Tracks which installed instances provide which capabilities.

    On construction it scans every installed instance in the group,
    reads its manifest, and builds an in-memory registry of
    ``{capability_name: {instance_id: {injector: ...}}}``.
    """

    def __init__(self, engine):
        """Initializes the CapabilityManager.

        Args:
            engine: The PackageEngine instance providing group context.
        """
        self._engine = engine
        self._registry = {}
        self._scan()

    def register(self, cap_name, instance_name, injector_rules):
        """Register a provider for the duration of this invocation.

        Args:
            cap_name (str): Name of the capability.
            instance_name (str): Instance ID providing the capability.
            injector_rules (dict): Injector rules for the capability.
        """
        self._registry.setdefault(cap_name, {})[instance_name] = {
            "injector": injector_rules,
        }

    def unregister_instance(self, instance_name):
        """Unregister all capabilities provided by an instance."""
        for cap_name, provs in list(self._registry.items()):
            if instance_name in provs:
                del provs[instance_name]
                if not provs:
                    del self._registry[cap_name]

    def get_providers(self, cap_name):
        """Return providers for a given capability.

        Args:
            cap_name (str): Name of the capability.

        Returns:
            dict: ``{instance_id: info}`` for a given capability, or ``{}``.
        """
        return self._registry.get(cap_name, {})

    def _scan(self):
        """Scan the group directory and populate the registry."""
        group_dir = os.path.join(PERSISTENT_DIR, self._engine.group_name)
        if not os.path.isdir(group_dir):
            return

        for instance_id in os.listdir(group_dir):
            if not Instance(self._engine.group_name, instance_id).is_installed:
                continue
            pkg_name = Instance(self._engine.group_name, instance_id).package_name
            if not pkg_name:
                continue
            try:
                pkg_dir = self._engine.find_package_dir(pkg_name)
            except Exception: # Catch PackageNotFoundError from engine
                continue
            
            path = os.path.join(pkg_dir, "manifest.yml")
            manifest = None
            if os.path.isfile(path):
                try:
                    with open(path, "r") as fh:
                        manifest = yaml.safe_load(fh)
                except (yaml.YAMLError, OSError):
                    pass
            
            if manifest is None:
                continue

            for cap in manifest.get("capabilities", {}).get("provides", []):
                name = cap.get("name")
                if name:
                    self.register(name, instance_id, cap.get("injectors", {}))
