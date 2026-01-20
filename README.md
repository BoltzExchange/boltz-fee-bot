# Boltz Pro Fee Bot

A multi-platform bot that allows users to subscribe to fee changes on [Boltz Pro](https://pro.boltz.exchange).

Currently supported platforms:
- **[Telegram](https://telegram.org/)** - Popular cloud-based messaging app
- **[SimpleX](https://simplex.chat/)** - Privacy-focused decentralized messenger

## Architecture

The bot uses a modular platform abstraction that allows adding new messaging platforms easily. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation.

```
┌─────────────────┐     ┌─────────────────┐
│ Telegram Adapter│     │ SimpleX Adapter │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Python Bot (Core Logic)       │
│  - Fee monitoring from Boltz Pro API    │
│  - Subscription management              │
│  - Platform-agnostic notifications      │
└─────────────────────────────────────────┘
                    │
                    ▼
         ┌─────────────────┐
         │   PostgreSQL    │
         └─────────────────┘
```

## Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/BoltzExchange/boltz-fee-bot.git
cd boltz-fee-bot

# Copy and configure environment
cp .env.sample .env
# Edit .env with your settings

# Start all services
docker compose up -d
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) | - |
| `SIMPLEX_ENABLED` | Enable SimpleX platform | `false` |
| `SIMPLEX_ADAPTER_URL` | SimpleX adapter service URL | `http://simplex-adapter:3000` |
| `SIMPLEX_BOT_NAME` | Display name for SimpleX bot | `Boltz Pro Fee Bot` |
| `CHECK_INTERVAL` | Fee check interval in seconds | `60` |
| `API_URL` | Boltz Pro API URL | `https://api.boltz.exchange` |

### Telegram Setup

1. Create a bot via [BotFather](https://core.telegram.org/bots#botfather)
2. Set `TELEGRAM_BOT_TOKEN` in `.env`
3. Use `/setcommands` with BotFather to register commands:
   ```
   start - Get started with the bot
   subscribe - Subscribe to Boltz Pro fee changes
   unsubscribe - Unsubscribe from fee alerts
   mysubscriptions - Show and manage existing subscriptions
   ```

### SimpleX Setup

SimpleX is enabled by default in Docker. The bot will:
1. Create a profile automatically
2. Generate a connection address (check logs)
3. Accept incoming connections automatically

To get the SimpleX connection link:
```bash
docker compose logs simplex-adapter | grep "Bot address:"
```

## Development

### Prerequisites

- Python 3.13+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+ (for SimpleX adapter)
- PostgreSQL 17+
- Docker (optional, for containerized setup)

### Local Setup

```bash
# Install Python dependencies
uv sync

# Start PostgreSQL
make postgres

# Run database migrations
uv run alembic upgrade head

# Start the bot
uv run bot.py
```

### Running Tests

```bash
# Unit tests only (no database required)
make test

# Full test suite including integration and e2e tests
# (automatically starts test database)
make test-all
```

### Code Quality

```bash
make format  # Format code with ruff
make check   # Run linter
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Get started and see help |
| `/subscribe` | Subscribe to fee alerts for a trading pair |
| `/unsubscribe` | Remove a subscription |
| `/mysubscriptions` | View and manage your subscriptions |
| `/help` | Show available commands |

## License

[MIT](LICENSE)
