import aiohttp
import logging
from aiogram import types, Bot

import datetime as dt
from utils import messages
from utils.api import db, awg
from keyboards.inline import gen_inline


async def buy_info(
    payload: types.CallbackQuery
):
    await payload.answer()
    await payload.message.answer(
        text=messages.PAYMENT_INFO,
        reply_markup=gen_inline()
    )


async def cmd_buy(
    message: types.Message,
    expires_at: str | None = None,
):
    # Проверяем, есть ли у пользователя уже активная подписка
    is_subscribed = expires_at is not None
    if is_subscribed:
        await message.reply(
            text=messages.PAYMENT_UNAVAILABLE_ALREADY_SUBSCRIBED,
            reply_markup=gen_inline()
        )
        return

    # Задаем количество дней для бесплатной подписки.
    # Ты можешь изменить это значение на любое другое.
    free_days = 30

    # Создаем фиктивный объект `SuccessfulPayment`, чтобы имитировать успешную оплату.
    # Это позволяет нам использовать твою функцию `successful_payment` без изменений.
    mock_successful_payment = types.SuccessfulPayment(
        currency="XTR",
        total_amount=free_days,
        invoice_payload="free_subscription",  # Можно использовать любое значение
        telegram_payment_charge_id="mock_charge_id",
        provider_payment_charge_id="mock_provider_charge_id"
    )

    # Создаем фиктивное сообщение, которое будет содержать наш фейковый платеж.
    mock_message = types.Message(
        message_id=message.message_id,
        chat=message.chat,
        from_user=message.from_user,
        date=message.date,
        text=message.text,
        successful_payment=mock_successful_payment
    )

    # Напрямую вызываем функцию `successful_payment`, которая активирует подписку.
    await successful_payment(message=mock_message, bot=message.bot)

    # Сообщаем пользователю, что подписка активирована бесплатно.
    await message.answer(
        text=f"Поздравляем! Ваша подписка на {free_days} дней активирована бесплатно.",
        reply_markup=gen_inline()
    )


async def pre_checkout_query(
    query: types.PreCheckoutQuery,
    bot: Bot
):
    # Эта функция больше не будет вызываться, так как мы пропускаем этап оплаты,
    # но оставляем ее на случай, если ты захочешь вернуть платежи.
    await bot.answer_pre_checkout_query(query.id, ok=True)


async def successful_payment(
    message: types.Message,
    bot: Bot
):
    is_test = message.successful_payment.invoice_payload.startswith("test_")

    async with aiohttp.ClientSession() as session:
        awg_id = await awg.create_client(
            name=str(message.chat.id),
            session=session
        )

        success = await db.update_user(
            id=message.chat.id,
            username=message.chat.username,
            awg_id=awg_id,
            expires_at=dt.datetime.strftime(dt.datetime.now() + dt.timedelta(
                days=message.successful_payment.total_amount + 1), "%Y-%m-%dT%H:%M:%S.000Z"),
            session=session
        )

    await message.answer(
        text=messages.PAYMENT_PROCESSED_SUCCESS if success else messages.PAYMENT_PROCESSED_FAIL,
        reply_markup=gen_inline()
    )

    if is_test:
        refund = await bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id
        )

        if refund is True:
            logging.info(
                f"Возврат произведен успешно: {message.successful_payment.telegram_payment_charge_id}")
        else:
            logging.error(
                f"Возврат не удался: {message.successful_payment.telegram_payment_charge_id}")
