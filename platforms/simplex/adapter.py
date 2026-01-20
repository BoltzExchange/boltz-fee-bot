"""SimpleX adapter that communicates with the TypeScript adapter service."""

import asyncio
import json
import logging

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from platforms.base import BotPlatform, PlatformUser, IncomingMessage, CommandHandler


class SimpleXAdapter(BotPlatform):
    """SimpleX Chat platform adapter using the TypeScript adapter service."""

    def __init__(self, adapter_url: str = "http://localhost:3000"):
        self.adapter_url = adapter_url
        self.adapter_ws_url = adapter_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        self.ws: ClientConnection | None = None
        self._command_handlers: dict[str, CommandHandler] = {}
        self._text_handler: CommandHandler | None = None  # Handler for plain text
        self._running = False
        self._listen_task: asyncio.Task | None = None
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._http_client: httpx.AsyncClient | None = None

    @property
    def platform_name(self) -> str:
        return "simplex"

    async def start(self) -> None:
        """Connect to SimpleX adapter and start listening for events."""
        self._running = True
        self._http_client = httpx.AsyncClient(base_url=self.adapter_url, timeout=30.0)
        await self._wait_for_adapter()
        await self._connect_ws()
        self._listen_task = asyncio.create_task(self._listen_loop())
        logging.info(
            f"SimpleXAdapter started, connected to adapter at {self.adapter_url}"
        )

    async def stop(self) -> None:
        """Disconnect from SimpleX adapter."""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logging.info("SimpleXAdapter stopped")

    async def _wait_for_adapter(self) -> None:
        """Wait for the adapter service to be ready."""
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = await self._http_client.get("/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "connected":
                        logging.info("SimpleX adapter is ready and connected")
                        return
                    logging.info(f"Adapter status: {data.get('status')}, waiting...")
            except Exception as e:
                logging.debug(f"Adapter not ready yet: {e}")

            await asyncio.sleep(2)

        raise RuntimeError("SimpleX adapter did not become ready in time")

    async def _connect_ws(self) -> None:
        """Connect to adapter WebSocket for events."""
        try:
            self.ws = await websockets.connect(self.adapter_ws_url)
            self._reconnect_delay = 1.0
            logging.info(
                f"Connected to SimpleX adapter WebSocket at {self.adapter_ws_url}"
            )
        except Exception as e:
            logging.error(f"Failed to connect to SimpleX adapter WebSocket: {e}")
            raise

    async def _listen_loop(self) -> None:
        """Main event loop for receiving events from adapter."""
        logging.info("SimpleX adapter event listener started")
        while self._running:
            try:
                if self.ws is None:
                    await self._connect_ws()

                async for message in self.ws:
                    try:
                        event = json.loads(message)
                        await self._handle_event(event)
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse adapter event: {e}")
                    except Exception as e:
                        logging.error(f"Error handling adapter event: {e}")

            except websockets.ConnectionClosed:
                logging.warning("Adapter WebSocket connection closed")
                self.ws = None
                if self._running:
                    await self._reconnect()
            except Exception as e:
                logging.error(f"Adapter listener error: {e}")
                self.ws = None
                if self._running:
                    await self._reconnect()

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        logging.info(f"Reconnecting to adapter in {self._reconnect_delay} seconds...")
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(
            self._reconnect_delay * 2, self._max_reconnect_delay
        )
        try:
            await self._connect_ws()
        except Exception:
            pass  # Will retry in next loop iteration

    async def _handle_event(self, event: dict) -> None:
        """Process events from the adapter."""
        event_type = event.get("type")

        if event_type == "newMessage":
            await self._handle_new_message(event)
        elif event_type == "contactConnected":
            await self._handle_contact_connected(event)
        else:
            logging.debug(f"Unhandled adapter event: {event_type}")

    async def _handle_new_message(self, event: dict) -> None:
        """Handle new message event from adapter."""
        contact_id = event.get("contactId")
        display_name = event.get("displayName", "")
        text = event.get("text", "")
        message_id = event.get("messageId")

        if not contact_id or not text:
            return

        logging.info(f"SimpleX message from {display_name} ({contact_id}): {text}")

        user = PlatformUser(
            platform="simplex",
            platform_user_id=str(contact_id),
            display_name=display_name,
        )
        message = IncomingMessage(
            user=user,
            text=text,
            conversation_id=str(contact_id),
            message_id=str(message_id) if message_id else None,
        )

        if text.startswith("/"):
            parts = text[1:].split(maxsplit=1)
            command = parts[0].lower()

            if command in self._command_handlers:
                try:
                    await self._command_handlers[command](message)
                except Exception as e:
                    logging.error(f"Error handling SimpleX command {command}: {e}")
            else:
                # Unknown command - send help
                await self.send_message(
                    str(contact_id),
                    f"Unknown command: /{command}. Use /help to see available commands.",
                )
        elif self._text_handler:
            # Handle plain text (numbers, etc.) via text handler
            try:
                await self._text_handler(message)
            except Exception as e:
                logging.error(f"Error handling SimpleX text message: {e}")

    async def _handle_contact_connected(self, event: dict) -> None:
        """Handle new contact connection."""
        contact_id = event.get("contactId")
        display_name = event.get("displayName", "")

        if contact_id:
            logging.info(
                f"New SimpleX contact connected: {display_name} ({contact_id})"
            )

            # Trigger start handler if registered
            if "start" in self._command_handlers:
                user = PlatformUser(
                    platform="simplex",
                    platform_user_id=str(contact_id),
                    display_name=display_name,
                )
                message = IncomingMessage(
                    user=user,
                    text="/start",
                    conversation_id=str(contact_id),
                )
                try:
                    await self._command_handlers["start"](message)
                except Exception as e:
                    logging.error(f"Error handling start for new contact: {e}")

    async def send_message(self, conversation_id: str, text: str) -> None:
        """Send a message to a SimpleX contact via the adapter."""
        if self._http_client is None:
            raise RuntimeError("SimpleXAdapter not connected")

        try:
            response = await self._http_client.post(
                "/send",
                json={
                    "contactId": int(conversation_id),
                    "text": text,
                },
            )
            response.raise_for_status()
            logging.debug(f"Sent message to SimpleX contact {conversation_id}")
        except Exception as e:
            logging.error(f"Failed to send message to {conversation_id}: {e}")
            raise

    def register_command(self, command: str, handler: CommandHandler) -> None:
        """Register a command handler."""
        self._command_handlers[command] = handler
        logging.debug(f"Registered SimpleX command handler: /{command}")

    def register_text_handler(self, handler: CommandHandler) -> None:
        """Register a handler for plain text messages (non-commands)."""
        self._text_handler = handler
        logging.debug("Registered SimpleX plain text handler")
