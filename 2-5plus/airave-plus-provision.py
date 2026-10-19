#!/usr/bin/env python3
"""Collect Airave 2.5+ provisioning fields through its brief boot Telnet window.

Uses only Python's standard library. The unit's web interface must be reachable
at 192.168.17.1 with its administrator credentials. The script reboots it once,
logs in as root during startup, and captures a short command's output before
the startup firewall closes Telnet. --command runs a different root command.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import select
import socket
import threading
import time
import urllib.request
import uuid


class Telnet:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.sock.setblocking(False)
        self.buf = b""

    def read_until(self, markers, timeout: float):
        if isinstance(markers, bytes):
            markers = (markers,)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for marker in markers:
                pos = self.buf.find(marker)
                if pos >= 0:
                    data, self.buf = self.buf[:pos], self.buf[pos + len(marker) :]
                    return data, marker
            ready, _, _ = select.select([self.sock], [], [], 0.1)
            if not ready:
                continue
            try:
                chunk = self.sock.recv(8192)
            except BlockingIOError:
                continue
            if not chunk:
                break
            self.buf += self.negotiate(chunk)
        data, self.buf = self.buf, b""
        return data, None

    def negotiate(self, chunk: bytes) -> bytes:
        plain = bytearray()
        i = 0
        while i < len(chunk):
            if chunk[i] != 255:
                plain.append(chunk[i])
                i += 1
            elif i + 1 >= len(chunk):
                break
            elif chunk[i + 1] == 255:
                plain.append(255)
                i += 2
            elif chunk[i + 1] in (251, 252, 253, 254) and i + 2 < len(chunk):
                if chunk[i + 1] in (251, 253):
                    self.sock.sendall(bytes((255, 254 if chunk[i + 1] == 251 else 252, chunk[i + 2])))
                i += 3
            elif chunk[i + 1] == 250:
                end = chunk.find(b"\xff\xf0", i + 2)
                i = len(chunk) if end < 0 else end + 2
            else:
                i += 2
        return bytes(plain)

    def write(self, value: str):
        self.sock.sendall(value.encode())

    def close(self):
        self.sock.close()


def connect_telnet(host: str) -> Telnet | None:
    sock = socket.socket()
    sock.settimeout(0.15)
    try:
        sock.connect((host, 23))
        return Telnet(sock)
    except OSError:
        sock.close()
        return None


def reboot(host: str, username: str, password: str):
    base = f"http://{host}/"
    passwords = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None, base, username, password)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPDigestAuthHandler(passwords),
    )
    opener.open(base + "goform/reboot", timeout=8).read()


def default_command() -> str:
    keys = "serialno|nai_domain|eap_preshared_key|ike_group_key|username|password"
    return (
        "id; uname -a; cat /proc/mtd; "
        f"fw_printenv 2>/dev/null | grep -E '^({keys})='; "
        f"strings /dev/mtdblock8 2>/dev/null | grep -E '^({keys})='; "
        "grep -E '^(acsUserName|acsPassword)' "
        "/conf_files/config/nptr_config/nptr69.conf 2>/dev/null"
    )


def try_root(tn: Telnet, password: str, command: str, marker: bytes):
    try:
        _, prompt = tn.read_until((b"login:", b"Login:"), 5)
        if not prompt:
            return b"", False
        tn.write("root\n")
        _, prompt = tn.read_until(b"assword:", 3)
        if not prompt:
            return b"", False
        half = marker.decode().split("_", 1)
        finish = f"_end_a={half[0]}; _end_b={half[1]}; echo ${{_end_a}}_${{_end_b}}"
        tn.write(password + "\n" + command + "; " + finish + "\n")
        data, seen = tn.read_until(marker, 8)
        return data, seen is not None
    except OSError:
        return b"", False


def parse_fields(raw: str):
    keys = {"serialno", "nai_domain", "eap_preshared_key", "ike_group_key", "username", "password"}
    env = {}
    for line in raw.splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_]+)=([^\s]*)", line.strip())
        if not match:
            continue
        key, value = match.groups()
        if key in keys and value and set(value) != {"*"}:
            env[key] = value
    missing = keys - env.keys()
    if missing:
        raise ValueError("Missing fields: " + ", ".join(sorted(missing)))
    return {
        "FEID": env["serialno"],
        "IKE_GROUP_KEY": env["ike_group_key"],
        "EAP_IDENTITY": env["serialno"] + "@" + env["nai_domain"],
        "EAP_PASSWORD": env["eap_preshared_key"],
        "ACS_USERNAME": env["username"],
        "ACS_PASSWORD": env["password"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.17.1")
    parser.add_argument("--web-user", default="admin")
    parser.add_argument("--web-password", default="admin")
    parser.add_argument("--root-password", default="root")
    parser.add_argument("--command", help="Run this shell command as root instead of collecting provisioning fields")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--from-capture", type=pathlib.Path, help="Parse a previous raw capture without rebooting")
    args = parser.parse_args()
    output = args.output or pathlib.Path(__file__).with_name(
        "airave-plus-command.txt" if args.command else "airave-plus-provision.txt"
    )

    if args.from_capture:
        raw = args.from_capture.read_text(errors="replace")
    else:
        print("Rebooting Airave; watching for Telnet...", flush=True)
        reboot(args.host, args.web_user, args.web_password)
        deadline = time.monotonic() + 70
        first = None
        while time.monotonic() < deadline and first is None:
            first = connect_telnet(args.host)
            if first is None:
                time.sleep(0.08)
        if first is None:
            raise SystemExit("Telnet did not open during boot")
        sessions = [first]
        for _ in range(2):
            time.sleep(0.2)
            extra = connect_telnet(args.host)
            if extra:
                sessions.append(extra)
        tag = uuid.uuid4().hex
        marker = (tag[:16] + "_" + tag[16:]).encode()
        command = "id; " + args.command if args.command else default_command()
        results = []
        lock = threading.Lock()

        def worker(index: int, session: Telnet):
            data, complete = try_root(session, args.root_password, command, marker)
            with lock:
                results.append((index, data, complete))

        threads = [threading.Thread(target=worker, args=(i, s)) for i, s in enumerate(sessions)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for session in sessions:
            session.close()
        _, data, complete = max(results, key=lambda result: (result[2], len(result[1])))
        if not complete or b"uid=0(root)" not in data:
            if data:
                partial = output.with_name(output.name + ".partial")
                partial.write_bytes(data)
                print("Partial boot capture:", partial.resolve())
            raise SystemExit("Root command did not complete in the boot window")
        raw = data.decode("utf-8", "replace")

    if args.command:
        output.write_text(raw, encoding="utf-8")
    else:
        fields = parse_fields(raw)
        output.write_text("".join(f"{key}={value}\n" for key, value in fields.items()), encoding="utf-8")
    print("Saved:", output.resolve())


if __name__ == "__main__":
    main()
