import re
import os

def process_file(filepath, replacements):
    if not os.path.exists(filepath): return
    with open(filepath, 'r') as f:
        content = f.read()

    content = re.sub(r'import logging\n', 'from steglib import events\n', content)
    content = re.sub(r'logger = logging\.getLogger\(__name__\)\n', '', content)
    
    for pattern, repl in replacements:
        content = re.sub(pattern, repl, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

backend_repl = [
    (r'logger\.info\(f"\[\{self\.pkg\}\] Checking image: \{image\}"\)', r'events.emit("checking_image", package=self.pkg, image=image)'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Downloading image: \{image\}\.\.\."\)', r'events.emit("downloading_image", package=self.pkg, image=image)'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Skipping image cache extraction \(no free space on device\)\."\)', r'events.emit("skipping_image_cache_extraction", package=self.pkg, reason="no free space on device")'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Loading cached image: \{image\}\.\.\."\)', r'events.emit("loading_cached_image", package=self.pkg, image=image)'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Backend is caching images\.\.\."\)', r'events.emit("caching_images", package=self.pkg)'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Starting package\.\.\."\)', r'events.emit("starting_package", package=self.pkg)'),
    (r'logger\.info\(f"\[\{self\.pkg\}\] Stopping package\.\.\."\)', r'events.emit("stopping_package", package=self.pkg)'),
    (r'logger\.error\(f"\[\{self\.pkg\}\] Missing docker-compose\.yml in \{self\.pkg_path\}"\)', r'events.emit("missing_compose_file", package=self.pkg, path=self.pkg_path)'),
    (r'logger\.error\(f"\[\{self\.pkg\}\] Logs command exited with \{process\.returncode\}"\)', r'events.emit("logs_command_failed", package=self.pkg, exit_code=process.returncode)'),
    (r'logger\.error\(err_msg\)', r'events.emit("backend_error", package=self.pkg, error=err_msg)'),
    (r'logger\.debug\(f"Backend error details: \{details\}"\)', r'events.emit("backend_error_details", package=self.pkg, details=details)'),
    # for run_cmd stdout parsing
    (r'logger\.info\(line\.rstrip\(\'\\n\'\)\)', r'events.emit("backend_log_line", package=self.pkg, line=line.rstrip(\'\\n\'))'),
    (r'logger\.info\(res\.stdout\.strip\(\)\)', r'events.emit("backend_log_stdout", package=self.pkg, output=res.stdout.strip())'),
    (r'logger\.error\(res\.stderr\.strip\(\)\)', r'events.emit("backend_log_stderr", package=self.pkg, output=res.stderr.strip())'),
    # Fix run_cmd calls
    (r'logger=logger,', r'')
]

group_init_repl = [
    (r'logger\.info\("\[Group: %s\] Initializing\.\.\.", group_name\)', r'events.emit("group_initializing", group=group_name)'),
    (r'logger\.info\("\[Group: %s\] Directory created at %s", group_name, group_dir\)', r'events.emit("group_directory_created", group=group_name, path=group_dir)'),
    (r'logger\.info\("\[Group: %s\] Initialized core global configuration\.", group_name\)', r'events.emit("group_config_initialized", group=group_name)'),
    (r'logger\.info\("\[Group: %s\] Applying initialization integrations\.\.\.", group_name\)', r'events.emit("group_applying_integrations", group=group_name)'),
    (r'logger\.info\("\[Group: %s\] Successfully requested reverse proxy generation\.", group_name\)', r'events.emit("group_reverse_proxy_requested", group=group_name)'),
    (r'logger\.info\("\[Group: %s\] Successfully requested wildcard cert generation\.", group_name\)', r'events.emit("group_cert_requested", group=group_name)'),
    (r'logger\.warning\("\[Group: %s\] Error requesting proxy config: %s", group_name, e\)', r'events.emit("group_proxy_error", group=group_name, error=str(e))'),
    (r'logger\.info\("\[Group: %s\] Initialization complete!", group_name\)', r'events.emit("group_initialization_complete", group=group_name)'),
    (r'logger\.info\("\[Group: %s\] Skipping formatting for block device %s \(already formatted as %s\)\.", group_name, block_device, fstype\)', r'events.emit("group_skipping_formatting", group=group_name, device=block_device, fstype=fstype)'),
    (r'logger\.info\("\[Group: %s\] Formatting block device %s as btrfs\.\.\.", group_name, block_device\)', r'events.emit("group_formatting_device", group=group_name, device=block_device)'),
    (r'logger\.warning\("\[Group: %s\] Warning: Block device %s does not exist\.", group_name, block_device\)', r'events.emit("group_device_not_found", group=group_name, device=block_device)')
]

