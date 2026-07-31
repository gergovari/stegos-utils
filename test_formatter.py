from steglib.client import EventFormatter
from rich.console import Console

console = Console()
status = console.status("Executing...")
formatter = EventFormatter(console, status, verbose=True)

events = [
    ("checking_updates", {}),
    ("package_installed", {"package": "nginx-proxy"}),
    ("starting_package", {"package": "whoami"}),
    ("instance_up_to_date", {"instance": "my-instance"}),
    ("upgrade_failed", {"error": "Some bad error"}),
    ("installed_packages_header", {}),
    ("package_listed", {"instance_id": "nginx-proxy-1", "package_name": "nginx-proxy", "status": "running"}),
    ("package_listed", {"instance_id": "whoami-2", "package_name": "whoami", "status": "stopped"}),
]

for event, data in events:
    formatter.handle(event, data)
formatter.finalize()
