"""Client IP resolution with explicit proxy trust assumptions."""

from __future__ import annotations

import ipaddress

from django.conf import settings
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """Return a normalized client IP.

    ``X-Forwarded-For`` is used only when ``TRUST_PROXY_HEADERS`` is enabled.
    With a single controlled proxy that appends the address it received, the
    last hop is the least spoofable value. Deployments with a different proxy
    topology must overwrite this header at the edge.
    """
    remote_addr = str(request.META.get("REMOTE_ADDR", "")).strip()
    if settings.TRUST_PROXY_HEADERS:
        forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR", ""))
        if forwarded:
            candidate = forwarded.split(",")[-1].strip()
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                # Never trust a malformed forwarded value; fall back to the
                # socket peer rather than accepting attacker-controlled input.
                pass
    if remote_addr:
        try:
            return str(ipaddress.ip_address(remote_addr))
        except ValueError:
            return remote_addr
    return "unknown"
