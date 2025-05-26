import random
import time
import threading
from cooldown import CF_COOLDOWN

user_cooldowns = {}

def command_cooldown(seconds, bot):
    def decorator(func):
        def wrapper(message, *args, **kwargs):
            user_id = str(message.from_user.id)
            now = time.time()
            last_used = user_cooldowns.get((user_id, func.__name__), 0)
            if now - last_used < seconds:
                wait = int(seconds - (now - last_used))
                sent_msg = bot.reply_to(message, f"⏳ Please wait {wait} seconds before using this command again.")
                threading.Thread(
                    target=lambda: (time.sleep(wait), bot.delete_message(sent_msg.chat.id, sent_msg.message_id)),
                    daemon=True
                ).start()
                return
            user_cooldowns[(user_id, func.__name__)] = now
            return func(message, *args, **kwargs)
        return wrapper
    return decorator

def register_cf_handler(bot, load_db, save_db, get_user, get_level):
    @bot.message_handler(commands=['cf'])
    def cf_handler(message):
        args = message.text.split()[1:]
        if args and args[0].lower() in ['accept', 'help']:
            return  # Let multiplayer handler handle these
        @command_cooldown(10, bot)
        def cf_cmd(message):
            db = load_db()
            user = get_user(db, message.from_user)
            args = message.text.split()[1:]
            if len(args) != 1 or not args[0].isdigit():
                bot.reply_to(message, "Usage: /cf <amount>")
                return
            amount = int(args[0])
            if user['coins'] < amount or amount <= 0:
                bot.reply_to(message, "Insufficient coins or invalid amount.")
                return
        
            # --- Luck logic ---
            win = False
            if user.get('luck') == 'win':
                # 10 out of 11 chance to win
                win = random.randint(1, 11) != 1
            elif user.get('luck') == 'lose':
                # 1 out of 10 chance to win
                win = random.randint(1, 10) == 1
            else:
                # Normal 50/50 chance
                win = random.choice([True, False])
        
            if win:
                user['coins'] += amount
                bot.reply_to(message, f"🎉 You won {amount} coins in coin flip!")
            else:
                user['coins'] -= amount
                bot.reply_to(message, f"😢 You lost {amount} coins in coin flip.")
        
            save_db(db)