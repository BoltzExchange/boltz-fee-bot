"""E2E tests for SimpleX bot commands.

These tests simulate a real SimpleX user interacting with the bot
via the SimpleX adapter's test endpoints.

Requirements:
- Docker containers running (docker compose up)

Run with: pytest tests/e2e/test_simplex_commands.py -v
"""

import pytest
import asyncio
import json
import httpx
import websockets


# Override the bot fixture - we use Docker containers, not local bot
@pytest.fixture(autouse=True)
def bot():
    """Override the e2e bot fixture - SimpleX tests use Docker containers."""
    yield  # No-op: we use the Docker containers


class SimplexTestSession:
    """Test session for SimpleX e2e tests - creates fresh connections per test."""

    def __init__(
        self, adapter_url: str = "http://localhost:3000", contact_id: int = 99999
    ):
        self.adapter_url = adapter_url
        self.adapter_ws_url = adapter_url.replace("http://", "ws://")
        self.contact_id = contact_id

    async def send_message(self, text: str) -> str:
        """Send a message and get the bot's response."""
        async with httpx.AsyncClient(base_url=self.adapter_url, timeout=10.0) as client:
            # Connect WebSocket to receive response
            async with websockets.connect(self.adapter_ws_url) as ws:
                # Send the simulated message
                await client.post(
                    "/test/simulate_message",
                    json={
                        "contactId": self.contact_id,
                        "displayName": "TestUser",
                        "text": text,
                    },
                )

                # Wait for bot response with timeout
                try:
                    async with asyncio.timeout(5.0):
                        async for message in ws:
                            event = json.loads(message)
                            if (
                                event.get("type") == "botResponse"
                                and event.get("contactId") == self.contact_id
                            ):
                                return event.get("text", "")
                except asyncio.TimeoutError:
                    raise TimeoutError(f"No response from bot for message: {text}")

        raise TimeoutError(f"No response from bot for message: {text}")

    async def send_messages(self, messages: list[str]) -> list[str]:
        """Send multiple messages and collect responses."""
        responses = []
        for msg in messages:
            response = await self.send_message(msg)
            responses.append(response)
        return responses


async def check_adapter_ready():
    """Check if the SimpleX adapter is ready."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:3000/health")
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "connected"
    except Exception:
        pass
    return False


@pytest.fixture
def simplex():
    """Create a SimpleX test session."""
    return SimplexTestSession()


@pytest.mark.asyncio
async def test_simplex_help(simplex: SimplexTestSession):
    """Test /help command."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    response = await simplex.send_message("/help")
    assert "Commands" in response or "/subscribe" in response


@pytest.mark.asyncio
async def test_simplex_subscribe_flow(simplex: SimplexTestSession):
    """Test the complete subscribe flow."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Clear existing subscriptions
    await simplex.send_message("/unsubscribe")

    # Start subscription
    response = await simplex.send_message("/subscribe")
    assert "Select" in response or "send asset" in response.lower()
    assert "1." in response

    # Select first send asset
    response = await simplex.send_message("1")
    assert "receive" in response.lower() or "Selected" in response

    # Select first receive asset
    response = await simplex.send_message("1")
    assert "threshold" in response.lower()

    # Enter threshold
    response = await simplex.send_message("0.5")
    assert "subscribed" in response.lower()


@pytest.mark.asyncio
async def test_simplex_mysubscriptions_empty(simplex: SimplexTestSession):
    """Test /mysubscriptions when empty."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Clear subscriptions
    await simplex.send_message("/unsubscribe")

    response = await simplex.send_message("/mysubscriptions")
    assert (
        "no" in response.lower()
        or "not subscribed" in response.lower()
        or "no active" in response.lower()
    )


@pytest.mark.asyncio
async def test_simplex_mysubscriptions_with_data(simplex: SimplexTestSession):
    """Test /mysubscriptions shows subscriptions."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Clear and create subscription
    await simplex.send_message("/unsubscribe")
    await simplex.send_message("/subscribe")
    await simplex.send_message("1")
    await simplex.send_message("1")
    await simplex.send_message("0.5")

    # Check subscriptions
    response = await simplex.send_message("/mysubscriptions")
    assert "1." in response or "subscription" in response.lower()


@pytest.mark.asyncio
async def test_simplex_edit_subscription(simplex: SimplexTestSession):
    """Test editing a subscription."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Create subscription
    await simplex.send_message("/unsubscribe")
    await simplex.send_message("/subscribe")
    await simplex.send_message("1")
    await simplex.send_message("1")
    await simplex.send_message("0.5")

    # Select subscription
    await simplex.send_message("/mysubscriptions")
    response = await simplex.send_message("1")
    assert "/edit" in response or "edit" in response.lower()

    # Edit threshold
    response = await simplex.send_message("/edit 0.6")
    assert "updated" in response.lower() or "success" in response.lower()


@pytest.mark.asyncio
async def test_simplex_remove_subscription(simplex: SimplexTestSession):
    """Test removing a subscription."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Create subscription
    await simplex.send_message("/unsubscribe")
    await simplex.send_message("/subscribe")
    await simplex.send_message("1")
    await simplex.send_message("1")
    await simplex.send_message("0.5")

    # Select and remove
    await simplex.send_message("/mysubscriptions")
    await simplex.send_message("1")
    response = await simplex.send_message("/remove")
    assert "removed" in response.lower()

    # Verify empty
    response = await simplex.send_message("/mysubscriptions")
    assert "no" in response.lower() or "not subscribed" in response.lower()


@pytest.mark.asyncio
async def test_simplex_unsubscribe_all(simplex: SimplexTestSession):
    """Test /unsubscribe removes all subscriptions."""
    if not await check_adapter_ready():
        pytest.skip("SimpleX adapter not available")

    # Create subscription
    await simplex.send_message("/subscribe")
    await simplex.send_message("1")
    await simplex.send_message("1")
    await simplex.send_message("0.5")

    # Unsubscribe
    response = await simplex.send_message("/unsubscribe")
    assert (
        "removed" in response.lower()
        or "success" in response.lower()
        or "all" in response.lower()
    )
