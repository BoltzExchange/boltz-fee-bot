import pytest
from pydantic import ValidationError
from telethon.tl.custom import Conversation

from tests.e2e.conftest import TestSettings
from tests.helpers import get_button_with_text, wait


try:
    TestSettings()
except ValidationError as e:
    pytest.skip(reason=f"Test settings not set {e}", allow_module_level=True)


async def remove_subscriptions(conv: Conversation):
    await conv.send_message("/unsubscribe")
    await conv.get_response()


async def subscribe(
    conv: Conversation, send_asset: str, receive_asset: str, custom_threshold: bool
):
    await conv.send_message("/subscribe")
    subscribe_init = await conv.get_response()
    assert "Select" in subscribe_init.text
    btc_button = get_button_with_text(subscribe_init, send_asset, strict=True)
    assert btc_button is not None
    await btc_button.click()

    subscribe = await conv.get_edit()
    btc_button = get_button_with_text(subscribe, send_asset, strict=True)
    assert btc_button is None
    ln_button = get_button_with_text(subscribe, receive_asset)
    assert ln_button is not None
    await wait()
    await ln_button.click()

    await wait()
    subscribe = await conv.get_edit()
    if custom_threshold:
        custom_button = get_button_with_text(subscribe, "Custom")
        assert custom_button is not None
        await custom_button.click()
        await wait()
        custom_message = await conv.get_response()
        assert "Send me the fee threshold" in custom_message.text
        await conv.send_message("abc")
        await wait()
        error = await conv.get_response()
        assert "Invalid" in error.text
        await conv.send_message("0.5")
    else:
        threshold_button = subscribe.buttons[0][0]
        print(threshold_button)
        assert threshold_button is not None
        await threshold_button.click()
    await wait()
    success = await conv.get_response()
    assert "You have subscribed" in success.text


@pytest.mark.parametrize(
    "send_asset, receive_asset, custom_threshold",
    [
        ("BTC", "LN", False),
        ("BTC", "LN", True),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe(
    conv: Conversation, send_asset: str, receive_asset: str, custom_threshold: bool
):
    await remove_subscriptions(conv)

    await subscribe(conv, send_asset, receive_asset, custom_threshold)


async def select_subscription(
    conv: Conversation, send_asset: str, receive_asset: str, threshold: str = None
):
    await conv.send_message("/mysubscriptions")
    my_subscriptions = await conv.get_response()
    assert "You are subscribed" in my_subscriptions.text
    button = get_button_with_text(my_subscriptions, f"{send_asset} -> {receive_asset}")
    if threshold:
        assert threshold in button.text

    await button.click()
    await wait()
    selected = await conv.get_edit()
    return selected


@pytest.mark.asyncio(loop_scope="session")
async def test_mysubscriptions(conv: Conversation):
    await remove_subscriptions(conv)

    await conv.send_message("/mysubscriptions")
    my_subscriptions = await conv.get_response()
    assert "You are not subscribed" in my_subscriptions.text
    send_asset = "BTC"
    receive_asset = "LN"

    await subscribe(conv, send_asset, receive_asset, False)

    selected = await select_subscription(conv, send_asset, receive_asset)

    edit_button = get_button_with_text(selected, "Edit threshold")
    assert edit_button is not None
    await edit_button.click()
    await wait()
    edit_message = await conv.get_response()
    assert "Send me the new fee threshold" in edit_message.text

    wrong_threshold = "invalid"
    await conv.send_message(wrong_threshold)
    await wait()
    error = await conv.get_response()
    assert "Invalid" in error.text

    new_threshold = "0.6"
    await conv.send_message(new_threshold)
    await wait()
    success = await conv.get_response()
    assert "updated" in success.text

    selected = await select_subscription(conv, send_asset, receive_asset, new_threshold)
    remove_button = get_button_with_text(selected, "Remove subscription")
    assert remove_button is not None
    await remove_button.click()
    await wait()
    success = await conv.get_response()
    assert "removed" in success.text

    await conv.send_message("/mysubscriptions")
    my_subscriptions = await conv.get_response()
    assert "You are not subscribed" in my_subscriptions.text
