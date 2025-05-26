import random
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

# --- Bank Levels ---
BANK_LEVELS = [
    {"lvl": 1, "deposit": 10000, "upgrade": 0},
    {"lvl": 2, "deposit": 100000, "upgrade": 100000},
    {"lvl": 3, "deposit": 1500000, "upgrade": 1000000},
    {"lvl": 4, "deposit": 2000000, "upgrade": 10000000},
    {"lvl": 5, "deposit": 5000000, "upgrade": 99999999},
    {"lvl": 6, "deposit": 10000000, "upgrade": 100000000},
    {"lvl": 7, "deposit": 100000000, "upgrade": 2000000000},
    {"lvl": 8, "deposit": 1500000000, "upgrade": 2000000000},
    {"lvl": 9, "deposit": 2000000000, "upgrade": 2100000000},
    {"lvl": 10, "deposit": 200000000000000, "upgrade": 100000000000000}
]

def get_bank_level(total_deposit):
    for lvl in reversed(BANK_LEVELS):
        if total_deposit >= lvl["deposit"]:
            return lvl
    return BANK_LEVELS[0]

def ensure_bank(user):
    if 'bank' not in user:
        user['bank'] = {
            "balance": 0,
            "pin": None,
            "level": 1,
            "total_deposit": 0,
            "deposit_history": [],
            "withdraw_history": []
        }

