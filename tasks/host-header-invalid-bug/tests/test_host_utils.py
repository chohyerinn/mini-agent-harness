import pytest

from host_utils import SecurityError, get_host


def test_missing_host_returns_empty_string():
    assert get_host("http", None, None) == ""


def test_invalid_host_returns_empty_without_trusted_hosts():
    assert get_host("http", "a.test:8080@b.test", None) == ""
    assert get_host("http", "a.test:port", None) == ""


def test_standard_ports_are_removed():
    assert get_host("http", "example.com:80", None) == "example.com"
    assert get_host("https", "example.com:443", None) == "example.com"


def test_server_tuple_is_used_when_header_missing():
    assert get_host("http", None, ("example.com", 80)) == "example.com"
    assert get_host("http", None, ("example.com", 8080)) == "example.com:8080"


def test_untrusted_host_still_raises_when_trusted_hosts_are_configured():
    with pytest.raises(SecurityError):
        get_host("http", "evil.test", None, trusted_hosts=["good.test"])


def test_trusted_host_is_allowed():
    assert get_host("http", "good.test", None, trusted_hosts=["good.test"]) == "good.test"

