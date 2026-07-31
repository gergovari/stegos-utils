import re

with open("lib/steglib/client.py", "r") as f:
    content = f.read()

# Fix unmanaged directory lists:
# We will insert them right before `# Success`
unmanaged_str = """
        if event_type == "unmanaged_directories_header":
            self.console.print("\\n[bold yellow]Unmanaged Directories Found:[/bold yellow]")
            return
        if event_type == "unmanaged_directory":
            self.console.print(f"  [yellow]•[/yellow] {getattr(event, 'path')}")
            return
        if event_type == "clean_aborted":
            self.console.print("[yellow]Clean aborted.[/yellow]")
            return
"""
content = content.replace("        # Success\n", unmanaged_str + "\n        # Success\n")


# Fix Success strings
# package_installed, cleaned_directories, reconfigured
success_logic = """
            if event_type == "all_repos_up_to_date": msg = "All apps are already up to date."
            elif event_type == "no_unmanaged_directories": msg = "Clean completed, no unmanaged directories found."
            elif event_type == "dependent_reconfigured": msg = f"Successfully reconfigured dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "dependent_restarted": msg = f"Successfully restarted dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "instance_uninstalled": msg = f"Successfully uninstalled {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "package_installed": msg = f"Successfully installed {getattr(event, 'package', 'unknown')} as {getattr(event, 'instance_id', 'unknown')}!"
            elif event_type == "cleaned_directories": msg = f"Successfully removed {getattr(event, 'count', 0)} unmanaged directories."
            elif event_type == "reconfigured": msg = f"Successfully reconfigured {getattr(event, 'count', 0)} instance(s) in group '{getattr(event, 'group', '')}'."
            elif event_type == "group_upgraded": msg = f"Successfully upgraded {len(getattr(event, 'instances', []))} instance(s)."
            else:
                msg = getattr(event, 'message', f"Successfully completed {event_type}")
                if hasattr(event, 'package') and getattr(event, 'package'): msg = f"Successfully operated on {getattr(event, 'package')}"
                elif hasattr(event, 'instance_id') and getattr(event, 'instance_id'): msg = f"Successfully operated on {getattr(event, 'instance_id')}"
"""

# We need to replace the old if/else block inside Success
old_success = """            if event_type == "all_repos_up_to_date": msg = "All apps are already up to date."
            elif event_type == "no_unmanaged_directories": msg = "Clean completed, no unmanaged directories found."
            elif event_type == "dependent_reconfigured": msg = f"Successfully reconfigured dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "dependent_restarted": msg = f"Successfully restarted dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "instance_uninstalled": msg = f"Successfully uninstalled {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            else:
                msg = getattr(event, 'message', f"Successfully completed {event_type}")
                if hasattr(event, 'package') and getattr(event, 'package'): msg = f"Successfully operated on {getattr(event, 'package')}"
                elif hasattr(event, 'instance_id') and getattr(event, 'instance_id'): msg = f"Successfully operated on {getattr(event, 'instance_id')}\""""

content = content.replace(old_success, success_logic.strip("\n"))

# Fix Info strings
# directory_deleted
info_logic = """
            if event_type == "cascade_removing_integrations": msg = "Removing integrations from dependent instances..."
            elif event_type == "instance_up_to_date": msg = f"{getattr(event, 'instance_id', getattr(event, 'package', 'Instance'))} is already up to date."
            elif event_type == "no_instances_upgraded": msg = "No instances needed upgrading."
            elif event_type == "stopping_instance": msg = f"Stopping instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "removing_instance": msg = f"Removing instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "directory_deleted": msg = f"Deleted {getattr(event, 'path', '')}"
            elif event_type == "starting_package": msg = f"Starting {getattr(event, 'package', getattr(event, 'instance_id', ''))}..."
            elif event_type == "stopping_package": msg = f"Stopping {getattr(event, 'package', getattr(event, 'instance_id', ''))}..."
            else:
                msg = getattr(event, 'message', f"Processing {event_type}...")
                if hasattr(event, 'package') and getattr(event, 'package'):
                    verb = event_type.split('_')[0].capitalize()
                    msg = f"{verb} {getattr(event, 'package')}..."
"""

old_info = """            if event_type == "cascade_removing_integrations": msg = "Removing integrations from dependent instances..."
            elif event_type == "instance_up_to_date": msg = f"{getattr(event, 'instance_id', getattr(event, 'package', 'Instance'))} is already up to date."
            elif event_type == "no_instances_upgraded": msg = "No instances needed upgrading."
            elif event_type == "stopping_instance": msg = f"Stopping instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "removing_instance": msg = f"Removing instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            else:
                msg = getattr(event, 'message', f"Processing {event_type}...")
                if hasattr(event, 'package') and getattr(event, 'package'):
                    verb = event_type.split('_')[0].capitalize()
                    msg = f"{verb} {getattr(event, 'package')}...\""""

content = content.replace(old_info, info_logic.strip("\n"))

# Fix dim strings
dim_fix = """
            if event_type == "log_debug" and not self.verbose: return
            msg = getattr(event, 'message', "")
            if event_type == "log_error": self.console.print(f"[red]{msg}[/red]", highlight=False)
            elif event_type == "log_warning": self.console.print(f"[yellow]{msg}[/yellow]", highlight=False)
            else: self.console.print(msg, style="dim", highlight=False)
"""
old_dim = """
            if event_type == "log_debug" and not self.verbose: return
            msg = getattr(event, 'message', "")
            if event_type == "log_error": self.console.print(f"[red]{msg}[/red]", markup=False)
            elif event_type == "log_warning": self.console.print(f"[yellow]{msg}[/yellow]", markup=False)
            else: self.console.print(f"[dim]{msg}[/dim]", markup=False)
"""
content = content.replace(old_dim.strip("\n"), dim_fix.strip("\n"))

content = content.replace('self.console.print(f"[dim]  └── ⏳ Starting backend...[/dim]", markup=False)', 'self.console.print("  └── ⏳ Starting backend...", style="dim", highlight=False)')
content = content.replace('self.console.print(f"[dim][{getattr(event, \'package\', \'unknown\')}] Backend is loading cache...[/dim]", markup=False)', 'self.console.print(f"[{getattr(event, \'package\', \'unknown\')}] Backend is loading cache...", style="dim", highlight=False)')
content = content.replace('self.console.print(f"[dim]{getattr(event, \'line\', \'\')}[/dim]", markup=False)', 'self.console.print(getattr(event, \'line\', \'\'), style="dim", highlight=False)')


with open("lib/steglib/client.py", "w") as f:
    f.write(content)
