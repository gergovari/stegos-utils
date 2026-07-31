import json
import logging
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

import socket
import http.client
import urllib.request
import urllib.parse
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

class EventFormatter:
    """Formats structured events into beautiful CLI output using rich."""
    def __init__(self, console, status, verbose=False):
        self.console = console
        self.status = status
        self.verbose = verbose
        # Buffers for tabular data
        self._list_buffer = []

    def handle(self, event: StegEvent):
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
            

        if event_type == "unmanaged_directories_header":
            self.console.print("\n[bold yellow]Unmanaged Directories Found:[/bold yellow]")
            return
        if event_type == "unmanaged_directory":
            self.console.print(f"  [yellow]•[/yellow] {getattr(event, 'path')}")
            return
        if event_type == "clean_aborted":
            self.console.print("[yellow]Clean aborted.[/yellow]")
            return

        # Success
        if event_type in ("package_installed", "instance_upgraded", "reconfigured", "cleaned_directories", "repo_updated", "group_upgraded", "dependent_reconfigured", "dependent_restarted", "all_repos_up_to_date", "no_unmanaged_directories", "instance_uninstalled"):
            if event_type == "all_repos_up_to_date": msg = "All apps are already up to date."
            elif event_type == "no_unmanaged_directories": msg = "Clean completed, no unmanaged directories found."
            elif event_type == "dependent_reconfigured": msg = f"Successfully reconfigured dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "dependent_restarted": msg = f"Successfully restarted dependent instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "instance_uninstalled": msg = f"Successfully uninstalled {getattr(event, 'instance_id', getattr(event, 'package', ''))}"
            elif event_type == "package_installed": msg = f"Successfully installed {getattr(event, 'package', 'unknown')} as {getattr(event, 'instance_id', 'unknown')}!"
            elif event_type == "cleaned_directories": msg = f"Successfully removed {getattr(event, 'count', 0)} unmanaged directories."
            elif event_type == "reconfigured": msg = f"Successfully reconfigured {getattr(event, 'count', 0)} instance(s) in group '{getattr(event, 'group', '')}'."
            elif event_type == "group_upgraded": msg = f"Successfully upgraded {len(getattr(event, 'instances', []))} instance(s)."
            elif event_type == "repos_updated": msg = f"Successfully updated {len(getattr(event, 'repos', []))} repository(ies)."
            else:
                msg = getattr(event, 'message', f"Successfully completed {event_type}")
                if hasattr(event, 'package') and getattr(event, 'package'): msg = f"Successfully operated on {getattr(event, 'package')}"
                elif hasattr(event, 'instance_id') and getattr(event, 'instance_id'): msg = f"Successfully operated on {getattr(event, 'instance_id')}"
            self.console.print(f"[bold green]✓[/bold green] [white]{msg}[/white]")
            return

        # Info
        if event_type in ("starting_package", "stopping_package", "removing_instance", "upgrading_and_restarting", "stopping_instance", "directory_deleted", "instance_purged", "cascade_removing_integrations", "instance_up_to_date", "no_instances_upgraded", "repo_up_to_date", "restarting_dependent", "integration_removed_no_longer_required", "dependents_found", "log_info"):
            if event_type == "cascade_removing_integrations": msg = "Removing integrations from dependent instances..."
            elif event_type == "instance_up_to_date": msg = f"{getattr(event, 'instance_id', getattr(event, 'package', 'Instance'))} is already up to date."
            elif event_type == "no_instances_upgraded": msg = "No instances needed upgrading."
            elif event_type == "stopping_instance": msg = f"Stopping instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "removing_instance": msg = f"Removing instance {getattr(event, 'instance_id', getattr(event, 'package', ''))}..."
            elif event_type == "directory_deleted": msg = f"Deleted {getattr(event, 'path', '')}"
            elif event_type == "starting_package": msg = f"Starting {getattr(event, 'package', getattr(event, 'instance_id', ''))}..."
            elif event_type == "stopping_package": msg = f"Stopping {getattr(event, 'package', getattr(event, 'instance_id', ''))}..."
            elif event_type == "upgrading_and_restarting": msg = f"Upgrading and restarting {getattr(event, 'instance_id', '')}..."
            elif event_type == "repo_up_to_date": msg = f"Repository {getattr(event, 'repo', '')} is already up to date."
            elif event_type == "restarting_dependent": msg = f"Restarting dependent instance {getattr(event, 'instance_id', '')}..."
            elif event_type == "integration_removed_no_longer_required": msg = f"Removed integration for '{getattr(event, 'capability', '')}' on {getattr(event, 'package', '')} as it is no longer required."
            elif event_type == "dependents_found": msg = f"Found {len(getattr(event, 'dependents', []))} dependent(s) for {getattr(event, 'provider', '')}."
            elif event_type == "log_info": msg = getattr(event, 'message', '')
            else:
                msg = getattr(event, 'message', f"Processing {event_type}...")
                if hasattr(event, 'package') and getattr(event, 'package'):
                    verb = event_type.split('_')[0].capitalize()
                    msg = f"{verb} {getattr(event, 'package')}..."
            self.console.print(f"[bold blue]ℹ[/bold blue] [white]{msg}[/white]")
            return

        # Warning
        if event_type in ("no_packages_installed", "integration_missing", "skipping_action", "skipping_repo", "group_not_found", "no_deployer_backend", "integration_disabled_missing_providers", "injector_no_target_services", "unknown_deployer", "missing_compose_file"):
            if event_type == "group_not_found": msg = "No drives initialized. Please run 'steggroup init'."
            elif event_type == "injector_no_target_services": msg = f"Injector targets {getattr(event, 'targets', [])} not found, available: {getattr(event, 'available', [])}"
            elif event_type == "unknown_deployer": msg = f"Unknown deployer '{getattr(event, 'deployer', '')}' for package {getattr(event, 'package', '')}."
            elif event_type == "missing_compose_file": msg = f"Missing docker-compose.yml for {getattr(event, 'package', '')} at {getattr(event, 'path', '')}"
            else: msg = getattr(event, 'message', f"Warning: {event_type}")
            self.console.print(f"[bold yellow]⚠[/bold yellow] [white]{msg}[/white]")
            return

        # Error
        if event_type in ("upgrade_failed", "action_failed", "backend_error", "reconfigure_failed", "command_failed", "cascade_reconfigure_failed", "backend_error_details", "command_failed_msg", "logs_command_failed", "circular_dependency", "directory_delete_failed", "network_precreate_error", "network_precreate_failed", "stop_failed", "log_exception"):
            if event_type == "circular_dependency": msg = f"Circular dependency detected involving {getattr(event, 'package', '')}"
            elif event_type == "directory_delete_failed": msg = f"Failed to delete directory {getattr(event, 'path', '')}: {getattr(event, 'error', '')}"
            elif event_type == "network_precreate_error": msg = f"Failed to pre-create networks: {getattr(event, 'error', '')}"
            elif event_type == "network_precreate_failed": msg = f"[{getattr(event, 'package', '')}] Failed to pre-create networks: {getattr(event, 'error', '')}"
            elif event_type == "stop_failed": msg = f"Failed to stop instance {getattr(event, 'instance_id', '')}"
            elif event_type == "log_exception": msg = getattr(event, 'message', '')
            else: msg = getattr(event, 'message', getattr(event, 'error', getattr(event, 'details', f"Error: {event_type}")))
            self.console.print(f"[bold red]✖[/bold red] [white]{msg}[/white]")
            return

        # Backend streams
        if event_type == "dockerd_starting_backend":
            if self.verbose: self.console.print("[dim]  └── ⏳ Starting backend...[/dim]", markup=False)
            return
        if event_type == "backend_loading_cache":
            if self.verbose: self.console.print(f"[{getattr(event, 'package', 'unknown')}] Backend is loading cache...", style="dim", highlight=False)
            return
        if event_type == "backend_log_line":
            self.console.print(getattr(event, 'line', ''), style="dim", highlight=False)
            return
        if event_type == "backend_log_stdout":
            self.console.print(getattr(event, 'output', ''), highlight=False)
            return
        if event_type == "backend_log_stderr":
            self.console.print(f"[red]{getattr(event, 'output', '')}[/red]", highlight=False)
            return
        if event_type.startswith("log_"):
            if event_type == "log_debug" and not self.verbose: return
            msg = getattr(event, 'message', "")
            if event_type == "log_error": self.console.print(f"[red]{msg}[/red]", highlight=False)
            elif event_type == "log_warning": self.console.print(f"[yellow]{msg}[/yellow]", highlight=False)
            else: self.console.print(msg, style="dim", highlight=False)
            return

        # Fallback for unknown events
        if self.verbose:
            self.console.print(f"[dim]Event: {event_type} {getattr(event, '_raw_data', event.to_dict())}[/dim]")


    def finalize(self):
        """Called when the stream ends to print any buffered data."""
        if self._list_buffer and self.console:
            from rich.table import Table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Instance", style="dim", width=25)
            table.add_column("App", width=25)
            for item in self._list_buffer:
                table.add_row(getattr(item, 'instance_id', '') or "", getattr(item, 'package', '') or "")
            self.console.print(table)
            self._list_buffer = []


    def _fallback(self, event_type, data):
        import sys
        if event_type.startswith("log_") and event_type != "log_debug":
            print(data.get("message", ""), file=sys.stderr)
        elif event_type == "backend_log_line":
            print(data.get("line", ""))
        elif self.verbose:
            print(f"Event: {event_type} {data}", file=sys.stderr)

