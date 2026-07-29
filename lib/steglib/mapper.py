import os
from steglib.utils import run_cmd
import logging
from typing import Optional
from steglib.constants import TARGET_FOLDERS

logger = logging.getLogger(__name__)

class DriveMapper:
    """Manages the discovery and mounting of stegOS-labeled block devices.

    This class provides methods to scan for block devices labeled with a specific
    prefix (e.g., 'stegos') and bind-mount their internal directories into the
    stegOS runtime tree.

    Attributes:
        root_dir (str): The root directory for all stegOS mounts.
        config_file (str): Path to the mount configuration file.
        label_prefix (str): Prefix used to identify stegOS devices.
        base_mnt_root (str): Directory where physical devices are initially mounted.
        selinux_tmpfs_ctx (str): SELinux context for tmpfs mounts.
        selinux_drive_ctx (str): SELinux context for drive mounts.
    """

    def __init__(
        self,
        root_dir: str = "/stegos",
        config_file: str = "/etc/stegmap/mounts.stegmap",
        label_prefix: str = "stegos",
        selinux_tmpfs_ctx: str = "rootcontext=system_u:object_r:container_file_t:s0",
        selinux_drive_ctx: str = "rootcontext=system_u:object_r:container_file_t:s0"
    ):
        """Initializes the DriveMapper with configuration paths.

        Args:
            root_dir: The root path where bind mounts will be created.
            config_file: Path to the configuration file for fallback labels.
            label_prefix: The volume label prefix to look for.
            selinux_tmpfs_ctx: SELinux context for the root tmpfs mount.
            selinux_drive_ctx: SELinux context for physical drive mounts.
        """
        self.root_dir = os.environ.get("STEGOS_ROOT", root_dir)
        self.config_file = os.environ.get("STEGOS_CONFIG", config_file)
        self.label_prefix = os.environ.get("STEGOS_PREFIX", label_prefix)
        self.selinux_tmpfs_ctx = os.environ.get("SELINUX_TMPFS_CTX", selinux_tmpfs_ctx)
        self.selinux_drive_ctx = os.environ.get("SELINUX_DRIVE_CTX", selinux_drive_ctx)
        
        self.base_mnt_root = os.path.join(self.root_dir, ".base_mounts")

    def _get_config_label(self, search_uuid: str) -> Optional[str]:
        """Retrieves a fallback label from the config file if one exists.

        Args:
            search_uuid: The UUID of the device to search for.

        Returns:
            The label string if found, else None.
        """
        if not os.path.isfile(self.config_file):
            return None
        try:
            with open(self.config_file, "r") as f:
                for line in f:
                    if f'UUID="{search_uuid}"' in line:
                        parts = line.split()
                        for p in parts:
                            if p.startswith('LABEL="'):
                                return p.split('"')[1]
        except OSError as e:
            logger.warning("Failed to read config file: %s", e)
        return None

    def _is_mounted(self, target: str) -> bool:
        """Checks if a target directory is currently a mount point.

        Args:
            target: The directory path to check.

        Returns:
            True if the target is found in /proc/mounts, False otherwise.
        """
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == target:
                        return True
        except OSError:
            pass
        return False

    def _setup_bind_mount(self, src_dir: str, group_name: str, folder_type: str) -> None:
        """Creates a bind mount for a specific group and folder type.

        Args:
            src_dir: The source directory on the physical drive.
            group_name: The resolved group name for this drive.
            folder_type: The type of folder (e.g., 'repos', 'persistent').
        """
        target_mnt = os.path.join(self.root_dir, folder_type, group_name)
        os.makedirs(target_mnt, exist_ok=True)

        if self._is_mounted(target_mnt):
            logger.info("Target already mounted: %s", target_mnt)
            return

        try:
            run_cmd(["mount", "--bind", src_dir, target_mnt], logger=logger, error_msg=f"Failed to bind mount {src_dir} to {target_mnt}", check=True)
            logger.info("Bind mounted: %s", target_mnt)
        except Exception:
            pass

    def mount_all(self) -> None:
        """Discovers and mounts all stegOS-labeled devices."""
        logger.info("Starting device discovery...")

        # Setup root tmpfs
        os.makedirs(self.root_dir, exist_ok=True)
        if not self._is_mounted(self.root_dir):
            mount_opts = "mode=0755"
            if self.selinux_tmpfs_ctx:
                mount_opts += f",{self.selinux_tmpfs_ctx}"
            try:
                run_cmd(["mount", "-t", "tmpfs", "-o", mount_opts, "tmpfs", self.root_dir], logger=logger, error_msg=f"Failed to establish tmpfs on {self.root_dir}", check=True)
                run_cmd(["mount", "--make-shared", self.root_dir], logger=logger, error_msg=f"Failed to make shared {self.root_dir}", check=True)
            except Exception as e:
                raise RuntimeError(f"Failed to establish tmpfs on {self.root_dir}: {e}")

        os.makedirs(self.base_mnt_root, exist_ok=True)

        # Discover devices using blkid
        try:
            res = run_cmd(["blkid"], logger=logger, check=True)
        except Exception as e:
            logger.error("Failed to run blkid: %s", e)
            return

        for line in res.stdout.splitlines():
            if "UUID=" not in line:
                continue

            parts = line.split(":")
            dev_path = parts[0].strip()
            rest = parts[1]

            # Extract UUID and LABEL
            loop_uuid = None
            loop_label = None
            for token in rest.split():
                if token.startswith('UUID="'):
                    loop_uuid = token.split('"')[1]
                elif token.startswith('LABEL="'):
                    loop_label = token.split('"')[1]

            if not loop_label and loop_uuid:
                fallback_label = self._get_config_label(loop_uuid)
                if fallback_label:
                    loop_label = fallback_label

            if not loop_label or not loop_label.startswith(self.label_prefix):
                continue

            short_uuid = loop_uuid[:8] if loop_uuid else "unknown"
            logger.info("Processing device: %s (%s)", dev_path, short_uuid)

            custom_name = ""
            if loop_label.startswith(f"{self.label_prefix}."):
                custom_name = loop_label[len(self.label_prefix)+1:]

            base_mnt = os.path.join(self.base_mnt_root, loop_uuid)
            os.makedirs(base_mnt, exist_ok=True)

            if not self._is_mounted(base_mnt):
                drive_opts = "rw"
                if self.selinux_drive_ctx:
                    drive_opts += f",{self.selinux_drive_ctx}"
                try:
                    run_cmd(["mount", "-o", drive_opts, dev_path, base_mnt], logger=logger, error_msg=f"Failed to mount {dev_path} to {base_mnt}", check=True)
                except Exception as e:
                    logger.error("Failed to mount physical device %s. Skipping.", dev_path)
                    continue

            # Assess structure (Structure A or B)
            is_struct_a = True
            for folder in TARGET_FOLDERS:
                if not os.path.isdir(os.path.join(base_mnt, folder)):
                    is_struct_a = False
                    break

            if is_struct_a:
                final_group = short_uuid
                if custom_name:
                    final_group = f"{custom_name}_{short_uuid}"
                logger.info("Structure A -> Group: %s", final_group)
                for folder in TARGET_FOLDERS:
                    self._setup_bind_mount(os.path.join(base_mnt, folder), final_group, folder)
            else:
                logger.info("Structure B -> Scanning subdirectories...")
                for item in os.listdir(base_mnt):
                    group_path = os.path.join(base_mnt, item)
                    if not os.path.isdir(group_path):
                        continue

                    is_valid_group = True
                    for folder in TARGET_FOLDERS:
                        if not os.path.isdir(os.path.join(group_path, folder)):
                            is_valid_group = False
                            break

                    if is_valid_group:
                        desired_group = item
                        if custom_name:
                            desired_group = f"{custom_name}.{item}"
                        final_group = f"{desired_group}_{short_uuid}"

                        logger.info("Sub-Group: %s -> Namespace: %s", item, final_group)
                        for folder in TARGET_FOLDERS:
                            self._setup_bind_mount(os.path.join(group_path, folder), final_group, folder)

        logger.info("Mapping operations completed.")

    def unmount_all(self) -> None:
        """Unmounts all stegOS bind mounts under the root directory."""
        logger.info("Starting cleanup...")
        
        mounts_to_remove = []
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        mnt_path = parts[1]
                        if mnt_path.startswith(self.root_dir):
                            mounts_to_remove.append(mnt_path)
        except OSError as e:
            logger.error("Failed to read /proc/mounts: %s", e)
            return

        if not mounts_to_remove:
            logger.info("No active mounts found under %s.", self.root_dir)
            return

        # Sort descending by length to unmount deepest paths first
        mounts_to_remove.sort(key=len, reverse=True)

        for target in mounts_to_remove:
            try:
                run_cmd(["umount", target], logger=logger, error_msg=f"Failed to unmount {target}", check=True)
                logger.info("Unmounted: %s", target)
            except Exception:
                logger.warning("Target busy: %s", target)
