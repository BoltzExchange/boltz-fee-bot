# Architecture Documentation

This document describes the multi-platform architecture of the Boltz Pro Fee Bot.

## Overview

The bot monitors [Boltz Pro](https://pro.boltz.exchange) fees and sends alerts to users when fees cross their configured thresholds. It supports multiple messaging platforms through a plugin-based adapter system.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Bot Orchestrator (bot.py)                      │
│  - Fee monitoring loop                                                   │
│  - Subscription management                                               │
│  - Notification dispatch                                                 │
└───────────────┬─────────────────────────────────────────┬───────────────┘
                │                                         │
       ┌────────▼────────┐                      ┌─────────▼─────────┐
       │ TelegramAdapter │                      │  SimpleXAdapter   │
       │ (python-telegram│                      │  (TypeScript      │
       │     -bot)       │                      │   service)        │
       └────────┬────────┘                      └─────────┬─────────┘
                │                                         │
                ▼                                         ▼
         Telegram API                              SimpleX Adapter
                                                   (TypeScript)
                                                   with embedded
                                                   chat core
```

## Platform Abstraction Layer

### Base Interface (`platforms/base.py`)

All platform adapters implement the `BotPlatform` abstract base class:

```python
class BotPlatform(ABC):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_message(self, conversation_id: str, text: str) -> None: ...
    def register_command(self, command: str, handler: CommandHandler) -> None: ...
    @property
    def platform_name(self) -> str: ...
```

### Data Classes

- `PlatformUser`: Normalized user representation across platforms
- `IncomingMessage`: Normalized message with user, text, and conversation ID
- `CommandHandler`: Type alias for async command handler functions

## Platform Implementations

### Telegram Adapter (`platforms/telegram/`)

Uses the `python-telegram-bot` library directly. The existing Telegram command handlers
(ConversationHandler-based with inline keyboards) are preserved for full feature support.

For notifications, a lightweight wrapper adapter provides the `BotPlatform` interface
while the native Application handles command processing.

### SimpleX Adapter (`platforms/simplex/`)

SimpleX Chat uses the official `simplex-chat` npm package (v6.5.0-beta.4.4) which embeds
the chat core as a native Node.js addon:

```
┌─────────────────┐     HTTP/WS      ┌──────────────────────────────────┐
│  Python Bot     │◄────────────────►│  SimpleX Adapter (TypeScript)    │
│  (SimpleX       │  POST /send      │  with embedded chat core         │
│   Adapter)      │  WS events       │  (simplex-chat npm package)      │
└─────────────────┘                  └──────────────────────────────────┘
```

**Architecture Benefits (v6.5.0-beta):**

1. **No separate CLI container** - The chat core is embedded as a native Node.js addon
2. **Proper SDK methods** - Uses `apiSendTextMessage()` instead of raw CLI commands
3. **Reliable event handling** - Built-in event loop with proper async iteration
4. **Automatic profile management** - Bot profile and address created on first run
5. **Simplified deployment** - One less container to manage

**Adapter API:**

- `GET /health` - Connection status check
- `POST /send` - Send message to contact: `{"contactId": 5, "text": "Hello"}`
- `GET /address` - Get bot's SimpleX address
- `GET /contacts` - List contacts
- `WebSocket /` - Event stream (newMessage, contactConnected)

### SimpleX Handlers (`platforms/simplex/handlers.py`)

Since SimpleX doesn't support inline keyboards, commands use a text-based menu system
with stateful conversation flow:

1. User sends `/subscribe`
2. Bot shows numbered asset list, user replies with number
3. Bot shows receive assets, user replies with number
4. Bot asks for threshold, user enters value
5. Subscription created

State is stored in memory per-user in `_user_state` dictionary.

## Database Schema

### Multi-Platform Support Migration

The migration `c7f2a8d91e23_add_multiplatform_support.py` adds platform support
while maintaining **full backward compatibility**:

```sql
-- Added columns:
ALTER TABLE subscriptions ADD COLUMN platform TEXT NOT NULL DEFAULT 'telegram';
ALTER TABLE subscriptions ADD COLUMN platform_chat_id TEXT;
ALTER TABLE subscriptions ALTER COLUMN chat_id DROP NOT NULL;
```

**Design decisions:**

1. **Additive only**: No breaking changes to existing data
2. **Platform column**: Identifies which adapter handles this subscription
3. **Dual ID columns**:
   - `chat_id` (BigInteger): Telegram uses numeric IDs
   - `platform_chat_id` (Text): Other platforms use string IDs
4. **Existing data**: All existing rows get `platform='telegram'` automatically

### Subscription Model

```python
class Subscription(Base):
    id: int
    platform: str              # 'telegram' or 'simplex'
    chat_id: int | None        # Telegram only
    platform_chat_id: str | None  # Non-Telegram platforms
    from_asset: str
    to_asset: str
    fee_threshold: Decimal

    def get_recipient_id(self) -> str:
        """Returns appropriate ID for the platform."""
        if self.platform == 'telegram':
            return str(self.chat_id)
        return self.platform_chat_id
```

## Command Logic Architecture

### Core Business Logic (`commands/core.py`)

Platform-agnostic functions for subscription management:

- `get_available_pairs()` - Get unsubscribed pairs for a user
- `create_subscription()` - Create new subscription
- `get_user_subscriptions()` - List user's subscriptions
- `update_subscription_threshold()` - Modify threshold
- `delete_subscription()` - Remove single subscription
- `delete_all_subscriptions()` - Remove all user subscriptions

These functions handle platform-specific ID routing internally.

### Platform-Specific Handlers

- **Telegram**: Uses existing `ConversationHandler` with inline keyboards
- **SimpleX**: Text-based menus in `platforms/simplex/handlers.py`

## Configuration

Environment variables (via `settings.py`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_token  # Set to enable

# SimpleX (optional)
SIMPLEX_ENABLED=true           # Enable SimpleX adapter
SIMPLEX_ADAPTER_URL=http://simplex-adapter:3000

# Common
CHECK_INTERVAL=60              # Fee check interval (seconds)
API_URL=https://api.boltz.exchange
```

## Docker Deployment

```yaml
services:
  postgres:        # Database
  simplex-adapter: # TypeScript adapter with embedded chat core
  bot:             # Python bot (multi-platform orchestrator)
```

The `simplex-adapter` container:
1. Uses `simplex-chat@6.5.0-beta.4.4` npm package with embedded chat core
2. Creates bot profile and address on first run
3. Persists bot identity in Docker volume
4. Exposes HTTP API and WebSocket for Python bot

## Testing

### Unit Tests

- `tests/test_migration.py` - Database schema backward compatibility
- `tests/test_platforms/test_base.py` - Platform abstraction contracts
- `tests/test_platforms/test_simplex.py` - SimpleX adapter (mocked service)
- `tests/test_platforms/test_telegram.py` - Telegram adapter
- `tests/test_dispatcher.py` - Multi-platform notification dispatch

### Running Tests

```bash
# Unit tests only (no database required)
make test

# All tests (requires PostgreSQL - run `make postgres` first)
make test-all
```

## Adding New Platforms

1. Create `platforms/<platform>/adapter.py` implementing `BotPlatform`
2. Create `platforms/<platform>/handlers.py` for command handling
3. Add platform constant to `db.py` (e.g., `PLATFORM_MATRIX = "matrix"`)
4. Add initialization logic to `bot.py` in `run_multiplatform_bot()`
5. Add configuration to `settings.py`
6. Add tests in `tests/test_platforms/`
