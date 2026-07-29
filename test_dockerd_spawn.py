import subprocess
import os

log_file = "fake_dockerd.log"
data_root = "/tmp/data"
exec_root = "/tmp/exec"
pid_file = "/tmp/docker.pid"
sock_file = "/tmp/docker.sock"
bip = "10.5.0.1/24"
pool_base = "10.5.0.0/16"

cmd = [
    "dockerd",
    "--data-root", data_root,
    "--exec-root", exec_root,
    "--pidfile", pid_file,
    "--host", f"unix://{sock_file}",
    "--iptables=true",
    f"--bip={bip}",
    "--default-address-pool", f"base={pool_base},size=24"
]

cmd_str = " ".join(cmd) + f" > {log_file} 2>&1"
print(f"Running: {cmd_str}")
subprocess.Popen(cmd_str, shell=True, env=os.environ, preexec_fn=os.setsid)
