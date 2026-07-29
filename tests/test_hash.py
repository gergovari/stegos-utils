import os
import hashlib

def hash_dir(directory):
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

print("Ready")