def register_bank_handlers(bot, load_db, save_db, get_user):
    @bot.message_handler(commands=['bank', 'b'])
    def bank_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        ensure_bank(user)
        args = message.text.split()[1:]
        if args:
            if args[0].lower() == "help":
                help_text = (
                    "🏦 *Bank Help*\n\n"
                    "/bank - Show your bank account info or create a new account\n"
                    "/bank upgrade - Upgrade your bank level (costs coins)\n"
                    "/bank lvl - Show your current bank level\n"
                    "/deposit <amount> - Deposit coins into your bank\n"
                    "/withdraw <amount> - Withdraw coins from your bank\n"
                    "Bank level increases your deposit limit. Upgrade to store more coins!\n"
                    "You can view your deposit/withdraw history from the bank menu."
                )
                bot.reply_to(message, help_text, parse_mode="Markdown")
                return
            if args[0].lower() == "upgrade":
                curr_lvl = user['bank']['level']
                if curr_lvl >= 10:
                    bot.reply_to(message, "Your bank is already at max level.")
                    return
                next_lvl_info = BANK_LEVELS[curr_lvl]
                cost = next_lvl_info['upgrade']
                if user['coins'] < cost:
                    bot.reply_to(message, f"Not enough coins to upgrade. You need {cost} coins for level {curr_lvl+1}.")
                    return
                user['coins'] -= cost
                user['bank']['level'] += 1
                save_db(db)
                bot.reply_to(message, f"Bank upgraded to level {curr_lvl+1}!")
                return
            elif args[0].lower() == "lvl":
                # --- New logic: send profile photo, username, user lvl, bank lvl ---
                photos = bot.get_user_profile_photos(message.from_user.id, limit=1)
                username = user.get('username', 'Unknown')
                user_lvl = user.get('lvl', 1)
                bank_level = user.get('bank', {}).get('level', 1)
                caption = (
                    f"👤 Username: {username}\n"
                    f"🏅 User Level: {user_lvl}\n"
                    f"🏦 Bank Level: {bank_level}"
                )
                if photos.total_count > 0:
                    file_id = photos.photos[0][0].file_id
                    bot.send_photo(message.chat.id, file_id, caption=caption)
                else:
                    bot.send_message(message.chat.id, caption)
                return
        # Default: show bank info or create account
        if user['bank']['pin'] is None:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("Create Account", callback_data="bank_create"))
            bot.send_message(message.chat.id, "You don't have a bank account yet. Click below to create one.", reply_markup=markup)
        else:
            bank = user['bank']
            text = (
                f"🏦 <b>Your Bank Account</b>\n"
                f"Bank Balance: <b>{bank['balance']}</b>\n"
                f"User Coins: <b>{user['coins']}</b>\n"
                f"Bank Level: <b>{bank['level']}</b>"
            )
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("Withdraw History", callback_data="bank_withdraw_history"),
                InlineKeyboardButton("Deposit History", callback_data="bank_deposit_history")
            )
            bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)
        save_db(db)

    @bot.callback_query_handler(func=lambda call: call.data == "bank_create")
    def bank_create_callback(call):
        db = load_db()
        user = get_user(db, call.from_user)
        ensure_bank(user)
        if user['bank']['pin'] is not None:
            bot.answer_callback_query(call.id, "You already have a bank account.")
            return
        msg = bot.send_message(call.message.chat.id, "Enter a 4-digit PIN for your bank account (numbers only):", reply_markup=ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, lambda m: bank_set_pin(m, bot, load_db, save_db, get_user))
        bot.answer_callback_query(call.id)

    def bank_set_pin(message, bot, load_db, save_db, get_user):
        db = load_db()
        user = get_user(db, message.from_user)
        # Fix: Check if message.text is None
        if not message.text or not message.text.strip().isdigit() or len(message.text.strip()) != 4:
            msg = bot.send_message(message.chat.id, "Invalid PIN. Please enter a 4-digit number:")
            bot.register_next_step_handler(msg, lambda m: bank_set_pin(m, bot, load_db, save_db, get_user))
            return
        pin = message.text.strip()
        user['bank']['pin'] = pin
        user['bank']['level'] = 1
        user['bank']['balance'] = 0
        user['bank']['total_deposit'] = 0
        user['bank']['deposit_history'] = []
        user['bank']['withdraw_history'] = []
        save_db(db)
        bot.send_message(message.chat.id, "✅ Bank account created successfully! Use /bank to view your account.")

    @bot.callback_query_handler(func=lambda call: call.data in ["bank_withdraw_history", "bank_deposit_history"])
    def bank_history_callback(call):
        db = load_db()
        user = get_user(db, call.from_user)
        ensure_bank(user)
        if call.data == "bank_withdraw_history":
            history = user['bank']['withdraw_history']
            title = "Withdraw"
        else:
            history = user['bank']['deposit_history']
            title = "Deposit"
        if not history:
            bot.send_message(call.from_user.id, f"No {title} history found.")
        else:
            lines = [f"{title} History:"]
            for h in history[-20:]:
                lines.append(f"{h['amount']} coins at {h['time']}")
            bot.send_message(call.from_user.id, "\n".join(lines))
        bot.answer_callback_query(call.id)

    @bot.message_handler(commands=['deposit', 'd'])
    def deposit_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        ensure_bank(user)
        args = message.text.split()[1:]
        if not args or not args[0].isdigit():
            bot.reply_to(message, "Usage: /deposit <amount>")
            return
        amount = int(args[0])
        if amount <= 0:
            bot.reply_to(message, "Amount must be positive.")
            return
        if user['coins'] < amount:
            bot.reply_to(message, "Insufficient coins.")
            return
        # Check bank level limit
        bank_lvl = user['bank']['level']
        lvl_info = BANK_LEVELS[bank_lvl-1]
        if user['bank']['balance'] + amount > lvl_info['deposit']:
            bot.reply_to(message, f"Your bank level limit is {lvl_info['deposit']} coins. Upgrade your bank to deposit more.")
            return
        user['coins'] -= amount
        user['bank']['balance'] += amount
        user['bank']['total_deposit'] += amount
        user['bank']['deposit_history'].append({"amount": amount, "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        save_db(db)
        bot.reply_to(message, f"Deposited {amount} coins to your bank. New bank balance: {user['bank']['balance']}")

    @bot.message_handler(commands=['withdraw', 'w'])
    def withdraw_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        ensure_bank(user)
        args = message.text.split()[1:]
        if not args or not args[0].isdigit():
            bot.reply_to(message, "Usage: /withdraw <amount>")
            return
        amount = int(args[0])
        if amount <= 0:
            bot.reply_to(message, "Amount must be positive.")
            return
        if user['bank']['balance'] < amount:
            bot.reply_to(message, "Insufficient bank balance.")
            return
        user['bank']['balance'] -= amount
        user['coins'] += amount
        user['bank']['withdraw_history'].append({"amount": amount, "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        save_db(db)
        bot.reply_to(message, f"Withdrew {amount} coins from your bank. New bank balance: {user['bank']['balance']}")