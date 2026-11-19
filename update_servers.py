"""Downloads the VPN Gate list, tests the servers, and saves servers.json.
USA servers come first, then servers from other countries."""
import base64
import json
import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://www.vpngate.net/api/iphone/"
MAX_SERVERS = 40        # how many servers to keep in servers.json
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
    if len(f) < 15:
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
        "country": f[6],
        "config": config,
        "proto": proto,
        "host": host,
        "port": port,
    })

print(f"{len(candidates)} servers in the VPN Gate list")
print(f"{sum(1 for c in candidates if c['country'] == 'US')} of them are in the USA")


def tcp_alive(c):
    try:
        with socket.create_connection((c["host"], c["port"]), timeout=CHECK_TIMEOUT):
            return True
    except OSError:
        return False


tcp = [c for c in candidates if c["proto"] == "tcp"]
udp = [c for c in candidates if c["proto"] == "udp"]

with ThreadPoolExecutor(max_workers=60) as pool:
    results = list(pool.map(tcp_alive, tcp))
tcp_ok = [c for c, ok in zip(tcp, results) if ok]
print(f"{len(tcp_ok)} of {len(tcp)} TCP servers responded")


def order(c):
    # USA first, then the rest; best score first inside each group.
    return (0 if c["country"] == "US" else 1, -c["score"])


tcp_ok.sort(key=order)
udp.sort(key=order)

chosen = tcp_ok + udp[:MAX_UDP]
chosen = chosen[:MAX_SERVERS]

if not chosen:
    raise SystemExit("No usable servers found, keeping the old file.")

servers = [
    {"ip": c["ip"], "score": c["score"], "country": c["country"], "config": c["config"]}
    for c in chosen
]

with open("servers.json", "w") as out:
    json.dump(servers, out)

print(f"Saved {len(servers)} servers")
