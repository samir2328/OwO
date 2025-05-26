import random

def register_obj_handler(bot, load_db, save_db, get_user, get_level):
    @bot.message_handler(commands=['obj'])
    def obj_cmd(message):
        db = load_db()
        user = get_user(db, message.from_user)
        args = message.text.split()[1:]
        if len(args) != 1 or not args[0].isdigit():
            bot.reply_to(message, "Usage: /obj <amount>")
            return
        amount = int(args[0])
        user_level = get_level(user['xp'])
        if amount > user_level['limit']:
            bot.reply_to(message, f"Your level limit is {user_level['limit']} coins.")
            return
        if user['coins'] < amount:
            bot.reply_to(message, "Insufficient coins.")
            return
        player_card = random.randint(1, 13)
        bot_card = random.randint(1, 13)
        result_msg = f"🃏 You drew: {player_card}\n🤖 Bot drew: {bot_card}\n"
        if player_card > bot_card:
            user['coins'] += amount
            result_msg += f"You win! +{amount} coins."
        elif player_card < bot_card:
            user['coins'] -= amount
            result_msg += f"You lose! -{amount} coins."
        else:
            result_msg += "It's a tie! No coins won or lost."
        save_db(db)
        bot.reply_to(message, result_msg)