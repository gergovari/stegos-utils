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
