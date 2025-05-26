import random

def register_dice_handler(bot, load_db, save_db, get_user, get_level):
    @bot.message_handler(commands=['dice'])
    def dice_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        args = message.text.split()[1:]
        if len(args) != 1 or not args[0].isdigit():
            bot.reply_to(message, "Usage: /dice <amount>")
            return
        amount = int(args[0])
        user_level = get_level(user['xp'])
        if amount > user_level['limit']:
            bot.reply_to(message, f"Your level limit is {user_level['limit']} coins.")
            return
        if user['coins'] < amount:
            bot.reply_to(message, "Insufficient coins.")
            return

        user_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        result_msg = f"🎲 You rolled: {user_roll}\n🤖 Bot rolled: {bot_roll}\n"
        if user_roll > bot_roll:
            user['coins'] += amount
            result_msg += f"You win! +{amount} coins."
        elif user_roll < bot_roll:
            user['coins'] -= amount
            result_msg += f"You lose! -{amount} coins."
        else:
            result_msg += "It's a tie! No coins won or lost."
        save_db(db)
        bot.reply_to(message, result_msg)