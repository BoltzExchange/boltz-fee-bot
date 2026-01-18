import base64
import logging

import httpx

from settings import NtfySettings


def _build_headers(settings: NtfySettings) -> dict[str, str]:
    """Build authentication headers for ntfy requests."""
    headers: dict[str, str] = {}
    if settings.ntfy_auth_header:
        headers["Authorization"] = settings.ntfy_auth_header
    elif settings.ntfy_basic_user and settings.ntfy_basic_pass:
        token = f"{settings.ntfy_basic_user}:{settings.ntfy_basic_pass}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(token).decode('ascii')}"
    return headers


async def publish(
    client: httpx.AsyncClient,
    settings: NtfySettings,
    topic: str,
    message: str,
    *,
    title: str | None = None,
    priority: str | None = None,
) -> bool:
    """
    Publish a message to an ntfy topic.

    Returns:
        True if published successfully, False otherwise
    """
    url = f"{settings.ntfy_base_url.rstrip('/')}/{topic}"
    headers = _build_headers(settings)

    if title:
        headers["Title"] = title

    effective_priority = priority or settings.ntfy_default_priority
    if effective_priority:
        headers["Priority"] = effective_priority

    try:
        response = await client.post(
            url,
            content=message.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logging.error(f"Failed to publish to ntfy topic '{topic}': {e}")
        return False
