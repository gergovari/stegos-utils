from steglib.client import EventFormatter
from rich.console import Console
console = Console()
formatter = EventFormatter(console, None, verbose=True)

events = [
    ("all_repos_up_to_date", {}),
    ("no_unmanaged_directories", {}),
    ("instance_up_to_date", {"instance": "my-instance"}),
    ("no_instances_upgraded", {}),
    ("group_not_found", {}),
    ("cascade_removing_integrations", {}),
    ("dependent_reconfigured", {"instance": "nginx-proxy"}),
    ("installed_packages_header", {}),
    ("package_listed", {"instance_id": "whoami-35e7750e", "package": "whoami"}),
    ("package_listed", {"instance_id": "nginx-proxy-805c321c", "package": "nginx-proxy"}),
]

for event, data in events:
    formatter.handle(event, data)
formatter.finalize()
