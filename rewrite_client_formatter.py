import re

with open("lib/steglib/client.py", "r") as f:
    content = f.read()

# Add imports at the top
import_stmt = """
from steglib.event_types import StegEvent
import steglib.event_types as event_types_module

_EVENT_CLASS_MAP = {}
for name in dir(event_types_module):
    obj = getattr(event_types_module, name)
    if isinstance(obj, type) and issubclass(obj, StegEvent) and obj is not StegEvent:
        # Check if it has the default event_type
        if hasattr(obj, 'event_type'):
            _EVENT_CLASS_MAP[obj.event_type] = obj

def deserialize_event(event_name: str, data: dict) -> StegEvent:
    cls = _EVENT_CLASS_MAP.get(event_name)
    if cls:
        # Extract valid fields
        valid_keys = {k for k in dir(cls) if not k.startswith('_')} 
        # Better: use dataclasses.fields(cls) if we import dataclasses
        import dataclasses
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
    
    # Fallback for unknown
    event = StegEvent(event_type=event_name)
    setattr(event, '_raw_data', data)
    return event
"""

if "_EVENT_CLASS_MAP" not in content:
    content = content.replace("import logging", "import logging" + import_stmt)

# Update handle signature
content = content.replace("def handle(self, event_type, data):", "def handle(self, event: StegEvent):")

# Update fallback and data usage
# We will just write a new handle function since it's cleaner.

new_handle = """    def handle(self, event: StegEvent):
        event_type = event.event_type
        if not self.console:
            return self._fallback(event_type, getattr(event, '_raw_data', event.to_dict()))
            
        # Spinner updates
        if event_type == "checking_updates":
            if self.status: self.status.update("[cyan]Checking for updates...[/cyan]")
            return
        elif event_type == "checking_upgrades":
            if self.status: self.status.update(f"[cyan]Checking upgrades for {getattr(event, 'package', 'package')}...[/cyan]")
            return
        elif event_type == "caching_images":
            if self.status: self.status.update(f"[cyan]Caching images for {getattr(event, 'package', 'package')}...[/cyan]")
            return
        elif event_type == "cascade_reconfiguring":
            if self.status: self.status.update("[cyan]Reconfiguring dependent instances...[/cyan]")
            return

        # Lists / Tables (Buffered)
        if event_type == "installed_packages_header":
            self._list_buffer = []
            return
        elif event_type == "package_listed":
            self._list_buffer.append(event)
            return
        elif event_type == "no_packages":
            self.console.print("[yellow]No instances found.[/yellow]")
            return
            
        # Success
        if event_type in ("package_installed", "instance_upgraded", "reconfigured", "cleaned_directories", "repo_updated", "group_upgraded", "dependent_reconfigured", "dependent_restarted", "all_repos_up_to_date", "no_unmanaged_directories", "instance_uninstalled"):
            if event_type == "all_repos_up_to_date": msg = "All apps are already up to date."
            elif event_type == "no_unmanaged_directories": msg = "Clean completed, no unmanaged directories found."
            elif event_type == "dependent_reconfigured": msg = f"Successfully reconfigured dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "dependent_restarted": msg = f"Successfully restarted dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "instance_uninstalled": msg = f"Successfully uninstalled {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            else:
                msg = getattr(event, 'message', f"Successfully completed {event_type}")
                if hasattr(event, 'package') and getattr(event, 'package'): msg = f"Successfully operated on {getattr(event, 'package')}"
                elif hasattr(event, 'instance_id') and getattr(event, 'instance_id'): msg = f"Successfully operated on {getattr(event, 'instance_id')}"
            self.console.print(f"[bold green]✓[/bold green] [white]{msg}[/white]")
            return

        # Info
        if event_type in ("starting_package", "stopping_package", "removing_instance", "upgrading_and_restarting", "stopping_instance", "directory_deleted", "instance_purged", "cascade_removing_integrations", "instance_up_to_date", "no_instances_upgraded"):
            if event_type == "cascade_removing_integrations": msg = "Removing integrations from dependent instances..."
            elif event_type == "instance_up_to_date": msg = f"{getattr(event, 'instance_id', getattr(event, 'package', 'Instance'))} is already up to date."
            elif event_type == "no_instances_upgraded": msg = "No instances needed upgrading."
            elif event_type == "stopping_instance": msg = f"Stopping instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "removing_instance": msg = f"Removing instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            else:
                msg = getattr(event, 'message', f"Processing {event_type}...")
                if hasattr(event, 'package') and getattr(event, 'package'):
                    verb = event_type.split('_')[0].capitalize()
                    msg = f"{verb} {getattr(event, 'package')}..."
            self.console.print(f"[bold blue]ℹ[/bold blue] [white]{msg}[/white]")
            return

        # Warning
        if event_type in ("no_packages_installed", "integration_missing", "skipping_action", "skipping_repo", "group_not_found", "no_deployer_backend", "integration_disabled_missing_providers"):
            if event_type == "group_not_found": msg = "No drives initialized. Please run 'steggroup init'."
            else: msg = getattr(event, 'message', f"Warning: {event_type}")
            self.console.print(f"[bold yellow]⚠[/bold yellow] [white]{msg}[/white]")
            return

        # Error
        if event_type in ("upgrade_failed", "action_failed", "backend_error", "reconfigure_failed", "command_failed", "cascade_reconfigure_failed", "backend_error_details", "command_failed_msg", "logs_command_failed"):
            msg = getattr(event, 'message', getattr(event, 'error', getattr(event, 'details', f"Error: {event_type}")))
            self.console.print(f"[bold red]✖[/bold red] [white]{msg}[/white]")
            return

        # Backend streams
        if event_type == "dockerd_starting_backend":
            if self.verbose: self.console.print("[dim]  └── ⏳ Starting backend...[/dim]", markup=False)
            return
        if event_type == "backend_loading_cache":
            if self.verbose: self.console.print(f"[dim][{getattr(event, 'package', 'unknown')}] Backend is loading cache...[/dim]", markup=False)
            return
        if event_type == "backend_log_line":
            self.console.print(f"[dim]{getattr(event, 'line', '')}[/dim]", markup=False)
            return
        if event_type.startswith("log_"):
            if event_type == "log_debug" and not self.verbose: return
            msg = getattr(event, 'message', "")
            if event_type == "log_error": self.console.print(f"[red]{msg}[/red]", markup=False)
            elif event_type == "log_warning": self.console.print(f"[yellow]{msg}[/yellow]", markup=False)
            else: self.console.print(f"[dim]{msg}[/dim]", markup=False)
            return

        # Fallback for unknown events
        if self.verbose:
            self.console.print(f"[dim]Event: {event_type} {getattr(event, '_raw_data', event.to_dict())}[/dim]")
"""

content = re.sub(r'    def handle\(self, event: StegEvent\):.*?(?=    def _fallback)', new_handle + '\n\n', content, flags=re.DOTALL)
# It might be `def handle(self, event_type, data):` if we didn't replace it correctly, so:
content = re.sub(r'    def handle\(self, event_type, data\):.*?(?=    def _fallback)', new_handle + '\n\n', content, flags=re.DOTALL)


content = content.replace('formatter.handle(msg.get("event"), msg.get("data", {}))', 'formatter.handle(deserialize_event(msg.get("event"), msg.get("data", {})))')
content = content.replace('table.add_row(item.get("instance_id", ""), item.get("package", ""))', 'table.add_row(item.instance_id or "", item.package or "")')

with open("lib/steglib/client.py", "w") as f:
    f.write(content)
