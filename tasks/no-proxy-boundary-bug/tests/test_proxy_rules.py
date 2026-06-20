import pytest

from proxy_rules import should_bypass_proxy


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost/", True),
        ("http://anotherdomain.com:8888/", True),
        ("http://newdomain.com:1234/", True),
        ("http://www.newdomain.com:1234/", True),
        ("http://foo.d.o.t/", True),
        ("http://d.o.t/", True),
        ("http://prelocalhost/", False),
        ("http://newdomain.com/", False),
        ("http://newdomain.com:1235/", False),
    ],
)
def test_no_proxy_respects_domain_boundaries(url, expected):
    no_proxy = "localhost, anotherdomain.com, newdomain.com:1234, .d.o.t"
    assert should_bypass_proxy(url, no_proxy) is expected
