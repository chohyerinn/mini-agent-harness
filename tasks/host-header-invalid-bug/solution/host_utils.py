import re


class SecurityError(Exception):
    pass


_HOST_RE = re.compile(r"^[A-Za-z0-9.\-:\[\]]+$")


def _has_valid_host_syntax(host):
    if not host or not _HOST_RE.match(host):
        return False
    if ":" in host and not host.startswith("["):
        _, _, port = host.rpartition(":")
        if port and not port.isdigit():
            return False
    return True


def host_is_trusted(host, trusted_hosts=None):
    if not _has_valid_host_syntax(host):
        return False
    if not trusted_hosts:
        return True
    return host in trusted_hosts


def get_host(scheme, host_header=None, server=None, trusted_hosts=None):
    if host_header:
        host = host_header
    elif server is not None:
        host, port = server
        if port is not None:
            host = f"{host}:{port}"
    else:
        return ""

    if scheme in {"http", "ws"}:
        host = host.removesuffix(":80")
    elif scheme in {"https", "wss"}:
        host = host.removesuffix(":443")

    if not host_is_trusted(host, trusted_hosts):
        if trusted_hosts:
            raise SecurityError(f"Host {host!r} is not trusted.")
        return ""

    return host
