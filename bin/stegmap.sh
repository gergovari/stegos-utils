#!/bin/sh
# Strict POSIX compliant (compatible with BusyBox ash)
set -eu

# ==========================================
# CONFIGURATION & DEFAULTS
# ==========================================
STEGOS_ROOT="${STEGOS_ROOT:-/stegos}"
CONFIG_FILE="${STEGOS_CONFIG:-/etc/stegmap/mounts.stegmap}"
LABEL_PREFIX="${STEGOS_PREFIX:-stegos}"
BASE_MNT_ROOT="${STEGOS_ROOT}/.base_mounts"
LOG_FILE="${STEGOS_LOG:-/var/log/stegmap.log}"
LOCK_DIR="${STEGOS_LOCK_DIR:-/var/lock/stegmap_lock}"

# SELinux Overrides (Leave empty if SELinux is disabled/permissive)
# Example: SELINUX_TMPFS_CTX="rootcontext=system_u:object_r:tmpfs_t:s0"
SELINUX_TMPFS_CTX="${SELINUX_TMPFS_CTX:-rootcontext=system_u:object_r:container_file_t:s0}"
SELINUX_DRIVE_CTX="${SELINUX_DRIVE_CTX:-rootcontext=system_u:object_r:container_file_t:s0}"

# Space-separated list of required folders (No arrays in POSIX sh)
TARGET_FOLDERS="repos containers conf"

# ==========================================
# LOGGING & LOCKING (POSIX)
# ==========================================
log_msg()   { echo "[$1] $2" | tee -a "$LOG_FILE"; logger -t stegmap "[$1] $2" 2>/dev/null || true; }
log_info()  { log_msg "INFO" "$1"; }
log_warn()  { log_msg "WARN" "$1" >&2; }
log_error() { log_msg "ERROR" "$1" >&2; }
log_fatal() { log_msg "FATAL" "$1" >&2; exit 1; }

# Atomic locking using directory creation (universally supported in BusyBox)
mkdir -p "$(dirname "$LOG_FILE")"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
	log_fatal "Another instance is running (lock directory $LOCK_DIR exists)."
fi
# Ensure lock is released on exit
trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT INT TERM

if [ "$(id -u)" -ne 0 ]; then
	log_fatal "This script requires root privileges."
fi

# ==========================================
# HELPER FUNCTIONS
# ==========================================
setup_bind_mount() {
	src_dir="$1"
	group_name="$2"
	folder_type="$3"

	target_mnt="${STEGOS_ROOT}/${folder_type}/${group_name}"
	mkdir -p "$target_mnt"

	# Check if already mounted (reading from /proc/mounts directly)
	if grep -q "[[:space:]]${target_mnt}[[:space:]]" /proc/mounts; then
		log_info "Target already mounted: $target_mnt"
	else
		if mount --bind "$src_dir" "$target_mnt"; then
			log_info "Bind mounted: $target_mnt"
		else
			log_error "Failed to bind mount $src_dir"
		fi
	fi
}

get_config_label() {
	search_uuid="$1"
	if [ -f "$CONFIG_FILE" ]; then
		# Use sed to extract the LABEL from the config file where the UUID matches
		sed -n "s/.*UUID=\"${search_uuid}\".*LABEL=\"\([^\"]*\)\".*/\1/p" "$CONFIG_FILE" | head -n 1
	fi
}

# ==========================================
# COMMAND: UNMOUNT
# ==========================================
cmd_unmount() {
	log_info "Starting cleanup..."

	# Check if any Docker containers are still running
	if command -v docker >/dev/null 2>&1; then
		if [ -n "$(docker ps -q 2>/dev/null)" ]; then
			log_fatal "Cannot unmount: Docker containers are still running. Stop them first (e.g. stegctl stop)."
		fi
	fi

	# Read /proc/mounts directly instead of findmnt.
	# Awk calculates string length, sorts descending to unmount deepest paths first.
	mounts_to_remove=$(awk -v prefix="${STEGOS_ROOT}" '$2 ~ "^" prefix "(/|$)" {print length($2), $2}' /proc/mounts | sort -rn | cut -d" " -f2)

	if [ -z "$mounts_to_remove" ]; then
		log_info "No active mounts found under $STEGOS_ROOT."
		exit 0
	fi

	for target in $mounts_to_remove; do
		if umount "$target"; then
			log_info "Unmounted: $target"
		else
			log_warn "Target busy: $target"
		fi
	done
}

