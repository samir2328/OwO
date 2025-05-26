import random

def register_oddandout_handler(bot, load_db, save_db, get_user, get_level):
    @bot.message_handler(commands=['odd'])
    def odd_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        args = message.text.split()[1:]
        if len(args) != 1 or not args[0].isdigit():
            bot.reply_to(message, "Usage: /odd <amount>")
            return
        amount = int(args[0])
        user_level = get_level(user['xp'])
        if amount > user_level['limit']:
            bot.reply_to(message, f"Your level limit is {user_level['limit']} coins.")
            return
        if user['coins'] < amount:
            bot.reply_to(message, "Insufficient coins.")
            return

        # 1 in 100 chance to win
        win = random.randint(1, 100) == 1
        if win:
            win_amount = amount * 100
            user['coins'] += win_amount
            result_msg = f"🎉 ODD AND OUT: You WON! +{win_amount} coins (100x)!"
        else:
            user['coins'] -= amount
            result_msg = f"😢 ODD AND OUT: You lost! -{amount} coins. Try again!"

        save_db(db)
        bot.reply_to(message, result_msg)