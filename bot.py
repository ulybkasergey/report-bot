import asyncio
import os
from datetime import datetime
from typing import Set, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ====== ЧИТАЕМ НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ======

API_TOKEN = os.getenv("API_TOKEN")
MANAGER_ID = int(os.getenv("MANAGER_ID", "0"))
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Stockholm")  # можно не трогать

if not API_TOKEN or MANAGER_ID == 0 or GROUP_ID == 0:
    raise RuntimeError("Не заданы API_TOKEN / MANAGER_ID / GROUP_ID в переменных окружения")

# Список людей, от которых ждём отчёты: Telegram ID -> имя
# 👉 сюда потом подставишь реальные ID и имена
EXPECTED_USERS = {
    111111111: "Иван",
    222222222: "Петя",
    333333333: "Маша",
}

# ====== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ СОСТОЯНИЯ ======

bot = Bot(API_TOKEN)
dp = Dispatcher()

# Кто уже отчитался сегодня (по user_id)
reported_today: Set[int] = set()

# Кого не хватало по итогам дня (для утреннего отчёта)
missed_yesterday: List[int] = []


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


async def reset_reports():
    """Сбросить список тех, кто отчитался — каждый день в 20:00."""
    global reported_today
    reported_today = set()
    print("Reports reset for", today_key())


async def evening_reminder():
    """Напоминание в чат в 20:00."""
    await reset_reports()
    text = (
        "Напоминание 🌙\n\n"
        "До 23:00 нужно выложить ежедневный #отчет.\n"
        "Просто напишите сообщение с хэштегом #отчет в этом чате."
    )
    await bot.send_message(chat_id=GROUP_ID, text=text)


async def check_missed():
    """В 23:00 фиксируем, кто не отчитался."""
    global missed_yesterday
    missed = [uid for uid in EXPECTED_USERS.keys() if uid not in reported_today]
    missed_yesterday = missed
    print("Missed users:", missed_yesterday)


async def morning_report_to_manager():
    """В 05:00 отправляем тебе список тех, кто вчера не отчитался."""
    if not missed_yesterday:
        text = "Доброе утро! Все вчера выложили #отчет ✅"
    else:
        names = ", ".join(EXPECTED_USERS[uid] for uid in missed_yesterday)
        text = (
            "Доброе утро! Вот кто вчера не выложил #отчет до 23:00:\n"
            f"{names}"
        )

    await bot.send_message(chat_id=MANAGER_ID, text=text)


# ====== ХЕНДЛЕРЫ СООБЩЕНИЙ ======

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для контроля #отчетов.\n"
        "Я буду напоминать в 20:00 и в 05:00 присылать список тех, кто не отчитался."
    )


@dp.message(Command("who"))
async def cmd_who(message: Message):
    """Команда /who — кто сегодня ещё не отчитался."""
    missed_now = [uid for uid in EXPECTED_USERS.keys() if uid not in reported_today]
    if not missed_now:
        await message.answer("На данный момент все из списка выложили #отчет ✅")
    else:
        names = ", ".join(EXPECTED_USERS[uid] for uid in missed_now)
        await message.answer("Пока не отчитались:\n" + names)


@dp.message(F.chat.id == GROUP_ID, F.text.contains("#отчет"))
async def handle_report(message: Message):
    """Любое сообщение с #отчет в нужном чате — считаем отчётом."""
    user_id = message.from_user.id
    reported_today.add(user_id)
    await message.reply("Отчет принят ✅")


# ====== ЗАПУСК БОТА И ПЛАНИРОВЩИКА ======

async def main():
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # В 20:00 — напоминание и сброс списка
    scheduler.add_job(evening_reminder, CronTrigger(hour=20, minute=0))

    # В 23:00 — фиксируем, кто не отчитался
    scheduler.add_job(check_missed, CronTrigger(hour=23, minute=0))

    # В 05:00 — шлём тебе список прогульщиков
    scheduler.add_job(morning_report_to_manager, CronTrigger(hour=5, minute=0))

    scheduler.start()

    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
