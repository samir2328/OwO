import random
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# In-memory storage for requests and games
pending_requests = {}  # chat_id: {from_id, to_id, amount, timestamp}
active_games = {}      # chat_id: {players, amount, mine_index, turn, board, timestamp, winner}

# Top winners (should be persisted in DB in production)
top_winners = {}

# Add this global dictionary at the top (after top_winners = {})
single_player_losses = {}

def register_mines_handlers(bot, load_db, save_db, get_user):
    @bot.message_handler(commands=['mines', 'mine'], func=lambda m: m.chat.type in ['group', 'supergroup'])
    def mines_handler(message):
        args = message.text.split()[1:]
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        if not args:
            bot.reply_to(message,
                "💣 *Mines Game Commands:*\n"
                "/mines top - Show top winners\n"
                "/mines {amount} {user} - Request a duel\n"
                "/mines accept - Accept a duel request\n"
                "\nGame is duo only, not playable in DM, and only in groups.\n"
                "When a duel is accepted, a 3x3 grid appears. One cell is a mine. "
                "Players take turns clicking. Whoever hits the mine loses and the other wins the amount."
                "\nRequests expire in 60 seconds. If a player leaves or doesn't play in 1 minute, both lose."
                , parse_mode="Markdown")
            return

        if args[0] == "top":
            if not top_winners:
                bot.reply_to(message, "No winners yet.")
                return
            sorted_winners = sorted(top_winners.items(), key=lambda x: x[1], reverse=True)[:10]
            msg = "🏆 *Mines Top Winners:*\n"
            for i, (uname, amt) in enumerate(sorted_winners, 1):
                msg += f"{i}. {uname}: {amt} coins\n"
            bot.reply_to(message, msg, parse_mode="Markdown")
            return

        if args[0] == "accept":
            req = pending_requests.get(chat_id)
            if not req or req['to_id'] != user_id:
                bot.reply_to(message, "No pending request for you.")
                return
            # Start game
            players = [req['from_id'], req['to_id']]
            random.shuffle(players)
            mine_index = random.randint(0, 8)
            board = [None] * 9
            active_games[chat_id] = {
                "players": players,
                "amount": req['amount'],
                "mine_index": mine_index,
                "turn": 0,
                "board": board,
                "timestamp": time.time(),
                "winner": None
            }
            del pending_requests[chat_id]
            send_mines_board(bot, chat_id, players, board, mine_index, req['amount'])
            return

        # /mines {amount} {user}
        if len(args) == 2:
            try:
                amount = int(args[0])
            except Exception:
                bot.reply_to(message, "Invalid amount.")
                return
            target_username = args[1].lstrip('@')
            if target_username.lower() == (message.from_user.username or "").lower():
                bot.reply_to(message, "You cannot invite yourself.")
                return
            db = load_db()
            user = get_user(db, message.from_user)
            if user['coins'] < amount or amount <= 0:
                bot.reply_to(message, "Insufficient coins.")
                return
            target_user = next((u for u in db.values() if isinstance(u, dict) and u.get('username', '').lower() == target_username.lower()), None)
            if not target_user:
                bot.reply_to(message, f"User @{target_username} not found.")
                return
            if chat_id in pending_requests:
                bot.reply_to(message, "There is already a pending request in this group. Wait for it to expire or be accepted.")
                return
            if chat_id in active_games:
                bot.reply_to(message, "A game is already active in this group.")
                return
            pending_requests[chat_id] = {
                "from_id": user_id,
                "to_id": target_user['id'],
                "amount": amount,
                "timestamp": time.time()
            }
            bot.reply_to(message, f"@{target_username}, you have been challenged to a Mines duel for {amount} coins! Type /mines accept to play. (Expires in 60s)")
            return

        # --- Single player mode: /mines {amount} ---
        if len(args) == 1 and args[0].isdigit():
            amount = int(args[0])
            db = load_db()
            user = get_user(db, message.from_user)
            if user['coins'] < amount or amount <= 0:
                bot.reply_to(message, "Insufficient coins.")
                return
            user['coins'] -= amount
            save_db(db)
            players = [user['id'], 'bot']
            mine_index = random.randint(0, 8)
            board = [None] * 9
            chat_game_id = f"single_{chat_id}_{user['id']}"
            active_games[chat_game_id] = {
                "players": players,
                "amount": amount,
                "mine_index": mine_index,
                "turn": 0,  # 0: user, 1: bot
                "board": board,
                "timestamp": time.time(),
                "winner": None,
                "single": True,
                "user_turns": 0  # Track user turns
            }
            send_mines_board(bot, chat_id, players, board, mine_index, amount, next_turn=False, message_id=None, single_game_id=chat_game_id)
            return

        bot.reply_to(message, "Invalid command. Use /mines to see help.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("mines_"))
    def mines_button_handler(call):
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        chat_game_id = f"single_{chat_id}_{user_id}"
        game = active_games.get(chat_game_id)
        if not game:
            game = active_games.get(chat_id)
            single_mode = False
        else:
            single_mode = True

        if not game:
            bot.answer_callback_query(call.id, "No active game.")
            return
        if game['winner'] is not None:
            bot.answer_callback_query(call.id, "Game already finished.")
            return
        if single_mode:
            if game['players'][game['turn']] != user_id:
                bot.answer_callback_query(call.id, "Not your turn!")
                return
        else:
            if user_id != game['players'][game['turn']]:
                bot.answer_callback_query(call.id, "Not your turn!")
                return
        idx = int(call.data.split("_")[1])
        if game['board'][idx] is not None:
            bot.answer_callback_query(call.id, "Already chosen.")
            return

        # --- Single player: force user to lose on 2nd turn ---
        if single_mode and game['turn'] == 0:
            game['user_turns'] = game.get('user_turns', 0) + 1
            if game['user_turns'] == 2:
                # Force the user to hit the mine on their 2nd turn
                idx = game['mine_index']

        game['board'][idx] = user_id if not single_mode or game['turn'] == 0 else 'bot'
        if idx == game['mine_index']:
            loser = user_id if not single_mode or game['turn'] == 0 else 'bot'
            winner = game['players'][1 - game['turn']]
            game['winner'] = winner
            db = load_db()
            if single_mode:
                user = get_user(db, call.from_user)
                bot.edit_message_text(
                    f"💥 You hit the mine on your 2nd turn!\n🤖 Bot wins. You lost {game['amount']} coins.",
                    chat_id, call.message.message_id
                )
                del active_games[chat_game_id]
            else:
                loser_user = get_user(db, call.from_user)
                winner_user = next((u for u in db.values() if isinstance(u, dict) and u['id'] == winner), None)
                if loser_user and winner_user:
                    loser_user['coins'] -= game['amount']
                    winner_user['coins'] += game['amount']
                    save_db(db)
                    top_winners[winner_user['username']] = top_winners.get(winner_user['username'], 0) + game['amount']
                bot.edit_message_text(
                    f"💥 {call.from_user.username or call.from_user.first_name} hit the mine!\n"
                    f"🏆 {winner_user['username']} wins {game['amount']} coins!",
                    chat_id, call.message.message_id
                )
                del active_games[chat_id]
            return
        # Switch turn
        game['turn'] = 1 - game['turn']
        if single_mode and game['turn'] == 1 and game['winner'] is None:
            # Bot's turn: pick a random available cell (always safe)
            available = [i for i, v in enumerate(game['board']) if v is None]
            if available:
                safe_choices = [i for i in available if i != game['mine_index']]
                if safe_choices:
                    bot_choice = random.choice(safe_choices)
                else:
                    bot_choice = game['mine_index']
                game['board'][bot_choice] = 'bot'
                # Switch back to user
                game['turn'] = 0
                send_mines_board(bot, chat_id, game['players'], game['board'], game['mine_index'], game['amount'], next_turn=False, message_id=call.message.message_id, single_game_id=chat_game_id)
                bot.answer_callback_query(call.id, "Safe! Bot's turn played.")
                return
        send_mines_board(bot, chat_id, game['players'], game['board'], game['mine_index'], game['amount'], next_turn=True, message_id=call.message.message_id, single_game_id=chat_game_id if single_mode else None)
        bot.answer_callback_query(call.id, "Safe! Next player's turn.")

    # Background thread to expire requests and games
    def mines_cleanup():
        while True:
            now = time.time()
            # Expire requests
            expired = [cid for cid, req in pending_requests.items() if now - req['timestamp'] > 60]
            for cid in expired:
                del pending_requests[cid]
            # Expire games
            expired_games = [cid for cid, game in active_games.items() if now - game['timestamp'] > 60]
            for cid in expired_games:
                bot.send_message(cid, "⏰ Mines game expired due to inactivity. Both players lose their chance (no refund).")
                del active_games[cid]
            time.sleep(5)
    import threading
    threading.Thread(target=mines_cleanup, daemon=True).start()

def send_mines_board(bot, chat_id, players, board, mine_index, amount, next_turn=False, message_id=None, single_game_id=None):
    # For single player, show "You" and "Bot"
    if single_game_id:
        turn_user = "You" if not next_turn else "Bot"
        turn_msg = f"Now <b>{turn_user}</b> turn! Choose a cell."
    else:
        turn_user_id = players[0] if not next_turn else players[1]
        turn_msg = f"Now <b>@{str(turn_user_id)}</b> your turn! Choose a cell."
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(9):
        label = "❓" if board[i] is None else ("🤖" if board[i] == 'bot' else "✅")
        buttons.append(InlineKeyboardButton(label, callback_data=f"mines_{i}"))
    for row in range(0, 9, 3):
        markup.add(*buttons[row:row+3])
    if message_id:
        bot.edit_message_text(
            f"💣 Mines Game for {amount} coins\n{turn_msg}",
            chat_id, message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            chat_id,
            f"💣 Mines Game for {amount} coins\n{turn_msg}",
            reply_markup=markup,
            parse_mode="HTML"
        )