# ==========================================
# COMMAND: MOUNT
# ==========================================
cmd_mount() {
	log_info "Starting device discovery..."

	# Ensure dynamic root is prepared
	mkdir -p "$STEGOS_ROOT" 2>/dev/null || true
	if ! grep -q "[[:space:]]${STEGOS_ROOT}[[:space:]]" /proc/mounts; then
		mount_opts="mode=0755"
		if [ -n "$SELINUX_TMPFS_CTX" ]; then
			mount_opts="${mount_opts},${SELINUX_TMPFS_CTX}"
		fi

		if ! mount -t tmpfs -o "$mount_opts" tmpfs "$STEGOS_ROOT"; then
			log_fatal "Failed to establish tmpfs on $STEGOS_ROOT."
		fi
	fi
	mkdir -p "$BASE_MNT_ROOT"

	# Pipe blkid directly into loop (Subshell created, but we don't need vars to persist outside)
	blkid | grep UUID | while read -r blkid_line; do
	dev_path=$(echo "$blkid_line" | cut -d: -f1)

	# POSIX extraction using sed
	loop_uuid=$(echo "$blkid_line" | sed -n 's/.*UUID="\([^"]*\)".*/\1/p')
	loop_label=$(echo "$blkid_line" | sed -n 's/.*LABEL="\([^"]*\)".*/\1/p')
	
	# Config override
	if [ -z "$loop_label" ] && [ -n "$loop_uuid" ]; then
		fallback_label=$(get_config_label "$loop_uuid")
		[ -n "$fallback_label" ] && loop_label="$fallback_label"
	fi

	# STRICT FILTER using case (POSIX alternative to regex)
	case "$loop_label" in
		"$LABEL_PREFIX"|"$LABEL_PREFIX".*) ;;
		*) continue ;;
	esac

	short_uuid=$(echo "$loop_uuid" | cut -c 1-8)
	log_info "Processing device: $dev_path ($short_uuid)"

	# Extract namespace using parameter expansion
	custom_name=""
	case "$loop_label" in
		"$LABEL_PREFIX".*) custom_name="${loop_label#$LABEL_PREFIX.}" ;;
	esac

	base_mnt="${BASE_MNT_ROOT}/${loop_uuid}"
	mkdir -p "$base_mnt"

	if ! grep -q "[[:space:]]${base_mnt}[[:space:]]" /proc/mounts; then
		drive_opts="rw"
		if [ -n "$SELINUX_DRIVE_CTX" ]; then
			drive_opts="${drive_opts},${SELINUX_DRIVE_CTX}"
		fi

		if ! mount -o "$drive_opts" "$dev_path" "$base_mnt"; then
			log_error "Failed to mount physical device $dev_path. Skipping."
			continue
		fi
	fi

	# Assess Structure A
	is_struct_a="true"
	for folder in $TARGET_FOLDERS; do
		if [ ! -d "${base_mnt}/${folder}" ]; then
			is_struct_a="false"
			break
		fi
	done

	if [ "$is_struct_a" = "true" ]; then
		final_group="${short_uuid}"
		[ -n "$custom_name" ] && final_group="${custom_name}_${short_uuid}"

		log_info "Structure A -> Group: $final_group"
		for folder in $TARGET_FOLDERS; do
			setup_bind_mount "${base_mnt}/${folder}" "$final_group" "$folder"
		done
	else
		log_info "Structure B -> Scanning subdirectories..."
		for group_path in "$base_mnt"/*; do
			[ ! -d "$group_path" ] && continue

			subfolder_name=$(basename "$group_path")

			is_valid_group="true"
			for folder in $TARGET_FOLDERS; do
				if [ ! -d "${group_path}/${folder}" ]; then
					is_valid_group="false"
					break
				fi
			done

			if [ "$is_valid_group" = "true" ]; then
				desired_group="${subfolder_name}"
				[ -n "$custom_name" ] && desired_group="${custom_name}.${subfolder_name}"

				final_group="${desired_group}_${short_uuid}"

				log_info "Sub-Group: $subfolder_name -> Namespace: $final_group"
				for folder in $TARGET_FOLDERS; do
					setup_bind_mount "${group_path}/${folder}" "$final_group" "$folder"
				done
			fi
		done
	fi
done

log_info "Mapping operations completed."
}

# ==========================================
# ENTRYPOINT
# ==========================================
if [ $# -ne 1 ]; then
	echo "Usage: $0 {mount|unmount}"
	exit 1
fi

case "$1" in
	mount)   cmd_mount ;;
	unmount) cmd_unmount ;;
	*)       echo "Usage: $0 {mount|unmount}"; exit 1 ;;
esac
