import asyncio
from typing import Optional

from telethon.tl.custom.message import Message, MessageButton


async def wait():
    await asyncio.sleep(0.75)


# Simplifies the most frequent action - look for a button
# with a given text either to check that it exists or click it.
def get_button_with_text(
    message: Message, text: str, strict: bool = False
) -> Optional[MessageButton]:
    if message.buttons is None:
        return None

    for row in message.buttons:
        for button in row:
            if strict:
                is_match = text == button.text
            else:
                is_match = text in button.text
            if is_match:
                return button

    return None
