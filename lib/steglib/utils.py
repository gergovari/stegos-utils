import subprocess
import logging

def run_cmd(cmd, logger, error_msg=None, **kwargs):
    """
    Executes a shell command. Automatically captures output.
    If the command fails (non-zero exit code), it logs the stderr/stdout via logger.debug.
    """
    # Force capture output and text decoding
    kwargs["capture_output"] = True
    kwargs["text"] = True
    
    # Extract check flag (default True unless overridden)
    check = kwargs.pop("check", True)
    
    # We always run check=False here so we can inspect the output on failure
    result = subprocess.run(cmd, check=False, **kwargs)
    
    if result.returncode != 0:
        if error_msg:
            logger.warning(error_msg)
            
        err_out = result.stderr.strip() if result.stderr else ""
        std_out = result.stdout.strip() if result.stdout else ""
        details = err_out or std_out or "No output."
        
        logger.debug("Command failed: %s\nDetails:\n%s", " ".join(cmd), details)
        
        if check:
            # Raise the exception like check=True would
            raise subprocess.CalledProcessError(
                result.returncode, cmd, output=result.stdout, stderr=result.stderr
            )
            
    return result

def hash_dir(directory):
    """Computes an MD5 hash of all file contents in a directory recursively."""
    import hashlib
    import os
    if not os.path.isdir(directory):
        return ""
    hasher = hashlib.md5()
    for root, _, files in os.walk(directory):
        for f in sorted(files):
            fpath = os.path.join(root, f)
            try:
                with open(fpath, "rb") as fp:
                    hasher.update(fp.read())
            except OSError:
                pass
    return hasher.hexdigest()
