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
        """Resolves a group name from an optional prefix.

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
            ValueError: If resolution is ambiguous or no groups exist.
        """
        if not os.path.isdir(PERSISTENT_DIR):
            if prefix:
                return prefix
            raise ValueError("No groups found. Initialize a drive with 'steggroup init' first.")

        all_groups = sorted(
            d for d in os.listdir(PERSISTENT_DIR)
            if os.path.isdir(os.path.join(PERSISTENT_DIR, d))
        )

        if prefix is None:
            if len(all_groups) == 1:
                return all_groups[0]
            if len(all_groups) > 1:
                if sys.stdin.isatty():
                    print("Multiple groups exist:")
                    for idx, g in enumerate(all_groups, 1):
                        print(f"  {idx}. {g}")
                    while True:
                        choice = input(f"Select group [1-{len(all_groups)}]: ").strip()
                        if choice.isdigit() and 1 <= int(choice) <= len(all_groups):
                            return all_groups[int(choice) - 1]
                        print("Invalid selection. Try again.")
                raise ValueError(f"Multiple groups exist. Specify --group. Available: {all_groups}")
            raise ValueError("No groups found. Initialize a drive with 'steggroup init' first.")

        # Exact match, then prefix match (name before the UUID suffix).
        matches = [
            d for d in all_groups
            if d == prefix or d.startswith(f"{prefix}_")
        ]

        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            if sys.stdin.isatty():
                print(f"Ambiguous group prefix '{prefix}':")
                for idx, g in enumerate(matches, 1):
                    print(f"  {idx}. {g}")
                while True:
                    choice = input(f"Select group [1-{len(matches)}]: ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(matches):
                        return matches[int(choice) - 1]
                    print("Invalid selection. Try again.")
            raise ValueError(f"Ambiguous group prefix '{prefix}': {matches}")

        # No match — assume literal (stegmap may create it later).
        return prefix
