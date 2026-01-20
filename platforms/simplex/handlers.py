"""SimpleX-specific command handlers.

SimpleX doesn't have inline keyboards, so we use a text-based menu approach
with numbered options and sequential commands.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from commands.core import (
    get_available_pairs,
    create_subscription,
    get_user_subscriptions,
    update_subscription_threshold,
    delete_subscription,
    delete_all_subscriptions,
)
from db import PLATFORM_SIMPLEX
from platforms.base import IncomingMessage
from platforms.simplex.adapter import SimpleXAdapter


class SimpleXCommandHandlers:
    """Handles SimpleX bot commands with text-based menus."""

    def __init__(self, adapter: SimpleXAdapter, session_maker: async_sessionmaker):
        self.adapter = adapter
        self.session_maker = session_maker
        # Store conversation state per user
        self._user_state: dict[str, dict] = {}

    def register_all(self) -> None:
        """Register all command handlers with the adapter."""
        self.adapter.register_command("start", self.handle_start)
        self.adapter.register_command("help", self.handle_help)
        self.adapter.register_command("subscribe", self.handle_subscribe)
        self.adapter.register_command("mysubscriptions", self.handle_mysubscriptions)
        self.adapter.register_command("unsubscribe", self.handle_unsubscribe)
        self.adapter.register_command("select", self.handle_select)
        self.adapter.register_command("threshold", self.handle_threshold)
        self.adapter.register_command("remove", self.handle_remove)
        self.adapter.register_command("edit", self.handle_edit)
        # Register plain text handler for stateful input
        self.adapter.register_text_handler(self.handle_text_input)

    async def handle_start(self, message: IncomingMessage) -> None:
        """Handle /start command."""
        welcome = (
            "Welcome to the Boltz Pro fee alert bot!\n\n"
            "Commands:\n"
            "/subscribe - Subscribe to fee alerts\n"
            "/mysubscriptions - View and manage subscriptions\n"
            "/unsubscribe - Unsubscribe from all alerts\n"
            "/help - Show this help message"
        )
        await self.adapter.send_message(message.conversation_id, welcome)

    async def handle_help(self, message: IncomingMessage) -> None:
        """Handle /help command."""
        await self.handle_start(message)

    async def handle_subscribe(self, message: IncomingMessage) -> None:
        """Handle /subscribe command - show available asset pairs."""
        async with self.session_maker() as session:
            pairs = await get_available_pairs(
                session, PLATFORM_SIMPLEX, message.conversation_id
            )

        if not pairs:
            await self.adapter.send_message(
                message.conversation_id,
                "No pairs available or you're subscribed to all pairs.",
            )
            return

        # Build numbered list of from_assets
        from_assets = list(pairs.keys())
        self._user_state[message.conversation_id] = {
            "step": "select_from",
            "pairs": pairs,
            "from_assets": from_assets,
        }

        menu = "Select the send asset:\n\n"
        for i, asset in enumerate(from_assets, 1):
            menu += f"{i}. {asset}\n"
        menu += "\nReply with the number (e.g. 1)"

        await self.adapter.send_message(message.conversation_id, menu)

    async def handle_select(self, message: IncomingMessage) -> None:
        """Handle /select <number> - process menu selection."""
        user_id = message.conversation_id
        state = self._user_state.get(user_id, {})
        step = state.get("step")

        # Parse selection number
        parts = message.text.split()
        if len(parts) < 2:
            await self.adapter.send_message(
                user_id, "Please specify a number: /select <number>"
            )
            return

        try:
            selection = int(parts[1]) - 1
        except ValueError:
            await self.adapter.send_message(user_id, "Invalid number. Try again.")
            return

        if step == "select_from":
            from_assets = state.get("from_assets", [])
            if selection < 0 or selection >= len(from_assets):
                await self.adapter.send_message(
                    user_id, "Invalid selection. Try again."
                )
                return

            from_asset = from_assets[selection]
            pairs = state.get("pairs", {})
            to_assets = list(pairs.get(from_asset, {}).keys())

            self._user_state[user_id] = {
                "step": "select_to",
                "from_asset": from_asset,
                "to_assets": to_assets,
                "pairs": pairs,
            }

            menu = f"Selected: {from_asset}\n\nSelect the receive asset:\n\n"
            for i, asset in enumerate(to_assets, 1):
                menu += f"{i}. {asset}\n"
            menu += "\nReply with the number"

            await self.adapter.send_message(user_id, menu)

        elif step == "select_to":
            to_assets = state.get("to_assets", [])
            if selection < 0 or selection >= len(to_assets):
                await self.adapter.send_message(
                    user_id, "Invalid selection. Try again."
                )
                return

            to_asset = to_assets[selection]
            from_asset = state.get("from_asset")

            self._user_state[user_id] = {
                "step": "enter_threshold",
                "from_asset": from_asset,
                "to_asset": to_asset,
            }

            msg = (
                f"Selected: {from_asset} -> {to_asset}\n\n"
                "Enter fee threshold percentage:\n"
                "e.g. 0.05 (for 0.05%) or -0.1 (for -0.1%)"
            )
            await self.adapter.send_message(user_id, msg)

        elif step == "select_subscription":
            subscriptions = state.get("subscriptions", [])
            if selection < 0 or selection >= len(subscriptions):
                await self.adapter.send_message(
                    user_id, "Invalid selection. Try again."
                )
                return

            sub = subscriptions[selection]
            self._user_state[user_id] = {
                "step": "subscription_action",
                "subscription_id": sub.id,
                "subscription_desc": sub.pretty_string(),
            }

            msg = (
                f"Selected: {sub.pretty_string()}\n\n"
                "What would you like to do?\n"
                "/edit <threshold> - Change threshold\n"
                "/remove - Remove subscription"
            )
            await self.adapter.send_message(user_id, msg)

    async def handle_threshold(self, message: IncomingMessage) -> None:
        """Handle /threshold <value> - set fee threshold."""
        user_id = message.conversation_id
        state = self._user_state.get(user_id, {})

        if state.get("step") != "enter_threshold":
            await self.adapter.send_message(
                user_id, "Please start with /subscribe first."
            )
            return

        parts = message.text.split()
        if len(parts) < 2:
            await self.adapter.send_message(
                user_id, "Please specify threshold: /threshold <value>"
            )
            return

        threshold = parts[1]
        from_asset = state.get("from_asset")
        to_asset = state.get("to_asset")

        async with self.session_maker() as session:
            success, msg = await create_subscription(
                session,
                PLATFORM_SIMPLEX,
                user_id,
                from_asset,
                to_asset,
                threshold,
            )

        # Clear state
        self._user_state.pop(user_id, None)
        await self.adapter.send_message(user_id, msg)

    async def handle_mysubscriptions(self, message: IncomingMessage) -> None:
        """Handle /mysubscriptions command."""
        user_id = message.conversation_id

        async with self.session_maker() as session:
            subscriptions = await get_user_subscriptions(
                session, PLATFORM_SIMPLEX, user_id
            )

        if not subscriptions:
            await self.adapter.send_message(
                user_id, "You have no active subscriptions."
            )
            return

        self._user_state[user_id] = {
            "step": "select_subscription",
            "subscriptions": subscriptions,
        }

        menu = "Your subscriptions:\n\n"
        for i, sub in enumerate(subscriptions, 1):
            menu += f"{i}. {sub.pretty_string()}\n"
        menu += "\nReply with the number to manage"

        await self.adapter.send_message(user_id, menu)

    async def handle_edit(self, message: IncomingMessage) -> None:
        """Handle /edit <threshold> - edit subscription threshold."""
        user_id = message.conversation_id
        state = self._user_state.get(user_id, {})

        if state.get("step") != "subscription_action":
            await self.adapter.send_message(
                user_id, "Please select a subscription first with /mysubscriptions"
            )
            return

        parts = message.text.split()
        if len(parts) < 2:
            await self.adapter.send_message(
                user_id, "Please specify new threshold: /edit <value>"
            )
            return

        new_threshold = parts[1]
        subscription_id = state.get("subscription_id")

        async with self.session_maker() as session:
            success, msg = await update_subscription_threshold(
                session, subscription_id, new_threshold
            )

        self._user_state.pop(user_id, None)
        await self.adapter.send_message(user_id, msg)

    async def handle_remove(self, message: IncomingMessage) -> None:
        """Handle /remove - remove selected subscription."""
        user_id = message.conversation_id
        state = self._user_state.get(user_id, {})

        if state.get("step") != "subscription_action":
            await self.adapter.send_message(
                user_id, "Please select a subscription first with /mysubscriptions"
            )
            return

        subscription_id = state.get("subscription_id")

        async with self.session_maker() as session:
            success, msg = await delete_subscription(session, subscription_id)

        self._user_state.pop(user_id, None)
        await self.adapter.send_message(user_id, msg)

    async def handle_unsubscribe(self, message: IncomingMessage) -> None:
        """Handle /unsubscribe - remove all subscriptions."""
        user_id = message.conversation_id

        async with self.session_maker() as session:
            success, msg = await delete_all_subscriptions(
                session, PLATFORM_SIMPLEX, user_id
            )

        self._user_state.pop(user_id, None)
        await self.adapter.send_message(user_id, msg)

    async def handle_text_input(self, message: IncomingMessage) -> None:
        """Handle plain text input based on current conversation state."""
        user_id = message.conversation_id
        state = self._user_state.get(user_id, {})
        step = state.get("step")
        text = message.text.strip()

        if not step:
            # No active state - ignore or prompt
            await self.adapter.send_message(
                user_id, "Use /help to see available commands."
            )
            return

        # Handle selection steps (expecting a number)
        if step in ("select_from", "select_to", "select_subscription"):
            try:
                int(text)  # Validate it's a number
            except ValueError:
                await self.adapter.send_message(user_id, "Please enter a valid number.")
                return

            # Create a fake message with /select format and delegate
            message.text = f"/select {text}"
            await self.handle_select(message)

        # Handle threshold entry (expecting a number/decimal)
        elif step == "enter_threshold":
            # Create a fake message with /threshold format and delegate
            message.text = f"/threshold {text}"
            await self.handle_threshold(message)

        else:
            await self.adapter.send_message(
                user_id, "Use /help to see available commands."
            )
