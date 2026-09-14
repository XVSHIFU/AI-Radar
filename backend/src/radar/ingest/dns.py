"""Opt-in fixed-provider DoH for networks that synthesize non-public DNS answers."""

import asyncio
import ipaddress

import httpx

from .public_transport import Resolver, is_public_address, system_resolver


async def cloudflare_resolver(host: str) -> list[str]:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not is_public_address(str(address)):
            raise ValueError("non-public address")
        return [str(address)]
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=10) as client:
        responses = await asyncio.gather(
            *(
                client.get(
                    "https://cloudflare-dns.com/dns-query",
                    params={"name": host, "type": record_type},
                    headers={"accept": "application/dns-json"},
                )
                for record_type in ("A", "AAAA")
            )
        )
    addresses: set[str] = set()
    for response in responses:
        response.raise_for_status()
        data = response.json()
        if data.get("Status") != 0:
            raise ValueError("DNS lookup failed")
        for answer in data.get("Answer", []):
            if answer.get("type") in (1, 28):
                value = answer["data"]
                if not is_public_address(value):
                    raise ValueError("DNS returned a non-public address")
                addresses.add(value)
    if not addresses:
        raise ValueError("DNS returned no addresses")
    return sorted(addresses, key=lambda value: (":" in value, value))


def configured_resolver(mode: str) -> Resolver:
    if mode == "system":
        return system_resolver
    if mode == "cloudflare":
        return cloudflare_resolver
    raise ValueError("unsupported fetch DNS mode")
