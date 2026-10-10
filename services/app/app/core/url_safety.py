"""Outbound-URL validation for user-supplied provider endpoints (SEC-03, GL#14).

A user-chosen base URL makes the worker issue requests on the user's behalf, so
it must not be able to name the host's own network: loopback, RFC 1918, link
local (including the cloud metadata address), multicast, reserved or any other
non-global address, in IPv4 or IPv6.

The check resolves the host and tests *every* returned address, so a hostname
that points at a private range is refused as firmly as a literal. Decimal,
octal and hex IPv4 spellings (``2130706433``, ``0177.0.0.1``, ``0x7f.1``) are
refused outright rather than normalised: nobody writes an endpoint that way
for a legitimate reason.

This is a point-in-time check. DNS can answer differently at connect time
(rebinding), so the consumer must re-validate immediately before it connects
and must not follow redirects.
"""

import ipaddress
import re
import socket
from urllib.parse import urlsplit

#: Spellings ``inet_aton`` accepts that ``ipaddress`` does not: all digits,
#: or dotted parts that are decimal/octal/hex numbers.
_NUMERIC_HOST = re.compile(r"^(0x[0-9a-f]*|\d+)(\.(0x[0-9a-f]*|\d+))*$", re.IGNORECASE)

#: Named explicitly so the intent survives a stdlib change.
_METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),
        ipaddress.ip_address("fd00:ec2::254"),
    }
)


class UnsafeURLError(ValueError):
    """Raised when a URL may not be fetched on a user's behalf."""


def _check_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Raise ``UnsafeURLError`` unless ``ip`` is a public unicast address."""
    if isinstance(ip, ipaddress.IPv6Address):
        # ::ffff:127.0.0.1 and 6to4 wrap an IPv4 address; judge the inner one.
        if ip.ipv4_mapped is not None:
            _check_ip(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            _check_ip(ip.sixtofour)
    if (
        ip in _METADATA_ADDRESSES
        or ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        raise UnsafeURLError("URL must not point at a private, loopback or reserved address")


def validate_outbound_url(url: str) -> str:
    """Validate that ``url`` is a public http(s) endpoint.

    Performs a blocking DNS lookup; call it off the event loop where that matters.

    Args:
        url: Candidate base URL.

    Returns:
        The URL, stripped.

    Raises:
        UnsafeURLError: If the scheme is not http/https, the URL carries
            credentials, the host is empty or a non-canonical numeric form,
            it cannot be resolved, or any resolved address is not public.
    """
    if not isinstance(url, str):
        raise UnsafeURLError("URL must be a string")
    url = url.strip()
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as e:
        raise UnsafeURLError("URL is not valid") from e
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("URL must start with http:// or https://")
    if not host:
        raise UnsafeURLError("URL must include a host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURLError("URL must not contain credentials")

    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
        if _NUMERIC_HOST.match(host):
            raise UnsafeURLError("URL host must be a name or a canonical IP address") from None

    if literal is not None:
        _check_ip(literal)
        return url

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as e:
        raise UnsafeURLError("URL host could not be resolved") from e
    if not infos:
        raise UnsafeURLError("URL host could not be resolved")
    for info in infos:
        _check_ip(ipaddress.ip_address(str(info[4][0]).split("%", 1)[0]))
    return url
