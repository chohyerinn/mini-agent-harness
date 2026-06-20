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
        # BUG: prelocalhost처럼 단지 문자열 끝이 같은 호스트도 매칭된다.
        if hostname.endswith(host) or host_with_port.endswith(host):
            return True
    return False