engine_repl = [
    (r'logger\.warning\(f"\[\{instance_name\}\] Integration \'\{cap_name\}\' providers disappeared! It will be disabled\."\)', r'events.emit("integration_disabled_missing_providers", package=instance_name, capability=cap_name)'),
    (r'logger\.debug\(f"Missing package_name in instance \{instance_id\}"\)', r'events.emit("missing_package_name", instance_id=instance_id)')
]

mapper_repl = [
    (r'logger\.info\("\[DriveMapper\] Validating drive %s\.\.\.", serial\)', r'events.emit("drive_validating", serial=serial)'),
    (r'logger\.warning\("\[DriveMapper\] Skipping drive %s: invalid metadata format\.", serial\)', r'events.emit("drive_metadata_invalid", serial=serial)'),
    (r'logger\.info\("\[DriveMapper\] Successfully mapped block device %s to drive %s", block_device, serial\)', r'events.emit("drive_mapped", device=block_device, serial=serial)'),
    (r'logger\.warning\("\[DriveMapper\] No unmounted block devices available for drive %s", serial\)', r'events.emit("drive_no_devices_available", serial=serial)'),
    (r'logger\.info\("\[DriveMapper\] Auto-detecting drives\.\.\."\)', r'events.emit("drive_autodetecting")'),
    (r'logger\.info\("\[DriveMapper\] Mounting drive %s \(%s\) to %s\.\.\.", serial, b_dev, m_point\)', r'events.emit("drive_mounting", serial=serial, device=b_dev, path=m_point)'),
    (r'logger\.info\("\[DriveMapper\] Successfully mounted %s", serial\)', r'events.emit("drive_mount_success", serial=serial)'),
    (r'logger\.warning\("\[DriveMapper\] Failed to mount %s: %s", serial, e\)', r'events.emit("drive_mount_failed", serial=serial, error=str(e))'),
    (r'logger\.info\("\[DriveMapper\] Drive %s is already mounted at %s", serial, m_point\)', r'events.emit("drive_already_mounted", serial=serial, path=m_point)'),
    (r'logger\.info\("\[DriveMapper\] Completed mounting drives\."\)', r'events.emit("drive_mounting_completed")'),
    (r'logger\.info\("\[DriveMapper\] Unmounting all drives\.\.\."\)', r'events.emit("drive_unmounting_all")'),
    (r'logger\.info\("\[DriveMapper\] Unmounting drive %s from %s\.\.\.", serial, m_point\)', r'events.emit("drive_unmounting", serial=serial, path=m_point)'),
    (r'logger\.info\("\[DriveMapper\] Successfully unmounted %s", serial\)', r'events.emit("drive_unmount_success", serial=serial)'),
    (r'logger\.warning\("\[DriveMapper\] Failed to unmount %s: %s", serial, e\)', r'events.emit("drive_unmount_failed", serial=serial, error=str(e))'),
    (r'logger\.info\("\[DriveMapper\] Drive %s is not mounted", serial\)', r'events.emit("drive_not_mounted", serial=serial)'),
    (r'logger\.info\("\[DriveMapper\] Completed unmounting drives\."\)', r'events.emit("drive_unmounting_completed")')
]

process_file('lib/steglib/backend.py', backend_repl)
process_file('lib/steglib/group_init.py', group_init_repl)
process_file('lib/steglib/engine.py', engine_repl)
process_file('lib/steglib/mapper.py', mapper_repl)
