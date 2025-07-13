"""
Author: Bunny
Bot: Universal Scrapper Bot
"""

import re
import os
import asyncio
from urllib.parse import urlparse
from aiogram import Bot, Dispatcher, types, executor
from pyrogram import Client

# === Setup ===
BOT_TOKEN = "8149868870:AAEHI6JPA6DqTUfO9WvxssvEQzbx4mXQPJg"
API_ID = "23925218"
API_HASH = "396fd3b1c29a427df8cc6fb54f3d307c"
PHONE_NUMBER = "+917011352327"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
user_client = Client("my_account", api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)

scrape_queue = asyncio.Queue()
default_limit = 100000

# === Helpers ===

def extract_channel_identifier(raw_input: str):
    raw_input = raw_input.strip()
    if raw_input.startswith("https://t.me/+"):
        return raw_input
    elif raw_input.startswith("https://t.me/"):
        return raw_input.split("/")[-1]
    elif raw_input.startswith("@"):
        return raw_input[1:]
    else:
        return raw_input

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    return unique_messages, duplicates_removed

async def scrape_messages(user_client, channel_username, limit, start_number=None):
    messages = []
    count = 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'

    async for message in user_client.search_messages(channel_username):
        if count >= limit:
            break

        text = message.text if message.text else message.caption
        if text:
            matched_messages = re.findall(pattern, text)
            for matched_message in matched_messages:
                extracted_values = re.findall(r'\d+', matched_message)
                if len(extracted_values) == 4:
                    card_number, mo, year, cvv = extracted_values
                    year = year[-2:]
                    formatted = f"{card_number}|{mo}|{year}|{cvv}"
                    messages.append(formatted)
                    count += 1

    if start_number:
        messages = [msg for msg in messages if msg.startswith(start_number)]
    return messages[:limit]

# === Scrape Processor ===

async def process_scrape_queue(user_client, bot):
    while True:
        task = await scrape_queue.get()
        message, channel_username, limit, start_number, temporary_msg, reply_id = task

        try:
            chat_info = await user_client.get_chat(channel_username)
            channel_name = chat_info.title
        except Exception:
            channel_name = str(channel_username)

        user = message.from_user
        scrapper = f"@{user.username}" if user.username else user.first_name

        scrapped_results = await scrape_messages(user_client, channel_username, limit, start_number)
        if scrapped_results:
            unique_messages, duplicates_removed = remove_duplicates(scrapped_results)

            if unique_messages:
                file_name = f"x{len(unique_messages)}_{channel_name}.txt"
                with open(file_name, 'w') as f:
                    f.write("\n".join(unique_messages))
                
                with open(file_name, 'rb') as f:
                    caption = (
                        f"<b>CC Scrapped Successful ✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Channel:</b> <code>{channel_name}</code>\n"
                        f"<b>Amount:</b> <code>{len(unique_messages)}</code>\n"
                        f"<b>Duplicates Removed:</b> <code>{duplicates_removed}</code>\n"
                        f"<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Scrapped By:</b> <code>{scrapper}</code>\n"
                    )
                    await temporary_msg.delete()
                    await bot.send_document(message.chat.id, f, caption=caption, parse_mode='html', reply_to_message_id=reply_id)
                os.remove(file_name)
            else:
                await temporary_msg.delete()
                await bot.send_message(message.chat.id, "Sorry Bro ❌ No Credit Card Found", reply_to_message_id=reply_id)
        else:
            await temporary_msg.delete()
            await bot.send_message(message.chat.id, "Sorry Bro ❌ No Credit Card Found", reply_to_message_id=reply_id)

        scrape_queue.task_done()

# === Commands ===

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await bot.send_message(message.chat.id, "<b>Welcome to CC Scrapper Bot 🧹\nUse /scr username amount</b>", parse_mode='html')

@dp.message_handler(commands=['cmds'])
async def cmds_cmd(message: types.Message):
    await bot.send_message(message.chat.id, "<b>Usage:\n/scr channel amount\n/scr channel amount bin</b>", parse_mode='html')

@dp.message_handler(commands=['scr'])
async def scr_cmd(message: types.Message):
    args = message.text.split()[1:]
    if len(args) < 2 or len(args) > 3:
        await bot.send_message(message.chat.id, "<b>⚠️ Provide channel username and amount</b>", parse_mode='html')
        return

    raw_input = args[0]
    limit = int(args[1])
    start_number = args[2] if len(args) == 3 else None

    if limit > default_limit:
        await bot.send_message(message.chat.id, f"<b>⚠️ Max limit is {default_limit}</b>", parse_mode='html')
        return

    channel_identifier = extract_channel_identifier(raw_input)

    try:
        if raw_input.startswith("https://t.me/+"):
            try:
                chat = await user_client.join_chat(channel_identifier)
                channel_username = chat.id
            except Exception as e:
                if "USER_ALREADY_PARTICIPANT" in str(e):
                    chat = await user_client.get_chat(channel_identifier)
                    channel_username = chat.id
                else:
                    await bot.send_message(message.chat.id, "<b>❌ Failed to join private channel</b>", parse_mode='html')
                    return
        else:
            await user_client.get_chat(channel_identifier)
            channel_username = channel_identifier
    except Exception:
        await bot.send_message(message.chat.id, "<b>❌ Channel not found or inaccessible</b>", parse_mode='html')
        return

    temporary_msg = await bot.send_message(message.chat.id, "<b>Scraping in progress... ⏳</b>", parse_mode='html')
    reply_id = message.reply_to_message.message_id if message.reply_to_message else None
    await scrape_queue.put((message, channel_username, limit, start_number, temporary_msg, reply_id))

# === Startup ===

async def on_startup(dp):
    await user_client.start()
    asyncio.create_task(process_scrape_queue(user_client, bot))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
