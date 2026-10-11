"""Generate a NEW private LAN Caddy configuration; never start/publish services."""
import argparse
import json
import os
from pathlib import Path
import sys

from check_storage import ROOT
from network_common import lan_ip, tailnet_host


def port(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise ValueError("port must be 1024..65535")
    return number


def generate(address, tailnet, api_port, lan_port, output):
    address = lan_ip(address)
    tailnet = tailnet_host(tailnet) if tailnet else None
    api_port, lan_port = port(api_port), port(lan_port)
    if api_port == lan_port:
        raise ValueError("Separate API and LAN ports required")
    text = (ROOT/"deploy/Caddyfile.lan.template").read_text()
    for key, value in {"LAN_IP":address, "API_PORT":api_port, "LAN_PORT":lan_port}.items():
        text = text.replace("@@"+key+"@@", str(value))
    origins = [f"https://{address}:{lan_port}"]
    if tailnet:
        origins.append("https://"+tailnet)
    data = {"format":"bublik-network-config-v1", "api_port":api_port,
            "lan_ip":address, "lan_port":lan_port, "tailnet_host":tailnet,
            "origins":origins, "api_bind":"127.0.0.1", "proxy_mode":True}
    output = Path(output).expanduser().absolute()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    # Existing directory/CA/config is never replaced, including symlink aliases.
    for name, content in (("Caddyfile", text), ("network.json", json.dumps(data,indent=2)+"\n")):
        fd = os.open(output/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,"w") as f:
            f.write(content)
    for directory in ("caddy-data", "caddy-config"):
        (output/directory).mkdir(mode=0o700)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lan-ip", required=True)
    parser.add_argument("--tailnet-host")
    parser.add_argument("--api-port",type=port,default=8000)
    parser.add_argument("--lan-port",type=port,default=8443)
    parser.add_argument("--output",type=Path,required=True,help="NEW directory with existing parent")
    args = parser.parse_args()
    try:
        result = generate(args.lan_ip,args.tailnet_host,args.api_port,args.lan_port,args.output)
    except (ValueError,OSError):
        parser.error("Invalid private endpoint/ports or output directory already exists/unwritable")
    print(json.dumps({"config":str(args.output), "origins":result["origins"]}))
    return 0


if __name__ == "__main__": sys.exit(main())
