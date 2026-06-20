from urllib.parse import urlparse


def should_bypass_proxy(url, no_proxy):
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    host_with_port = hostname
    if parsed.port is not None:
        host_with_port += f":{parsed.port}"

    for host in (item.strip() for item in no_proxy.split(",")):
        if not host:
            continue
        host = host.lstrip(".")
        if hostname == host or host_with_port == host:
            return True
        host = "." + host
        if hostname.endswith(host) or host_with_port.endswith(host):
            return True
    return False
