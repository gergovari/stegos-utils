def fix_file(filepath, replacements):
    with open(filepath, "r") as f:
        content = f.read()
    for old, new in replacements:
        content = content.replace(old, new)
    with open(filepath, "w") as f:
        f.write(content)

# engine.py
fix_file("lib/steglib/engine.py", [
    ("from steglib.constants import (\nfrom steglib.event_types import IntegrationDisabledMissingProvidersEvent, IntegrationRemovedNoLongerRequiredEvent", 
     "from steglib.event_types import IntegrationDisabledMissingProvidersEvent, IntegrationRemovedNoLongerRequiredEvent\nfrom steglib.constants import (")
])

# dockerd.py
fix_file("lib/steglib/dockerd.py", [
    ('group_dir))}..."))', 'group_dir)}..."))'),
    ('events.emit(LogInfoEvent(message=f"  └── ⏳ Starting isolated Docker daemon for group: {os.path.basename(group_dir)}..."))', 
     'events.emit(LogInfoEvent(message=f"  └── ⏳ Starting isolated Docker daemon for group: {os.path.basename(group_dir)}..."))')
])

# backend.py
fix_file("lib/steglib/backend.py", [
    ('(Press Ctrl+C to skip))...")', '(Press Ctrl+C to skip)..."))')
])

# manager.py
fix_file("lib/steglib/manager.py", [
    ("from steglib.event_types import In\nfrom steglib.event_types import", "from steglib.event_types import"),
    ("from steglib.engine import PackageNotFoundError\nfrom steglib.event_types", "from steglib.event_types"),
    ("from steglib.config import (\nfrom steglib.event_types import", "from steglib.event_types import CircularDependencyEvent, DependentReconfiguredEvent, DependentRestartedEvent, GroupNotFoundEvent, GroupUpgradedEvent, InstalledPackagesHeaderEvent, InstancePurgedEvent, InstanceUninstalledEvent, InstanceUpToDateEvent, InstanceUpgradedEvent, LogInfoEvent, MissingComposeFileEvent, NoDeployerBackendEvent, NoInstancesUpgradedEvent, NoPackagesInstalledEvent, NoUnmanagedDirectoriesEvent, PackageInstalledEvent, PackageListedEvent, ReconfigureFailedEvent, ReconfiguredEvent, RemovingInstanceEvent, RestartingDependentEvent, SkippingActionEvent, StartingPackageEvent, StopFailedEvent, StoppingInstanceEvent, UnknownDeployerEvent, UnmanagedDirectoriesHeaderEvent, UnmanagedDirectoryEvent, UpgradeFailedEvent, UpgradingAndRestartingEvent\nfrom steglib.config import (")
])

# mapper.py
fix_file("lib/steglib/mapper.py", [
    ('events.emit(LogInfoEvent(message="Processing device: %s (%s))" % ( dev_path, short_uuid))',
     'events.emit(LogInfoEvent(message="Processing device: %s (%s)" % ( dev_path, short_uuid)))'),
    ('events.emit(LogErrorEvent(message="Failed to mount physical device %s. Skipping.)" % ( dev_path))',
     'events.emit(LogErrorEvent(message="Failed to mount physical device %s. Skipping." % ( dev_path)))'),
    ('events.emit(LogInfoEvent(message="Successfully formatted with label: %s)" % ( label))',
     'events.emit(LogInfoEvent(message="Successfully formatted with label: %s" % ( label)))')
])

