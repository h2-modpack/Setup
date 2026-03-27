"""
Shared utilities for new_pack.py and new_module.py.
"""

import os
import stat
import shutil
import subprocess


def rmtree(path):
    """shutil.rmtree with read-only override (required for .git/ on Windows)."""
    def force_remove(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=force_remove)


def fill(template, **kwargs):
    """Replace {{KEY}} placeholders in template string."""
    for key, value in kwargs.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def write(path, content):
    """Write content to path, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def run(cmd, cwd=None):
    """Print and execute a shell command, raising on failure."""
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)
