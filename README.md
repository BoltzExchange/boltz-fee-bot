# Boltz Fee Bot

A Telegram bot that allows users to subscribe to fee changes on [Boltz Pro](https://pro.boltz.exchange)

## Setup

The bot uses [uv](https://docs.astral.sh/uv/) for dependency management.

For running the bot, you need to have a telegram bot token. You can get one by talking to [BotFather](https://core.telegram.org/bots#botfather)

A PostgreSQL database is required for storing subscribed chats. Run `make postgres` to get a local instance running.

Once setup, copy the `.env.sample` file to `.env` and fill in the values. Start the bot with `uv run bot.py` or use the `Dockerfile`.

## Telegram Bot Commands

The bot supports the following commands:

```
start - Get started with the bot
subscribe - Subscribe to boltz pro fee changes
unsubscribe - Unsubscribe from boltz pro fee changes
mysubscriptions - Show and manage existing subscriptions
```

This list can be used with BotFather by using the `/setcommands` command.

## ntfy Integration

In addition to the Telegram bot, fee alerts can be sent to [ntfy](https://ntfy.sh) topics via a REST API.

### Running the ntfy API

Start the ntfy subscription API server alongside the Telegram bot:

```bash
uv run uvicorn ntfy_api:app --host 0.0.0.0 --port 8000
```

### ntfy Configuration

Optional environment variables for ntfy:

| Variable | Description | Default |
|----------|-------------|---------|
| `NTFY_BASE_URL` | Base URL for ntfy server | `https://ntfy.sh` |
| `NTFY_AUTH_HEADER` | Authorization header (e.g., `Bearer tk_xxx`) | - |
| `NTFY_BASIC_USER` | Basic auth username | - |
| `NTFY_BASIC_PASS` | Basic auth password | - |
| `NTFY_DEFAULT_PRIORITY` | Default notification priority | - |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ntfy/subscribe` | Create a subscription |
| GET | `/ntfy/subscriptions` | List all subscriptions |
| GET | `/ntfy/subscriptions/{id}` | Get a specific subscription |
| DELETE | `/ntfy/subscriptions/{id}` | Delete a subscription |
| DELETE | `/ntfy/subscriptions/topic/{topic}` | Delete all subscriptions for a topic |

### Example: Create a Subscription

```bash
curl -X POST http://localhost:8000/ntfy/subscribe \
  -H "Content-Type: application/json" \
  -d '{
    "ntfy_topic": "my-boltz-alerts",
    "from_asset": "BTC",
    "to_asset": "LN",
    "fee_threshold": 0.1
  }'
```

Then subscribe to notifications on your device:

```bash
# Using ntfy CLI
ntfy subscribe my-boltz-alerts

# Or open in browser
open https://ntfy.sh/my-boltz-alerts
```

API documentation is available at `http://localhost:8000/docs` when running.
