"""Downloads the VPN Gate list, keeps the best USA servers, saves servers.json."""
import json
import urllib.request

URL = "https://www.vpngate.net/api/iphone/"
MAX_SERVERS = 20

with urllib.request.urlopen(URL, timeout=120) as r:
    text = r.read().decode("utf-8", errors="ignore")

servers = []
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
    servers.append({"ip": f[1], "score": score, "config": f[-1].strip()})

servers.sort(key=lambda s: s["score"], reverse=True)
servers = servers[:MAX_SERVERS]

if not servers:
    raise SystemExit("No USA servers found, keeping the old file.")

with open("servers.json", "w") as out:
    json.dump(servers, out)

print(f"Saved {len(servers)} USA servers")
