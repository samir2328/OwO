import json
import os
import random
from datetime import datetime, timedelta, UTC
import telebot
from telebot.types import InputMediaPhoto
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from PIL import Image, ImageDraw, ImageFont
from limit_utils import is_in_limit_cooldown, check_and_update_send_limit, reset_send_window, check_and_update_receive_cooldown
import threading
import time
import bank
import oddandout
import dice
import admin_panel
from cooldown import CF_COOLDOWN, OS_COOLDOWN
import obj
import cf  # <-- Add this line
import portalocker  # <-- Add this line
import mines  # <-- Add this line
import cfmultiplayer  # Add this with your other imports
active_dice_games = {}

API_TOKEN = '7026873857:AAEZs64VIwmozKGIGeczH4BkfYDoM0oNGyo'
DB_PATH = os.path.join(os.path.dirname(__file__), 'playerdb.json')
DAILY_COOLDOWN = timedelta(hours=24)
DAILY_STREAK_WINDOW = timedelta(hours=48)

LEVELS = [
    {"lvl": 1, "xp": 0, "limit": 60000},
    {"lvl": 2, "xp": 1000, "limit": 100000},
    {"lvl": 3, "xp": 3000, "limit": 150000},
    {"lvl": 4, "xp": 5000, "limit": 250000},
    {"lvl": 5, "xp": 8000, "limit": 500000},
    {"lvl": 6, "xp": 10000, "limit": 550000},
    {"lvl": 7, "xp": 15000, "limit": 700000},
    {"lvl": 8, "xp": 20000, "limit": 900000},
    {"lvl": 9, "xp": 50000, "limit": 900000},
    {"lvl": 10, "xp": 100000, "limit": float('inf')}
]

bot = telebot.TeleBot(API_TOKEN)

# Global database variable
global_db = None

def load_db():
    global global_db
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, 'w') as f:
            json.dump({}, f)
    with open(DB_PATH, 'r') as f:
        content = f.read().strip()
        if not content:
            # If file is empty, initialize with {}
            global_db = {}
            save_db(global_db)
            return global_db
        try:
            global_db = json.loads(content)
            return global_db
        except json.JSONDecodeError:
            print("ERROR: playerdb.json is corrupted! Please fix it manually.")
            raise

def save_db(db):
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, 'w') as f:
        json.dump(db, f, indent=2)
    os.replace(tmp_path, DB_PATH)
    global global_db
    global_db = db
    # Remove this block to avoid file lock issues
    # with open(DB_PATH, 'w') as f:
    #     portalocker.lock(f, portalocker.LOCK_EX)
    #     json.dump(db, f, indent=2)
    #     portalocker.unlock(f)

def get_user(db, user):
    uid = str(user.id)
    is_new = False
    if uid not in db:
        db[uid] = {
            "id": user.id,
            "username": user.username or user.first_name,
            "coins": 0,
            "xp": 0,
            "lvl": 1,
            "streak": 0,
            "lastDaily": 0,
            "last_cf": 0,
            "last_os": 0,
            "limit_cooldown": 0,
            "sent_in_window": 0,
            "sent_window_start": 0,
            "token": str(random.randint(10**9, 10**10-1))
        }
        is_new = True
    if 'last_cf' not in db[uid]:
        db[uid]['last_cf'] = 0
    if 'last_os' not in db[uid]:
        db[uid]['last_os'] = 0
    if 'limit_cooldown' not in db[uid]:
        db[uid]['limit_cooldown'] = 0
    if 'sent_in_window' not in db[uid]:
        db[uid]['sent_in_window'] = 0
    if 'sent_window_start' not in db[uid]:
        db[uid]['sent_window_start'] = 0
    if 'token' not in db[uid]:
        db[uid]['token'] = str(random.randint(10**9, 10**10-1))
    if is_new:
        save_db(db)
    return db[uid]

