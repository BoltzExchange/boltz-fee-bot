# Boltz Fee Bot

A Telegram bot that allows users to subscribe to fee changes on [Boltz Pro](https://pro.boltz.exchange)

## Setup

The bot uses [uv](https://docs.astral.sh/uv/) for dependency management.

For running the bot, you need to have a telegram bot token. You can get one by talking to [BotFather](https://core.telegram.org/bots#botfather)

A PostgreSQL database is required for storing subscribed chats. Run `make postgres` to get a local instance running.

Once setup, copy the `.env.sample` file to `.env` and fill in the values. Start the bot with `uv run bot.py` or use the `Dockerfile`.

## Commands

The bot supports the following commands:

```
start - Get started with the bot
subscribe - Subscribe to boltz pro fee changes
unsubscribe - Unsubscribe from boltz pro fee changes
mysubscriptions - Show and manage existing subscriptions
```

This list can be used with BotFather by using the `/setcommands` command.
