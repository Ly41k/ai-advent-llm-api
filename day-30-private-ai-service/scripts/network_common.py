"""Strict private endpoints and exclusive network configuration; no shell eval."""
import ipaddress
import re
from urllib.parse import urlsplit

PRIVATE_V4 = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def lan_ip(value):
    ip = ipaddress.IPv4Address(value)
    if not any(ip in network for network in PRIVATE_V4):
        raise ValueError("RFC1918 LAN IPv4 required")
    return str(ip)


def tailnet_host(value):
    # Canonical full MagicDNS node name, no paths, ports or shell/config tokens.
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.ts\.net", value):
        raise ValueError("Full lowercase node.tailnet.ts.net hostname required")
    return value


def private_origin(value, mode):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.netloc != parsed.netloc.lower()
            or parsed.port == 443):
        raise ValueError("Canonical HTTPS origin required; omit explicit :443")
    if mode == "lan":
        lan_ip(parsed.hostname)
    elif mode == "tailnet":
        tailnet_host(parsed.hostname)
        if parsed.port is not None:
            raise ValueError("Tailnet Serve uses HTTPS port 443")
    else:
        raise ValueError("Network mode required")
    return parsed
