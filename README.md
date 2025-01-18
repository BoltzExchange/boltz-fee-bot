# Boltz Fee Bot

A telegram bot that allows users to subscribe to fee changes on [boltz pro](https://pro.boltz.exchange)

## Setup

The bot uses [uv](https://docs.astral.sh/uv/) for dependency management.

For running the bot, you need to have a telegram bot token. You can get one by talking to [BotFather](https://core.telegram.org/bots#botfather)

A postgres database is required for storing subscribed chats. Run `make postgres` to get a local instance running.

Once setup, copy the `.env.sample` file to `.env` and fill in the values. Start the bot with `uv run bot.py` or use the `Dockerfile`.
