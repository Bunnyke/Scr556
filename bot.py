import re
import os
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from pyrogram import Client

BOT_TOKEN = "8149868870:AAEHI6JPA6DqTUfO9WvxssvEQzbx4mXQPJg"
API_ID = "20711021"
API_HASH = "84459a13351f6a102e087fdfc3547e31"
PHONE_NUMBER = "+917803946534"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
user_client = Client("my_account", api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)

scrape_queue = asyncio.Queue()
default_limit = 100000

# Extract channel username or ID from any input format
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
    unique = list(set(messages))
    return unique, len(messages) - len(unique)

async def scrape_messages(user_client, channel_username, limit, start_number=None):
    messages, count = [], 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    async for message in user_client.search_messages(channel_username):
        if count >= limit:
            break
        text = message.text or message.caption
        if text:
            for match in re.findall(pattern, text):
                values = re.findall(r'\d+', match)
                if len(values) == 4:
                    cc, mo, year, cvv = values
                    year = year[-2:]
                    messages.append(f"{cc}|{mo}|{year}|{cvv}")
                    count += 1
    if start_number:
        messages = [m for m in messages if m.startswith(start_number)]
    return messages[:limit]

async def process_scrape_queue(user_client, bot):
    while True:
        task = await scrape_queue.get()
        message, channel_username, limit, start_number, temp_msg, reply_id = task

        try:
            chat_info = await user_client.get_chat(channel_username)
            channel_name = chat_info.title
        except:
            channel_name = str(channel_username)

        user = message.from_user
        scrapper = f"@{user.username}" if user.username else user.first_name

        results = await scrape_messages(user_client, channel_username, limit, start_number)
        if results:
            unique, dupes = remove_duplicates(results)
            if unique:
                fname = f"cc_{len(unique)}_{channel_name}.txt"
                with open(fname, "w") as f:
                    f.write("\n".join(unique))
                with open(fname, "rb") as f:
                    caption = (
                        f"<b>CC Scrapped Successful ✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Channel:</b> <code>{channel_name}</code>\n"
                        f"<b>Amount:</b> <code>{len(unique)}</code>\n"
                        f"<b>Duplicates Removed:</b> <code>{dupes}</code>\n"
                        f"<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Scrapped By:</b> <code>{scrapper}</code>"
                    )
                    await temp_msg.delete()
                    await bot.send_document(message.chat.id, f, caption=caption, parse_mode='html', reply_to_message_id=reply_id)
                os.remove(fname)
            else:
                await temp_msg.delete()
                await bot.send_message(message.chat.id, "❌ No valid CCs found.", reply_to_message_id=reply_id)
        else:
            await temp_msg.delete()
            await bot.send_message(message.chat.id, "❌ No CCs found in that channel.", reply_to_message_id=reply_id)

        scrape_queue.task_done()

# ========== COMMANDS ==========

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    reply_id = message.reply_to_message.message_id if message.reply_to_message else None
    msg = (
        "<b>👋 Welcome to the CC Scrapper Bot 🧹</b>\n\n"
        "📌 Usage:\n"
        "<code>/scr channel amount</code>\n"
        "<code>/scr channel amount bin</code>\n\n"
        "💬 You can also reply to someone's message with /scr!"
    )
    await bot.send_message(message.chat.id, msg, parse_mode='html', reply_to_message_id=reply_id)

@dp.message_handler(commands=['cmds'])
async def cmds_cmd(message: types.Message):
    reply_id = message.reply_to_message.message_id if message.reply_to_message else None
    msg = (
        "<b>📋 Available Commands:</b>\n"
        "<code>/scr username amount</code>\n"
        "<code>/scr username amount bin</code>\n\n"
        "⚠ Max limit: 100000"
    )
    await bot.send_message(message.chat.id, msg, parse_mode='html', reply_to_message_id=reply_id)

@dp.message_handler(commands=['scr'])
async def scr_cmd(message: types.Message):
    args = message.text.split()[1:]
    reply_id = message.reply_to_message.message_id if message.reply_to_message else None

    if len(args) < 2 or len(args) > 3:
        await bot.send_message(message.chat.id, "<b>⚠️ Use /scr channel amount [bin]</b>", parse_mode='html', reply_to_message_id=reply_id)
        return

    raw_input = args[0]
    limit = int(args[1])
    start_number = args[2] if len(args) == 3 else None

    if limit > default_limit:
        await bot.send_message(message.chat.id, f"<b>❌ Limit cannot exceed {default_limit}</b>", parse_mode='html', reply_to_message_id=reply_id)
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
                    await bot.send_message(message.chat.id, "❌ Could not join private channel", reply_to_message_id=reply_id)
                    return
        else:
            await user_client.get_chat(channel_identifier)
            channel_username = channel_identifier
    except:
        await bot.send_message(message.chat.id, "❌ Invalid channel or no access", reply_to_message_id=reply_id)
        return

    temp_msg = await bot.send_message(message.chat.id, "⏳ Scraping in progress...", parse_mode='html', reply_to_message_id=reply_id)
    await scrape_queue.put((message, channel_username, limit, start_number, temp_msg, reply_id))

# ========== STARTUP ==========

async def on_startup(dp):
    await user_client.start()
    asyncio.create_task(process_scrape_queue(user_client, bot))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
