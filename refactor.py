import re

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # We'll just do some basic replacements for manager.py
    # This is a bit manual, but I'll craft specific replacements.
    
    # 1. replace imports
    content = re.sub(r'import logging\n', 'from steglib import events\n', content)
    content = re.sub(r'logger = logging\.getLogger\(__name__\)\n', '', content)
    
    # 2. replace specific log lines with events.emit
    replacements = [
        (r'logger\.info\("Successfully installed %s as %s!", pkg, display_name\)', r'events.emit("package_installed", package=pkg, instance_id=display_name)'),
        (r'logger\.info\("\[%s\] Reconfigured dependent instance\. Restarting\.\.\.", dep_id\)', r'events.emit("dependent_restarted", instance_id=dep_id)'),
        (r'logger\.info\("\[%s\] Reconfigured dependent instance\.", dep_id\)', r'events.emit("dependent_reconfigured", instance_id=dep_id)'),
        (r'logger\.warning\("Failed to cascade reconfigure \'%s\': %s", dep_id, e\)', r'events.emit("cascade_reconfigure_failed", instance_id=dep_id, error=str(e))'),
        (r'logger\.warning\("Could not reconfigure \'%s\' \(instance \'%s\'\)\.", pkg_name, instance_id\)', r'events.emit("reconfigure_failed", package=pkg_name, instance_id=instance_id)'),
        (r'logger\.info\("Successfully reconfigured %d instance\(s\) in group \'%s\'\.", count, self\.engine\.group_name\)', r'events.emit("reconfigured", count=count, group=self.engine.group_name)'),
        (r'logger\.warning\("\'%s\' is used by: %s", provider_id, ", "\.join\(dependents\)\)', r'events.emit("dependents_found", provider=provider_id, dependents=dependents)'),
        (r'logger\.info\("Stopping instance \'%s\' before removal\.\.\.", real_id\)', r'events.emit("stopping_instance", instance_id=real_id)'),
        (r'logger\.warning\("Failed to stop instance cleanly\. Proceeding with removal\.\.\."\)', r'events.emit("stop_failed", instance_id=real_id)'),
        (r'logger\.info\("Removing instance \'%s\'\.\.\.", real_id\)', r'events.emit("removing_instance", instance_id=real_id)'),
        (r'logger\.info\("Removed \'%s\' and all persistent data\.", real_id\)', r'events.emit("instance_purged", instance_id=real_id)'),
        (r'logger\.info\("Uninstalled \'%s\'\. Config and data preserved\.", real_id\)', r'events.emit("instance_uninstalled", instance_id=real_id)'),
        (r'logger\.info\("\[%s\] Checking for upgrades/integrations\.\.\.", instance_id\)', r'events.emit("checking_upgrades", instance_id=instance_id)'),
        (r'logger\.info\("\[%s\] Ensuring instance is up to date and restarting\.\.\.", instance_id\)', r'events.emit("upgrading_and_restarting", instance_id=instance_id)'),
        (r'logger\.info\("\[%s\] Instance upgraded\.", instance_id\)', r'events.emit("instance_upgraded", instance_id=instance_id)'),
        (r'logger\.info\("\[%s\] Already up to date\.", instance_id\)', r'events.emit("instance_up_to_date", instance_id=instance_id)'),
        (r'logger\.warning\("Could not upgrade \'%s\' \(instance \'%s\'\): %s", pkg_name, instance_id, exc\)', r'events.emit("upgrade_failed", package=pkg_name, instance_id=instance_id, error=str(exc))'),
        (r'logger\.info\("\[%s\] Cascade reconfiguring dependent instance\.\.\.", dep_id\)', r'events.emit("cascade_reconfiguring", instance_id=dep_id)'),
        (r'logger\.info\("\[%s\] Restarting dependent instance\.\.\.", dep_id\)', r'events.emit("restarting_dependent", instance_id=dep_id)'),
        (r'logger\.warning\("Failed to reconfigure \'%s\': %s", dep_id, e\)', r'events.emit("cascade_reconfigure_failed", instance_id=dep_id, error=str(e))'),
        (r'logger\.info\("Upgraded instances in group \'%s\': %s", self\.engine\.group_name, ", "\.join\(upgraded_instances\)\)', r'events.emit("group_upgraded", group=self.engine.group_name, instances=upgraded_instances)'),
        (r'logger\.info\("No instances upgraded in group \'%s\'\.", self\.engine\.group_name\)', r'events.emit("no_instances_upgraded", group=self.engine.group_name)'),
        (r'logger\.info\("\[%s\] Skipping \(not a git repository\)\.", name\)', r'events.emit("skipping_repo", repo=name)'),
        (r'logger\.info\("\[%s\] Checking for updates\.\.\.", name\)', r'events.emit("checking_updates", repo=name)'),
        (r'logger\.info\("\[%s\] Successfully updated from remote\.", name\)', r'events.emit("repo_updated", repo=name)'),
        (r'logger\.info\("\[%s\] Already up to date\.", name\)', r'events.emit("repo_up_to_date", repo=name)'),
        (r'logger\.info\("Updated repositories: %s", ", "\.join\(updated_repos\)\)', r'events.emit("repos_updated", repos=updated_repos)'),
        (r'logger\.info\("All repositories are up to date\."\)', r'events.emit("all_repos_up_to_date")'),
        (r'logger\.info\("No packages installed in group \'%s\'\.", self\.engine\.group_name\)', r'events.emit("no_packages_installed", group=self.engine.group_name)'),
        (r'logger\.info\("Installed packages in group \'%s\':", self\.engine\.group_name\)', r'events.emit("installed_packages_header", group=self.engine.group_name)'),
        (r'logger\.info\("  - %s \(Package: %s\)", instance_id, pkg_name\)', r'events.emit("package_listed", instance_id=instance_id, package=pkg_name)'),
        (r'logger\.info\("  \(none\)"\)', r'events.emit("no_packages")'),
        (r'logger\.info\("Group directory \'%s\' does not exist\.", self\.engine\.group_dir\)', r'events.emit("group_not_found", group=self.engine.group_dir)'),
        (r'logger\.info\("No unmanaged directories found in group \'%s\'\.", self\.engine\.group_name\)', r'events.emit("no_unmanaged_directories", group=self.engine.group_name)'),
        (r'logger\.info\("Found unmanaged directories:"\)', r'events.emit("unmanaged_directories_header")'),
        (r'logger\.info\("  - %s", path\)', r'events.emit("unmanaged_directory", path=path)'),
        (r'logger\.info\("Deleted %s", path\)', r'events.emit("directory_deleted", path=path)'),
        (r'logger\.warning\("Failed to delete %s: %s", path, e\)', r'events.emit("directory_delete_failed", path=path, error=str(e))'),
        (r'logger\.info\("Successfully cleaned %d directory\(ies\)\.", count\)', r'events.emit("cleaned_directories", count=count)'),
        (r'logger\.info\("Aborted\."\)', r'events.emit("clean_aborted")'),
        (r'logger\.info\("\[%s\] Reconfiguring to remove integrations\.\.\.", dep_id\)', r'events.emit("cascade_removing_integrations", instance_id=dep_id)'),
        (r'logger\.info\("\[%s\] Reconfigured dependent instance\. Restarting\.\.\.", dep_id\)', r'events.emit("dependent_reconfigured_restarting", instance_id=dep_id)'),
        (r'logger\.info\("\[%s\] Reconfigured dependent instance\.", dep_id\)', r'events.emit("dependent_reconfigured", instance_id=dep_id)'),
        (r'logger\.warning\("Failed to reconfigure \'%s\'\.", dep_id\)', r'events.emit("reconfigure_failed", instance_id=dep_id)')
    ]
    
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

process_file('lib/steglib/manager.py')
