import json
from steglib import events
import os
import pwd
import tempfile
import time

from steglib.constants import LABEL_PREFIX, TARGET_FOLDERS, GLOBAL_CONF_FILENAME
from steglib.utils import run_cmd


class GroupInitializer:
    """Handles the initialization of stegOS groups on block devices.

    This class provides the logic to verify, format, and seed a block device
    so that it can be mounted as a stegOS group.
    """

    def __init__(self):
        """Initializes the GroupInitializer."""
        pass

    def is_root(self) -> bool:
        """Checks if the current process has root privileges.

        Returns:
            True if the effective user ID is 0, False otherwise.
        """
        return os.geteuid() == 0

    def check_filesystem(self, device: str) -> str:
        """Checks the filesystem type of a given block device.

        Args:
            device: The path to the block device.

        Returns:
            The filesystem type string, or an empty string if none is found.

        Raises:
            RuntimeError: If the 'blkid' command is not found.
        """
        try:
            result = run_cmd(
                ["blkid", "-o", "value", "-s", "TYPE", device],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def check_if_mounted(self, device: str) -> bool:
        """Checks if a given block device is currently mounted.

        Args:
            device: The path to the block device.

        Returns:
            True if the device is found in /proc/mounts, False otherwise.
        """
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    if line.startswith(f"{device} "):
                        return True
        except (FileNotFoundError, OSError):
            pass
        return False

    def initialize(
        self,
        device: str,
        group_name: str,
        domain: str = None,
        timezone: str = None,
        force: bool = False
    ) -> None:
        """Initializes a block device as a stegOS group.

        Args:
            device: Path to the block device (e.g., /dev/sda).
            group_name: Logical name of the group.
            domain: Base domain for global configuration. Defaults to 'localhost'.
            timezone: Timezone for global configuration. Defaults to 'UTC'.
            force: If True, wipe the drive even if it contains a filesystem.

        Raises:
            PermissionError: If the process does not have root privileges.
            ValueError: If the group name is invalid or device does not exist.
            RuntimeError: If initialization steps (formatting, mounting, seeding) fail.
        """
        if not self.is_root():
            raise PermissionError("Root privileges are required to mount and format drives.")

        import re
        if not re.match(r"^[a-zA-Z0-9.\-_]+$", group_name):
            raise ValueError("Group name can only contain alphanumeric characters, dots, dashes, and underscores.")

        if not os.path.exists(device):
            raise ValueError(f"Device '{device}' does not exist.")

        if self.check_if_mounted(device):
            raise RuntimeError(f"Device '{device}' is currently mounted and actively in use by the system. Refusing to initialize.")

        fs_type = self.check_filesystem(device)
        if fs_type:
            if not force:
                raise RuntimeError(
                    f"Device {device} already contains a filesystem ({fs_type}). "
                    "Use force=True to wipe all data and initialize."
                )
            events.emit("log_info", message="Device %s contains data. Proceeding with wipe due to force=True..." % ( device))

        events.emit("log_info", message="Formatting %s as ext4..." % ( device))
        label = f"{LABEL_PREFIX}.{group_name}"
        try:
            run_cmd(["mkfs.ext4", "-F", "-L", label, "-q", device], error_msg=f"Failed to format logical volume '{device}' as ext4.", check=True)
            events.emit("log_info", message="Successfully formatted with label: %s" % ( label))
        except Exception as e:
            raise RuntimeError(f"Failed to format logical volume '{device}' as ext4. See logs for details.") from e

        # Temporarily mount to seed folders
        tmp_mnt = tempfile.mkdtemp(prefix="steggroup_")
        events.emit("log_info", message="Mounting temporarily to %s to seed folders..." % ( tmp_mnt))
        try:
            run_cmd(["mount", device, tmp_mnt], error_msg=f"Failed to mount logical volume '{device}' to '{tmp_mnt}'.", check=True)

            # Create required folders
            for folder in TARGET_FOLDERS:
                path = os.path.join(tmp_mnt, folder)
                os.makedirs(path, exist_ok=True)
                events.emit("log_debug", message="Created directory: /%s" % ( folder))

            base_domain = domain or "localhost"
            tz = timezone or "UTC"

            events.emit("log_info", message="Seeding a default global configuration into the new group...")
            default_global = {
                "base_domain": base_domain,
                "timezone": tz
            }

            persistent_dir = "persistent"
            global_path = os.path.join(tmp_mnt, persistent_dir, GLOBAL_CONF_FILENAME)
            with open(global_path, "w") as f:
                json.dump(default_global, f, indent=4)
            events.emit("log_debug", message="Seeded: %s" % ( global_path))

            # Ownership adjustment for stegOS standard user if needed
            try:
                steg_pw = pwd.getpwnam("steguser")
                steg_uid = steg_pw.pw_uid
                steg_gid = steg_pw.pw_gid
                for root, dirs, files in os.walk(tmp_mnt):
                    for d in dirs:
                        os.chown(os.path.join(root, d), steg_uid, steg_gid)
                    for f in files:
                        os.chown(os.path.join(root, f), steg_uid, steg_gid)
                os.chown(tmp_mnt, steg_uid, steg_gid)
                events.emit("log_info", message="Adjusted ownership for 'steguser'.")
            except KeyError:
                events.emit("log_warning", message="'steguser' not found on this system. Ownership left as root.")

        except Exception as e:
            events.emit("log_warning", message="Failed to initialize logical volume '%s'. It may need to be cleaned up manually." % ( device))
            raise RuntimeError(f"Failed to initialize logical volume '{device}'. See logs for details.") from e
        finally:
            events.emit("log_info", message="Unmounting...")
            try:
                run_cmd(["umount", tmp_mnt], check=True)
            except Exception:
                pass
            try:
                os.rmdir(tmp_mnt)
            except OSError:
                pass