@bot.message_handler(commands=['start'])
def start_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    save_db(db)
    bot.reply_to(message, f"Welcome, {user['username']}! Use /help to see commands.")

@bot.message_handler(commands=['bal', 'balance', 'wallet'])
def balance_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    save_db(db)
    bot.reply_to(message, f"💰 Balance for {user['username']}: {user['coins']} coins")

@bot.message_handler(commands=['pay'])
def pay_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    now = int(time.time())
    in_cooldown, wait_hours, wait_minutes = is_in_limit_cooldown(user, now)
    if in_cooldown:
        bot.reply_to(message, f"⏳ You have reached your transaction limit. Please wait {wait_hours} hour(s) and {wait_minutes} minute(s) before sending or receiving coins again.")
        return
    args = message.text.split()[1:]
    if len(args) != 2:
        bot.reply_to(message, "Usage: /pay <username> <amount>")
        return
    username = args[0].lstrip('@')
    amount_arg = args[1]
    if amount_arg.lower() == "all":
        amount = user['coins']
    else:
        try:
            amount = int(amount_arg)
        except ValueError:
            bot.reply_to(message, "Amount must be a number or 'all'.")
            return
    receiver = next((u for u in db.values() if isinstance(u, dict) and u.get('username') == username), None)
    if not receiver:
        bot.reply_to(message, f"User @{username} not found.")
        return
    if amount <= 0:
        bot.reply_to(message, "Amount must be positive.")
        return
    sender_level = get_level(user['xp'])
    if not check_and_update_send_limit(user, amount, sender_level['limit'], now):
        save_db(db)
        bot.reply_to(message, f"You have reached your transaction limit of {sender_level['limit']} coins in 10 hours. Please wait 10 hours before sending more coins.")
        return
    if user['coins'] < amount:
        bot.reply_to(message, "Insufficient coins.")
        return
    if not check_and_update_receive_cooldown(receiver, now):
        bot.reply_to(message, f"User @{username} is in cooldown and cannot receive coins right now.")
        return

    user['coins'] -= amount
    receiver['coins'] += amount
    save_db(db)
    bot.reply_to(message, f"✅ Sent {amount} coins to @{username}.")
    try:
        bot.send_message(receiver['id'], f"{user['username']} pay you {amount}")
    except Exception:
        pass

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    now = datetime.utcnow()
    last_daily = datetime.utcfromtimestamp(user['lastDaily']) if user['lastDaily'] else None
    if last_daily and now - last_daily < DAILY_COOLDOWN:
        wait = (DAILY_COOLDOWN - (now - last_daily)).seconds // 3600
        bot.reply_to(message, f"You already claimed daily! Wait {wait} more hour(s).")
        return
    if last_daily and now - last_daily < DAILY_STREAK_WINDOW:
        user['streak'] += 1
    else:
        user['streak'] = 1
    reward = 5000 + (user['streak'] - 1) * 50
    user['coins'] += reward
    user['lastDaily'] = int(now.timestamp())
    save_db(db)
    bot.reply_to(message, f"🎁 Daily claimed! Streak: {user['streak']} days. You received {reward} coins.")

user_cooldowns = {}

def command_cooldown(seconds, exclude_admin=False):
    def decorator(func):
        def wrapper(message, *args, **kwargs):
            user_id = str(message.from_user.id)
            now = time.time()
            if exclude_admin and is_admin(message.from_user.id):
                return func(message, *args, **kwargs)
            last_used = user_cooldowns.get((user_id, func.__name__), 0)
            if now - last_used < seconds:
                wait = int(seconds - (now - last_used))
                bot.reply_to(message, f"⏳ Please wait {wait} seconds before using this command again.")
                return
            user_cooldowns[(user_id, func.__name__)] = now
            return func(message, *args, **kwargs)
        return wrapper
    return decorator

