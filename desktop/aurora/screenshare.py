"""Screen sharing over VNC with wayvnc (Settings → Sharing).

The configuration lives in ~/.config/aurora/screen-sharing/: a random
password (shown in Settings) and an RSA key, so viewers connect with
RSA-AES encryption (TigerVNC, RealVNC, Remmina). The shell runs wayvnc while
the switch is on; the firewall opens port 5900 only then.
"""

import os
import secrets
import subprocess

from aurora import config_path

PORT = 5900


def folder():
    return config_path("screen-sharing")


def password():
    path = os.path.join(folder(), "password")
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return new_password()


def new_password():
    os.makedirs(folder(), mode=0o700, exist_ok=True)
    pw = "-".join(secrets.token_hex(2) for _ in range(3))
    fd = os.open(os.path.join(folder(), "password"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(pw)
    write_config()
    return pw


def write_config():
    os.makedirs(folder(), mode=0o700, exist_ok=True)
    key = os.path.join(folder(), "rsa_key.pem")
    if not os.path.exists(key):
        subprocess.run(["openssl", "genrsa", "-traditional", "-out", key, "2048"],
                       capture_output=True, check=False)
        os.chmod(key, 0o600)
    user = os.environ.get("USER") or os.path.basename(os.path.expanduser("~"))
    cfg = os.path.join(folder(), "wayvnc.conf")
    fd = os.open(cfg, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"address=0.0.0.0\nport={PORT}\nenable_auth=true\nusername={user}\n"
                f"password={password_file_value()}\nrsa_private_key_file={key}\n")
    return cfg


def password_file_value():
    with open(os.path.join(folder(), "password")) as f:
        return f.read().strip()


def command():
    password()                       # creates password and config on first use
    return ["wayvnc", "--config", write_config()]
