"""Configuration resolution models."""

import sys

class ConfigResolver:
    """Interactively (or non-interactively) resolves configuration values
    against a JSON Schema definition."""

    def __init__(self, schema, pkg_conf, cli_conf, reconfigure, non_interactive, interactive_cb=None):
        """Initializes the ConfigResolver.
        
        Args:
            schema: The JSON schema dict for configuration.
            pkg_conf: Existing package configuration dict.
            cli_conf: Configuration overrides provided via CLI.
            reconfigure: If True, forces re-prompting for all values.
            non_interactive: If True, aborts when required input is missing.
            interactive_cb: Optional callback for interactive prompts.
        """
        self.schema = schema
        self.pkg_conf = pkg_conf
        self.cli_conf = cli_conf
        self.reconfigure = reconfigure
        self.non_interactive = non_interactive
        self.interactive_cb = interactive_cb
        
        self.properties = self.schema.get("properties", {})
        self.required = set(self.schema.get("required", []))
        self.final = {}

    def resolve(self):
        """Walk the schema properties and collect final values.
        
        Returns:
            dict: The resolved configuration.
            
        Raises:
            ValueError: If missing required config in non-interactive mode.
        """
        needs_prompt = self._needs_prompt()

        if needs_prompt and self.non_interactive:
            raise ValueError("Missing required configuration values and non-interactive mode is set.")

        if needs_prompt:
            print("\n--- Configuration Required ---")

        for key, prop in self.properties.items():
            if self._apply_cli_overrides(key):
                continue
                
            if self._apply_pkg_conf(key):
                continue
                
            if self._apply_defaults(key, prop, needs_prompt):
                continue

            self._prompt_user(key, prop)

        if needs_prompt:
            print("------------------------------\n")

        return self.final

    def _needs_prompt(self):
        """Determines if any prompts are needed."""
        return any(
            key not in self.cli_conf
            and (self.reconfigure or key not in self.pkg_conf)
            and "default" not in prop
            and key not in self.pkg_conf
            for key, prop in self.properties.items()
        )

    def _apply_cli_overrides(self, key):
        """Applies configuration overrides from the CLI if available."""
        if key in self.cli_conf:
            self.final[key] = self.cli_conf[key]
            return True
        return False

    def _apply_pkg_conf(self, key):
        """Applies existing package configuration if not reconfiguring."""
        if not self.reconfigure and key in self.pkg_conf:
            self.final[key] = self.pkg_conf[key]
            return True
        return False

    def _apply_defaults(self, key, prop, needs_prompt):
        """Applies default values if in non-interactive mode."""
        default = self.pkg_conf.get(key, prop.get("default", ""))
        is_req = key in self.required

        if self.non_interactive:
            if default != "":
                self.final[key] = default
            elif is_req:
                raise ValueError(f"Missing required value for '{key}'.")
            return True
            
        return False

    def _prompt_user(self, key, prop):
        """Prompts the user for a configuration value."""
        default = self.pkg_conf.get(key, prop.get("default", ""))
        is_req = key in self.required
        
        desc = prop.get("description", "")
        base_prompt = key
        if desc:
            base_prompt += f" ({desc})"

        while True:
            if self.interactive_cb:
                val = self.interactive_cb(base_prompt, default=default if default != "" else None)
                if (val is None or val == "") and is_req:
                    base_prompt = f"[Required] {key}"
                    continue
                if val is None or val == "":
                    val = default if default != "" else None
            else:
                prompt = base_prompt
                if default != "":
                    prompt += f" [default: {default}]"
                prompt += ": "
                user_input = input(prompt)
                if not user_input and default != "":
                    val = default
                elif not user_input and is_req:
                    print("This field is required.")
                    continue
                elif not user_input:
                    val = None
                    break
                else:
                    val = user_input

            if val is None or val == "":
                break

            val_type = prop.get("type", "string")
            if val is not None:
                try:
                    if val_type == "integer":
                        val = int(val)
                    elif val_type == "number":
                        val = float(val)
                    elif val_type == "boolean":
                        val = str(val).lower() in ("true", "1", "yes", "y")
                except ValueError:
                    if self.interactive_cb:
                        base_prompt = f"[Invalid type, expected {val_type}] {key}"
                    else:
                        print(f"Invalid type. Expected {val_type}.")
                    continue

            if val is not None:
                self.final[key] = val
            break