class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)

class UnixHTTPHandler(urllib.request.AbstractHTTPHandler):
    def __init__(self, socket_path):
        super().__init__()
        self.socket_path = socket_path

    def unix_open(self, req):
        return self.do_open(lambda host: UnixHTTPConnection(self.socket_path), req)

    unix_request = urllib.request.AbstractHTTPHandler.do_request_


class StegClient:
    def __init__(self, url=None):
        import os
        self.url = url or os.environ.get("STEGOS_DAEMON_URL", "unix:///run/stegos/stegos.sock")
        if self.url.startswith("unix://"):
            self.socket_path = self.url[7:]
            opener = urllib.request.build_opener(UnixHTTPHandler(self.socket_path))
            urllib.request.install_opener(opener)
        elif self.url.startswith("http://"):
            self.socket_path = None
            urllib.request.install_opener(urllib.request.build_opener())
        else:
            raise ValueError("URL must start with unix:// or http://")

    def _request(self, method, path, data=None):
        if self.url.startswith("unix://"):
            full_url = f"unix://localhost{path}"
        else:
            full_url = f"{self.url}{path}"
            
        req = urllib.request.Request(full_url, method=method)
        if data is not None:
            req.data = json.dumps(data).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as response:
                body = response.read()
                if body:
                    return json.loads(body)
                return None
        except HTTPError as e:
            body = e.read()
            try:
                err_data = json.loads(body)
                raise RuntimeError(f"API Error: {err_data.get('error', e.reason)}")
            except json.JSONDecodeError:
                raise RuntimeError(f"API Error: {e.reason} - {body.decode('utf-8')}")
        except (FileNotFoundError, ConnectionRefusedError):
            raise RuntimeError(f"Could not connect to daemon at {self.url}. Is stegd running?")
        except Exception as e:
            raise RuntimeError(f"Connection Error: {e}")

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data=None):
        return self._request("POST", path, data)

    def stream(self):
        """Returns a connected socket for interactive streaming."""
        if self.socket_path:
            conn = UnixHTTPConnection(self.socket_path)
        else:
            parsed = urllib.parse.urlparse(self.url)
            conn = http.client.HTTPConnection(parsed.netloc)
            
        try:
            conn.connect()
        except (FileNotFoundError, ConnectionRefusedError):
            raise RuntimeError(f"Could not connect to daemon at {self.url}. Is stegd running?")
            
        conn.request("POST", "/stream", headers={"Upgrade": "stegos-stream", "Connection": "Upgrade"})
        resp = conn.getresponse()
        if resp.status != 101:
            raise RuntimeError(f"Failed to upgrade connection: {resp.status} {resp.reason}")
        return conn.sock

    def call_interactive(self, action, args, prompt_callback=None):
        sock = self.stream()
        f = sock.makefile("rw")
        f.write(json.dumps({"action": action, "args": args}) + "\n")
        f.flush()
        
        try:
            from rich.console import Console
            console = Console(stderr=True)
            status = console.status("[bold green]Executing...", spinner="dots")
            status.start()
        except ImportError:
            console = None
            status = None
            
        formatter = EventFormatter(console, status, args.get("verbose", False))
            
        try:
            while True:
                line = f.readline()
                if not line:
                    break
                msg = json.loads(line)
                if msg["type"] == "prompt":
                    if status:
                        status.stop()
                    if prompt_callback:
                        ans = prompt_callback(msg)
                    else:
                        from steglib.cli_utils import do_local_prompt
                        ans = do_local_prompt(msg["message"], msg.get("prompt_type", "text"), msg.get("choices"), msg.get("default"), msg.get("multiple"))
                    f.write(json.dumps({"answer": ans}) + "\n")
                    f.flush()
                    if status:
                        status.start()
                elif msg["type"] == "done":
                    formatter.finalize()
                    return msg.get("result")
                elif msg["type"] == "error":
                    formatter.finalize()
                    err = RuntimeError(msg.get("error"))
                    if "details" in msg:
                        err.details = msg["details"]
                    raise err
                elif msg["type"] == "event":
                    formatter.handle(deserialize_event(msg.get("event"), msg.get("data", {})))
        finally:
            if status:
                status.stop()
