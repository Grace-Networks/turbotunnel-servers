"""Downloads the VPN Gate list, keeps USA servers that actually respond,
and saves servers.json."""
import base64
import json
import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://www.vpngate.net/api/iphone/"
MAX_SERVERS = 30        # how many servers to keep in servers.json
MAX_UDP = 10            # UDP servers can't be tested, so keep only a few
CHECK_TIMEOUT = 5       # seconds to wait for a TCP server to answer

with urllib.request.urlopen(URL, timeout=120) as r:
    text = r.read().decode("utf-8", errors="ignore")


def parse_config(b64):
    """Returns (proto, host, port) from the base64 .ovpn config, or None."""
    try:
        cfg = base64.b64decode(b64).decode("utf-8", errors="ignore")
    except Exception:
        return None
    proto = None
    remote = None
    for line in cfg.splitlines():
        t = line.strip()
        if t.startswith(("#", ";")):
            continue
        m = re.match(r"proto\s+(tcp|udp)", t)
        if m and proto is None:
            proto = m.group(1)
        m = re.match(r"remote\s+(\S+)\s+(\d+)", t)
        if m and remote is None:
            remote = (m.group(1), int(m.group(2)))
    if not proto or not remote:
        return None
    return proto, remote[0], remote[1]


candidates = []
for line in text.splitlines():
    if not line or line.startswith("*") or line.startswith("#"):
        continue
    f = line.split(",")
    if len(f) < 15 or f[6] != "US":
        continue
    try:
        score = int(f[2])
    except ValueError:
        score = 0
    config = f[-1].strip()
    info = parse_config(config)
    if info is None:
        continue
    proto, host, port = info
    candidates.append({
        "ip": f[1],
        "score": score,
        "config": config,
        "proto": proto,
        "host": host,
        "port": port,
    })

print(f"{len(candidates)} USA servers in the VPN Gate list")


def tcp_alive(c):
    try:
        with socket.create_connection((c["host"], c["port"]), timeout=CHECK_TIMEOUT):
            return True
    except OSError:
        return False


tcp = [c for c in candidates if c["proto"] == "tcp"]
udp = [c for c in candidates if c["proto"] == "udp"]

with ThreadPoolExecutor(max_workers=40) as pool:
    results = list(pool.map(tcp_alive, tcp))
tcp_ok = [c for c, ok in zip(tcp, results) if ok]
print(f"{len(tcp_ok)} of {len(tcp)} TCP servers responded")

tcp_ok.sort(key=lambda c: c["score"], reverse=True)
udp.sort(key=lambda c: c["score"], reverse=True)

# Working TCP servers first, then a few UDP ones as a backup.
chosen = tcp_ok + udp[:MAX_UDP]
chosen = chosen[:MAX_SERVERS]

if not chosen:
    raise SystemExit("No usable USA servers found, keeping the old file.")

servers = [
    {"ip": c["ip"], "score": c["score"], "config": c["config"]}
    for c in chosen
]

with open("servers.json", "w") as out:
    json.dump(servers, out)

print(f"Saved {len(servers)} USA servers")
