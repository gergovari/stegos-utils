import re

with open("lib/steglib/client.py", "r") as f:
    content = f.read()

new_handle = """    def handle(self, event_type, data):
        if not self.console:
            return self._fallback(event_type, data)
            
        # Spinner updates
        if event_type == "checking_updates":
            if self.status: self.status.update("[cyan]Checking for updates...[/cyan]")
            return
        elif event_type == "checking_upgrades":
            if self.status: self.status.update(f"[cyan]Checking upgrades for {data.get('package', 'package')}...[/cyan]")
            return
        elif event_type == "caching_images":
            if self.status: self.status.update(f"[cyan]Caching images for {data.get('package', 'package')}...[/cyan]")
            return
        elif event_type == "cascade_reconfiguring":
            if self.status: self.status.update("[cyan]Reconfiguring dependent instances...[/cyan]")
            return

        # Lists / Tables (Buffered)
        if event_type == "installed_packages_header":
            self._list_buffer = []
            return
        elif event_type == "package_listed":
            self._list_buffer.append(data)
            return
        elif event_type == "no_packages":
            self.console.print("[yellow]No instances found.[/yellow]")
            return
            
        # Success
        if event_type in ("package_installed", "instance_upgraded", "reconfigured", "cleaned_directories", "repo_updated", "group_upgraded", "dependent_reconfigured", "dependent_restarted", "all_repos_up_to_date", "no_unmanaged_directories", "instance_uninstalled"):
            if event_type == "all_repos_up_to_date": msg = "All apps are already up to date."
            elif event_type == "no_unmanaged_directories": msg = "Clean completed, no unmanaged directories found."
            elif event_type == "dependent_reconfigured": msg = f"Successfully reconfigured dependent instance {data.get('instance', data.get('package', ''))}"
            elif event_type == "dependent_restarted": msg = f"Successfully restarted dependent instance {data.get('instance', data.get('package', ''))}"
            elif event_type == "instance_uninstalled": msg = f"Successfully uninstalled {data.get('instance', data.get('package', ''))}"
            else:
                msg = data.get("message", f"Successfully completed {event_type}")
                if "package" in data: msg = f"Successfully operated on {data['package']}"
                elif "instance" in data: msg = f"Successfully operated on {data['instance']}"
            self.console.print(f"[bold green]✓[/bold green] [white]{msg}[/white]")
            return

        # Info
        if event_type in ("starting_package", "stopping_package", "removing_instance", "upgrading_and_restarting", "stopping_instance", "directory_deleted", "instance_purged", "cascade_removing_integrations", "instance_up_to_date", "no_instances_upgraded"):
            if event_type == "cascade_removing_integrations": msg = "Removing integrations from dependent instances..."
            elif event_type == "instance_up_to_date": msg = f"{data.get('instance', data.get('package', 'Instance'))} is already up to date."
            elif event_type == "no_instances_upgraded": msg = "No instances needed upgrading."
            elif event_type == "stopping_instance": msg = f"Stopping instance {data.get('instance', data.get('package', ''))}..."
            elif event_type == "removing_instance": msg = f"Removing instance {data.get('instance', data.get('package', ''))}..."
            else:
                msg = data.get("message", f"Processing {event_type}...")
                if "package" in data:
                    verb = event_type.split('_')[0].capitalize()
                    msg = f"{verb} {data['package']}..."
            self.console.print(f"[bold blue]ℹ[/bold blue] [white]{msg}[/white]")
            return

        # Warning
        if event_type in ("no_packages_installed", "integration_missing", "skipping_action", "skipping_repo", "group_not_found", "no_deployer_backend", "integration_disabled_missing_providers"):
            if event_type == "group_not_found": msg = "No drives initialized. Please run 'steggroup init'."
            else: msg = data.get("message", f"Warning: {event_type}")
            self.console.print(f"[bold yellow]⚠[/bold yellow] [white]{msg}[/white]")
            return

        # Error
        if event_type in ("upgrade_failed", "action_failed", "backend_error", "reconfigure_failed", "command_failed", "cascade_reconfigure_failed", "backend_error_details", "command_failed_msg", "logs_command_failed"):
            msg = data.get("message", data.get("error", data.get("details", f"Error: {event_type}")))
            self.console.print(f"[bold red]✖[/bold red] [white]{msg}[/white]")
            return

        # Backend streams
        if event_type == "backend_log_line":
            self.console.print(f"[dim]{data.get('line', '')}[/dim]", markup=False)
            return
        if event_type.startswith("log_"):
            if event_type == "log_debug" and not self.verbose: return
            msg = data.get("message", "")
            if event_type == "log_error": self.console.print(f"[red]{msg}[/red]", markup=False)
            elif event_type == "log_warning": self.console.print(f"[yellow]{msg}[/yellow]", markup=False)
            else: self.console.print(f"[dim]{msg}[/dim]", markup=False)
            return

        # Fallback for unknown events
        if self.verbose:
            self.console.print(f"[dim]Event: {event_type} {data}[/dim]")

    def finalize(self):
        \"\"\"Called when the stream ends to print any buffered data.\"\"\"
        if self._list_buffer and self.console:
            from rich.table import Table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Instance", style="dim", width=25)
            table.add_column("App", width=25)
            for item in self._list_buffer:
                table.add_row(item.get("instance_id", ""), item.get("package", ""))
            self.console.print(table)
            self._list_buffer = []"""

content = re.sub(r'    def handle\(self, event_type, data\):.*?(?=    def _fallback)', new_handle + '\n\n', content, flags=re.DOTALL)

with open("lib/steglib/client.py", "w") as f:
    f.write(content)
