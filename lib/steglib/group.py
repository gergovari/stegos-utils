"""Group resolution for stegOS package groups.

A 'group' corresponds to a mounted stegOS drive (or partition within one).
Groups are identified by a name optionally suffixed with a short UUID,
e.g. ``mygroup_0266c519``.  The resolver accepts partial prefixes so that
users can type ``stegpkg --group mygroup`` without memorizing the UUID.
"""

import os
import sys

from .constants import PERSISTENT_DIR


class GroupManager:
    """Resolves stegOS group names from optional partial prefixes."""

    @staticmethod
    def resolve(prefix=None):
        """Resolve a group name from an optional prefix.

        Resolution rules:
          - No prefix, one group exists → return that group.
          - No prefix, zero or many groups → error.
          - Prefix given → exact match first, then startswith match.
          - Exactly one match → return it.
          - Zero matches → return the literal prefix (stegmap may create it).
          - Multiple matches → error.

        Args:
            prefix: Optional group name or prefix to match against.

        Returns:
            The fully-qualified group name string.

        Raises:
            SystemExit: If resolution is ambiguous or no groups exist.
        """
        if not os.path.isdir(PERSISTENT_DIR):
            if prefix:
                return prefix
            print("Error: No groups found. Initialize a drive with"
                  " 'steggroup init' first.")
            sys.exit(1)

        all_groups = sorted(
            d for d in os.listdir(PERSISTENT_DIR)
            if os.path.isdir(os.path.join(PERSISTENT_DIR, d))
        )

        if prefix is None:
            if len(all_groups) == 1:
                return all_groups[0]
            if len(all_groups) > 1:
                print("Error: Multiple groups exist. Specify --group."
                      f" Available: {all_groups}")
                sys.exit(1)
            print("Error: No groups found. Initialize a drive with"
                  " 'steggroup init' first.")
            sys.exit(1)

        # Exact match, then prefix match (name before the UUID suffix).
        matches = [
            d for d in all_groups
            if d == prefix or d.startswith(f"{prefix}_")
        ]

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(f"Error: Ambiguous group prefix '{prefix}': {matches}")
            sys.exit(1)

        # No match — assume literal (stegmap may create it later).
        return prefix
