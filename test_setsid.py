import os
import subprocess
os.setsid() # Parent becomes process group leader
subprocess.Popen(["sh", "-c", "echo success > test_setsid.log"], preexec_fn=os.setsid)