@bot.message_handler(commands=['os'])
@command_cooldown(10)
def os_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    now = int(time.time())
    if now - user.get('last_os', 0) < OS_COOLDOWN:
        wait = OS_COOLDOWN - (now - user.get('last_os', 0))
        bot.reply_to(message, f"⏳ Please wait {wait} seconds before using /os again.")
        return
    user['last_os'] = now
    args = message.text.split()[1:]
    if len(args) != 1 or not args[0].isdigit():
        bot.reply_to(message, "Usage: /os <amount>")
        save_db(db)
        return
    amount = int(args[0])
    user_level = get_level(user['xp'])
    if amount > user_level['limit']:
        bot.reply_to(message, f"Your level limit is {user_level['limit']} coins.")
        save_db(db)
        return
    if user['coins'] < amount:
        bot.reply_to(message, "Insufficient coins.")
        save_db(db)
        return
    symbols = ['🍒', '🍋', '🍉', '⭐', '7️⃣']
    slot = [random.choice(symbols) for _ in range(3)]
    result_msg = f"🎰 [{' | '.join(slot)}]\n"
    if slot[0] == slot[1] == slot[2]:
        win_amount = amount * 5
        user['coins'] += win_amount
        result_msg += f"Jackpot! You win {win_amount} coins!"
    elif slot[0] == slot[1] or slot[1] == slot[2] or slot[0] == slot[2]:
        win_amount = amount * 2
        user['coins'] += win_amount
        result_msg += f"Nice! You win {win_amount} coins!"
    else:
        user['coins'] -= amount
        result_msg += f"No match. You lose {amount} coins."
    save_db(db)
    bot.reply_to(message, result_msg)

@bot.message_handler(commands=['xp', 'lvl', 'levels', 'points'])
@command_cooldown(5)
def xp_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    level = get_level(user['xp'])
    img = Image.new('RGB', (400, 120), color='#222222')
    draw = ImageDraw.Draw(img)
    font_bold = ImageFont.truetype("arial.ttf", 22)
    font = ImageFont.truetype("arial.ttf", 16)
    draw.text((120, 40), user['username'], fill="#fff", font=font_bold)
    draw.text((120, 70), f"Level: {level['lvl']}", fill="#fff", font=font)
    draw.text((120, 95), f"XP: {user['xp']}", fill="#fff", font=font)
    img_path = os.path.join(os.path.dirname(__file__), f"profile_{user['id']}.png")
    img.save(img_path)
    with open(img_path, 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption=f"{user['username']} | Level {level['lvl']} | XP {user['xp']}")
    os.remove(img_path)

def is_banned(user):
    return user.get('banned', False)

def ban_message(user):
    return f"{user.get('ban_reason','')}\n{user.get('token','')} {user['username']} you are baned from this game\nis you want any help then msg hum @samir2329"

@bot.message_handler(commands=['start', 'bal', 'balance', 'wallet', 'pay', 'daily', 'obj', 'os', 'xp', 'lvl', 'levels', 'points'])
def all_cmds(message):
    db = load_db()
    user = get_user(db, message.from_user)
    if is_banned(user):
        bot.reply_to(message, ban_message(user))
        return
    xp_gain = random.randint(5, 14)
    user['xp'] += xp_gain
    new_level = get_level(user['xp'])
    if new_level['lvl'] > user['lvl']:
        user['lvl'] = new_level['lvl']
        bot.reply_to(message, f"🎉 {user['username']} leveled up to {user['lvl']}!")
    save_db(db)

def get_level(xp):
    for lvl in reversed(LEVELS):
        if xp >= lvl["xp"]:
            return lvl
    return LEVELS[0]

@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def random_xp(message):
    db = load_db()
    user = get_user(db, message.from_user)
    if is_banned(user):
        bot.reply_to(message, ban_message(user))
        return
    xp_gain = random.randint(5, 14)
    user['xp'] += xp_gain
    new_level = get_level(user['xp'])
    if new_level['lvl'] > user['lvl']:
        user['lvl'] = new_level['lvl']
        bot.reply_to(message, f"🎉 {user['username']} leveled up to {user['lvl']}!")
    save_db(db)

