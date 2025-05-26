import random
import time

# In-memory storage for pending cf requests and active games
pending_cf_requests = {}  # chat_id: {from_id, to_id, amount, timestamp}
active_cf_games = {}      # chat_id: {players, amount, timestamp, winner}

def register_cf_multiplayer_handlers(bot, load_db, save_db, get_user):
    @bot.message_handler(commands=['cf'])
    def cf_multiplayer_handler(message):
        args = message.text.split()[1:]
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        # --- /cf req list ---
        if args and args[0].lower() == "req" and len(args) > 1 and args[1].lower() == "list":
            # List all requests sent to this user in this chat
            requests = [
                req for req in pending_cf_requests.values()
                if req['to_id'] == user_id and req.get('chat_id', chat_id) == chat_id
            ]
            if not requests:
                bot.reply_to(message, "No pending cf requests for you in this chat.")
            else:
                lines = ["Pending cf requests for you:"]
                db = load_db()
                for req in requests:
                    from_user = db.get(str(req['from_id']), {"username": "Unknown"})
                    lines.append(f"From @{from_user.get('username', 'Unknown')} for {req['amount']} coins")
                bot.reply_to(message, "\n".join(lines))
            return

        # --- /cf accept ---
        if args and args[0].lower() == "accept":
            # Find a pending request for this user in this chat
            req = None
            for r in pending_cf_requests.values():
                if r['to_id'] == user_id and r.get('chat_id', chat_id) == chat_id:
                    req = r
                    break
            if not req:
                bot.reply_to(message, "No pending challenge for you.")
                return
            # Start game
            players = [req['from_id'], req['to_id']]
            random.shuffle(players)
            winner_id = random.choice(players)
            loser_id = players[0] if players[1] == winner_id else players[1]
            db = load_db()
            winner = get_user(db, type('User', (), {'id': winner_id})())
            loser = get_user(db, type('User', (), {'id': loser_id})())
            amount = req['amount']
            if loser['coins'] < amount:
                bot.reply_to(message, f"{loser['username']} does not have enough coins.")
                # Remove this request
                for k in list(pending_cf_requests.keys()):
                    if pending_cf_requests[k] == req:
                        del pending_cf_requests[k]
                return
            loser['coins'] -= amount
            winner['coins'] += amount
            save_db(db)
            bot.send_message(chat_id,
                f"🎲 Coin Flip Result:\n"
                f"@{winner['username']} wins {amount} coins from @{loser['username']}!"
            )
            # Remove this request
            for k in list(pending_cf_requests.keys()):
                if pending_cf_requests[k] == req:
                    del pending_cf_requests[k]
            return

        # --- /cf {username} {amount} ---
        if len(args) == 2:
            try:
                amount = int(args[1])
            except Exception:
                bot.reply_to(message, "Invalid amount.")
                return
            target_username = args[0].lstrip('@')
            if target_username.lower() == (message.from_user.username or "").lower():
                bot.reply_to(message, "You cannot challenge yourself.")
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
            if target_user['coins'] < amount:
                bot.reply_to(message, f"User @{target_username} does not have enough coins.")
                return
            # Allow multiple requests per user in a chat
            req_id = f"{chat_id}_{user_id}_{target_user['id']}_{int(time.time())}"
            pending_cf_requests[req_id] = {
                "from_id": user_id,
                "to_id": target_user['id'],
                "amount": amount,
                "timestamp": time.time(),
                "chat_id": chat_id
            }
            bot.reply_to(message, f"@{target_username}, you have been challenged to a coin flip for {amount} coins! Type /cf accept to play. (Expires in 60s)")
            return

        # --- /cf help or fallback ---
        if not args or args[0].lower() == "help":
            bot.reply_to(message,
                "🎲 *CF Multiplayer Commands:*\n"
                "/cf help - Show this help message\n"
                "/cf <amount> - Single player coin flip\n"
                "/cf <username> <amount> - Challenge a user to a coin flip\n"
                "/cf accept - Accept a pending challenge\n"
                "/cf req list - List all pending cf requests for you\n"
                "\nHow it works:\n"
                "- Both players must have enough coins\n"
                "- Winner is chosen randomly\n"
                "- If you win, you get the amount from the other player\n"
                "- Requests expire in 60 seconds\n",
                parse_mode="Markdown"
            )
            return

        # If only one argument and it's a number, let single player handler process it
        if len(args) == 1 and args[0].isdigit():
            return  # Do nothing, so single player handler can process

        # Fallback: show help
        bot.reply_to(message,
            "🎲 *CF Multiplayer Commands:*\n"
            "/cf help - Show this help message\n"
            "/cf <amount> - Single player coin flip\n"
            "/cf <username> <amount> - Challenge a user to a coin flip\n"
            "/cf accept - Accept a pending challenge\n"
            "/cf req list - List all pending cf requests for you\n"
            "\nHow it works:\n"
            "- Both players must have enough coins\n"
            "- Winner is chosen randomly\n"
            "- If you win, you get the amount from the other player\n"
            "- Requests expire in 60 seconds\n",
            parse_mode="Markdown"
        )

    # Background thread to expire requests
    def cf_cleanup():
        while True:
            now = time.time()
            expired = [k for k, req in pending_cf_requests.items() if now - req['timestamp'] > 60]
            for k in expired:
                del pending_cf_requests[k]
            time.sleep(5)
    import threading
    threading.Thread(target=cf_cleanup, daemon=True).start()