import re


class SecurityError(Exception):
    pass


_HOST_RE = re.compile(r"^[A-Za-z0-9.\-:\[\]]+$")


def host_is_trusted(host, trusted_hosts=None):
    if not host or not _HOST_RE.match(host):
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
        host = ""

    if scheme in {"http", "ws"}:
        host = host.removesuffix(":80")
    elif scheme in {"https", "wss"}:
        host = host.removesuffix(":443")

    if not host_is_trusted(host, trusted_hosts):
        # BUG: trusted_hosts가 없을 때도 누락/invalid host를 예외로 처리한다.
        raise SecurityError(f"Host {host!r} is not trusted.")

    return host