@bot.message_handler(commands=['top'])
def top_cmd(message):
    db = load_db()
    users = [u for u in db.values() if isinstance(u, dict) and u.get('coins', 0) > 0]
    users = sorted(users, key=lambda u: u.get('coins', 0), reverse=True)
    top_users = users[:25]
    msg_lines = ["🏆 Top 25 Richest Players:"]
    for idx, user in enumerate(top_users, 1):
        msg_lines.append(f"{idx}. {user.get('username', 'Unknown')} - {user.get('coins', 0)} coins")
    bot.reply_to(message, "\n".join(msg_lines))

@bot.message_handler(commands=['rank'])
def rank_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    users = [u for u in db.values() if isinstance(u, dict) and u.get('coins', 0) > 0]
    users = sorted(users, key=lambda u: u.get('coins', 0), reverse=True)
    user_rank = None
    for idx, u in enumerate(users, 1):
        if u['id'] == user['id']:
            user_rank = idx
            break
    if user_rank:
        bot.reply_to(message, f"🏅 Your rank: {user_rank} out of {len(users)}\n💰 Coins: {user.get('coins', 0)}")
    else:
        bot.reply_to(message, "You are not ranked yet (you have 0 coins).")

@bot.message_handler(commands=['limit', 'l'])
def limit_cmd(message):
    args = message.text.split()[1:]
    if not args:
        db = load_db()
        user = get_user(db, message.from_user)
        level = get_level(user['xp'])
        limit = level['limit']
        bot.reply_to(
            message,
            f"🔒 Your current level: {level['lvl']}\n"
            f"Your send/receive limit: {limit if limit != float('inf') else 'Unlimited'} coins per transaction."
        )
    else:
        try:
            lvl_num = int(args[0])
            level_info = next((lvl for lvl in LEVELS if lvl['lvl'] == lvl_num), None)
            if not level_info:
                raise ValueError
            limit = level_info['limit']
            bot.reply_to(
                message,
                f"Level {lvl_num} limit: {limit if limit != float('inf') else 'Unlimited'} coins per transaction."
            )
        except ValueError:
            bot.reply_to(message, "Please provide a valid level number (1-10). Example: /limit 5")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = (
        "🤖 *OWO Bot Help*\n\n"
        "Here are the available commands:\n"
        "/start - Start the bot and register yourself\n"
        "/help - Show this help message\n"
        "/bal, /balance, /wallet - Show your coin balance\n"
        "/pay <username> <amount> - Pay coins to another user\n"
        "/daily - Claim your daily reward and increase your streak\n"
        "/cf <amount> - Coin flip game (win or lose coins)\n"
        "/obj <amount> - Card game (draw a card vs bot)\n"
        "/os <amount> - Slot machine game\n"
        "/xp, /lvl, /levels, /points - Show your XP and level\n"
        "/top - Show the top 25 richest players\n"
        "/limit, /l - Show your current level and limit\n"
        "/limit <level> - Show the limit for a specific level\n"
        "/dice - Play a dice game\n"
        "/dice <amount> - Play a dice game with a specific amount\n"
        "/odd <amount> - Play a dice game with a specific amount If You Won Then Your Amount has 100x\n"
        "\n"
        "*Features & Benefits:*\n"
        "- Earn coins and XP by playing games and being active\n"
        "- Level up to increase your transaction limits\n"
        "- Daily rewards with streak bonuses\n"
        "- Compete for the top spot on the leaderboard\n"
        "- Secure: Each user has a unique 10-digit token\n"
        "- Admins can ban/unban users for fair play\n"
        "\n"
        "If you are banned and need help, contact @samir2329\n"
        "Join This Group For Updates \n"
        "https://t.me/OwOBotSupport\n"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(content_types=['new_chat_members'])
def on_new_group(message):
    db = load_db()
    chat_id = message.chat.id
    if 'groups' not in db:
        db['groups'] = []
    if chat_id not in db['groups']:
        db['groups'].append(chat_id)
        save_db(db)

def is_admin(user_id):
    db = load_db()
    admins = db.get("admins", [])
    return int(user_id) in admins

@bot.message_handler(commands=['adminhelp', 'ahelp'])
def admin_help_cmd(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ You are not an admin.")
        return
    bot.reply_to(message,
        "/bal {username} - Check any user's balance\n"
        "/xp {username} - Check any user's XP/level\n"
        "/update - Show who used which command (DM only)\n"
        "/addadmin {username} - Add admin\n"
        "/demoteadmin {username} - Remove admin"
    )

@bot.message_handler(commands=['bal'])
def admin_bal_cmd(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args:
        return
    username = args[0].lstrip('@')
    db = load_db()
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username') == username), None)
    if user:
        bot.reply_to(message, f"💰 {username}'s balance: {user['coins']} coins")
    else:
        bot.reply_to(message, f"User @{username} not found.")

@bot.message_handler(commands=['xp'])
def admin_xp_cmd(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args:
        return
    username = args[0].lstrip('@')
    db = load_db()
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username') == username), None)
    if user:
        bot.reply_to(message, f"⭐ {username}'s XP: {user['xp']} | Level: {user['lvl']}")
    else:
        bot.reply_to(message, f"User @{username} not found.")

@bot.message_handler(commands=['addadmin'])
def add_admin_cmd(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(message, "Usage: /addadmin {username}")
        return
    username = args[0].lstrip('@')
    db = load_db()
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username') == username), None)
    if user:
        admins = db.get("admins", [])
        if user['id'] not in admins:
            admins.append(user['id'])
            db["admins"] = admins
            save_db(db)
            bot.reply_to(message, f"✅ @{username} is now an admin.")
        else:
            bot.reply_to(message, f"@{username} is already an admin.")
    else:
        bot.reply_to(message, f"User @{username} not found.")

@bot.message_handler(commands=['demoteadmin'])
def demote_admin_cmd(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(message, "Usage: /demoteadmin {username}")
        return
    username = args[0].lstrip('@')
    db = load_db()
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username') == username), None)
    if user:
        admins = db.get("admins", [])
        if user['id'] in admins:
            admins.remove(user['id'])
            db["admins"] = admins
            save_db(db)
            bot.reply_to(message, f"✅ @{username} is no longer an admin.")
        else:
            bot.reply_to(message, f"@{username} is not an admin.")
    else:
        bot.reply_to(message, f"User @{username} not found.")

# Command usage logging for /update
command_usage_log = []

# Register bank handlers after bot and utility functions
bank.register_bank_handlers(bot, load_db, save_db, get_user)

# Register odd and out handler
oddandout.register_oddandout_handler(bot, load_db, save_db, get_user, get_level)

# Register dice handler
dice.register_dice_handler(bot, load_db, save_db, get_user, get_level)

# Register cf handler
# ... existing code ...
cfmultiplayer.register_cf_multiplayer_handlers(bot, load_db, save_db, get_user)
cf.register_cf_handler(bot, load_db, save_db, get_user, get_level)
# ... existing code ...

# Register obj handler
obj.register_obj_handler(bot, load_db, save_db, get_user, get_level)

# Register mines handler
mines.register_mines_handlers(bot, load_db, save_db, get_user)

# If you want to reload the free money handlers after adding/removing a command from the admin panel, you can call `register_all_free_money_handlers()` after such changes (for example, by calling it from your admin panel code).

# Example of the required code block
from admin_panel import register_free_money_handler

def register_all_free_money_handlers():
    register_free_money_handler(bot, load_db, save_db, get_user)

register_all_free_money_handlers()

# Start polling (this keeps the bot running)
if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Bot crashed with error: {e}")
            time.sleep(5)  # Wait 5 seconds before restarting