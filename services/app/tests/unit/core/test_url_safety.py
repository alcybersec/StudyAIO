"""SEC-03 (GL#14): user-supplied provider URLs may not name the host's network."""

import socket
from unittest.mock import patch

import pytest

from app.core.url_safety import UnsafeURLError, validate_outbound_url


def _resolves_to(*addrs: str):
    def fake(host, port, *a, **kw):
        return [(socket.AF_INET6 if ":" in x else socket.AF_INET, 1, 6, "", (x, 0)) for x in addrs]

    return patch("app.core.url_safety.socket.getaddrinfo", side_effect=fake)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://127.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]:11434",
        "http://[::ffff:127.0.0.1]/",
        "http://[fd00:ec2::254]/",
        "http://[fe80::1]/",
        "http://10.0.0.5",
        "http://172.16.3.4",
        "http://192.168.1.10",
        "http://100.64.0.1",
        "http://0.0.0.0",
        "http://224.0.0.1",
        "http://240.0.0.1",
        "http://2130706433/",  # decimal 127.0.0.1
        "http://0177.0.0.1/",  # octal
        "http://0x7f.0.0.1/",  # hex
        "http://0x7f000001/",
    ],
)
def test_literal_and_numeric_hosts_are_refused(url):
    with pytest.raises(UnsafeURLError):
        validate_outbound_url(url)


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://example.com", "gopher://example.com", "example.com", "http://"],
)
def test_non_http_or_hostless_refused(url):
    with pytest.raises(UnsafeURLError):
        validate_outbound_url(url)


def test_credentials_in_url_refused():
    with _resolves_to("93.184.216.34"), pytest.raises(UnsafeURLError):
        validate_outbound_url("http://user:pw@example.com/")


def test_hostname_resolving_private_is_refused():
    with _resolves_to("10.1.2.3"), pytest.raises(UnsafeURLError):
        validate_outbound_url("https://innocent.example.com")


def test_hostname_with_any_private_answer_is_refused():
    with _resolves_to("93.184.216.34", "127.0.0.1"), pytest.raises(UnsafeURLError):
        validate_outbound_url("https://mixed.example.com")


def test_hostname_resolving_private_ipv6_refused():
    with _resolves_to("::1"), pytest.raises(UnsafeURLError):
        validate_outbound_url("https://v6.example.com")


def test_unresolvable_host_refused():
    with (
        patch("app.core.url_safety.socket.getaddrinfo", side_effect=socket.gaierror),
        pytest.raises(UnsafeURLError),
    ):
        validate_outbound_url("https://nope.invalid")


def test_public_hostname_accepted():
    with _resolves_to("93.184.216.34"):
        assert validate_outbound_url(" https://api.example.com/v1 ") == "https://api.example.com/v1"


def test_public_ip_literal_accepted():
    assert validate_outbound_url("https://93.184.216.34:8443") == "https://93.184.216.34:8443"
