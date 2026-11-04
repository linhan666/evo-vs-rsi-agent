#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Remote control helper for EvoVS-RSI.

All *experiments* run on the remote host; this script is control-plane only
(SSH over an authenticated SOCKS5 proxy).  SFTP subsystem is unavailable on
the target host, therefore file transfer is implemented as binary-safe
``cat > file`` writes / ``tar -czf -`` pipes.

Usage:
    python ops/rctl.py exec  "cmd ..."            [--host H] [--timeout S]
    python ops/rctl.py put   <local> <remote>     [--host H]
    python ops/rctl.py putdir <localdir> <remotedir> [--host H]
    python ops/rctl.py get   <remote> <local>     [--host H]
"""
import argparse
import os
import shlex
import sys
import tempfile

import socks
import paramiko

def _load_local_env():
    """Load ops/local.env (gitignored) so no credential is ever hard-coded here."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local.env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _require(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit("missing {0}; put it in ops/local.env".format(name))
    return value


_load_local_env()

PROXY_HOST = _require("EVOVS_PROXY_HOST")
PROXY_PORT = int(_require("EVOVS_PROXY_PORT"))
PROXY_USER = _require("EVOVS_PROXY_USER")
PROXY_PSWD = _require("EVOVS_PROXY_PSWD")

SSH_USER = _require("EVOVS_SSH_USER")
SSH_PSWD = _require("EVOVS_SSH_PSWD")
DEFAULT_HOST = os.environ.get("EVOVS_HOST", "172.25.18.26")

CHUNK = 1 << 16


def connect(host, timeout=30):
    sock = socks.socksocket()
    sock.set_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT,
                   username=PROXY_USER, password=PROXY_PSWD)
    sock.settimeout(timeout)
    sock.connect((host, 22))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=22, username=SSH_USER, password=SSH_PSWD,
                   sock=sock, timeout=timeout, allow_agent=False, look_for_keys=False)
    return client


def run(client, cmd, timeout=1800, stdin_data=None, quiet=False):
    """Execute a remote command; return (exit_code, stdout_text, stderr_text)."""
    last = None
    for _ in range(3):
        try:
            chan = client.get_transport().open_session(timeout=60)
            chan.settimeout(timeout)
            chan.exec_command(cmd)
            if stdin_data:
                for i in range(0, len(stdin_data), CHUNK):
                    chan.sendall(stdin_data[i:i + CHUNK])
            chan.shutdown_write()

            out_buf, err_buf = [], []
            while True:
                if chan.recv_ready():
                    data = chan.recv(CHUNK)
                    out_buf.append(data)
                    if not quiet:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                if chan.recv_stderr_ready():
                    data = chan.recv_stderr(CHUNK)
                    err_buf.append(data)
                    if not quiet:
                        sys.stderr.buffer.write(data)
                        sys.stderr.buffer.flush()
                if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
                    break
            code = chan.recv_exit_status()
            chan.close()
            return (code,
                    b"".join(out_buf).decode("utf-8", "replace"),
                    b"".join(err_buf).decode("utf-8", "replace"))
        except Exception as exc:  # transient channel failures are retried
            last = exc
    raise RuntimeError("remote exec failed: {}: {}".format(type(last).__name__, last))


def put_file(client, local, remote):
    with open(local, "rb") as fh:
        data = fh.read()
    cmd = "mkdir -p {} && cat > {}".format(
        shlex.quote(os.path.dirname(remote) or "."), shlex.quote(remote))
    code, _, err = run(client, cmd, stdin_data=data, quiet=True)
    if code != 0:
        raise RuntimeError("upload failed (exit={}): {}".format(code, err[:500]))
    print("[put] {} -> {} ({} bytes)".format(local, remote, len(data)))


def put_dir(client, localdir, remotedir):
    localdir = os.path.abspath(localdir)
    parent, name = os.path.split(localdir)
    fd, tmp = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    try:
        import subprocess
        subprocess.run(["tar", "-czf", tmp, "-C", parent, name], check=True)
        size = os.path.getsize(tmp)
        with open(tmp, "rb") as fh:
            data = fh.read()
        cmd = "mkdir -p {} && tar -xzf - -C {}".format(
            shlex.quote(remotedir), shlex.quote(remotedir))
        code, _, err = run(client, cmd, stdin_data=data, quiet=True)
        if code != 0:
            raise RuntimeError("putdir failed (exit={}): {}".format(code, err[:500]))
        print("[putdir] {} -> {} ({} bytes tar.gz)".format(localdir, remotedir, size))
    finally:
        os.unlink(tmp)


def write_stdin(client, remote, mode="600"):
    """Write stdin to a remote file without exposing content in argv."""
    data = sys.stdin.buffer.read()
    cmd = "umask 077; mkdir -p {} && cat > {} && chmod {} {}".format(
        shlex.quote(os.path.dirname(remote) or "."), shlex.quote(remote),
        mode, shlex.quote(remote))
    code, _, err = run(client, cmd, stdin_data=data, quiet=True)
    if code != 0:
        raise RuntimeError("write failed (exit={}): {}".format(code, err[:500]))
    print("[write] -> {} ({} bytes, mode {})".format(remote, len(data), mode))


def get_file(client, remote, local):
    code, out, err = run(client, "cat {}".format(shlex.quote(remote)), quiet=True)
    if code != 0:
        raise RuntimeError("download failed (exit={}): {}".format(code, err[:500]))
    os.makedirs(os.path.dirname(os.path.abspath(local)) or ".", exist_ok=True)
    with open(local, "wb") as fh:
        fh.write(out.encode("utf-8"))
    print("[get] {} -> {} ({} bytes)".format(remote, local, len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["exec", "put", "putdir", "get", "write"])
    ap.add_argument("args", nargs="+")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--timeout", type=int, default=1800)
    ns = ap.parse_args()

    client = connect(ns.host)
    try:
        if ns.action == "exec":
            cmd = " ".join(ns.args)
            code, _, _ = run(client, cmd, timeout=ns.timeout)
            sys.exit(code)
        elif ns.action == "put":
            put_file(client, ns.args[0], ns.args[1])
        elif ns.action == "putdir":
            put_dir(client, ns.args[0], ns.args[1])
        elif ns.action == "get":
            get_file(client, ns.args[0], ns.args[1])
        elif ns.action == "write":
            write_stdin(client, ns.args[0])
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
