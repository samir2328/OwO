import json
import os
import random
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import telebot  # <-- Add this line

DB_PATH = os.path.join(os.path.dirname(__file__), 'playerdb.json')
API_TOKEN = '7026873857:AAEZs64VIwmozKGIGeczH4BkfYDoM0oNGyo'
bot = telebot.TeleBot(API_TOKEN)
CONSOLE_LOG_PATH = os.path.join(os.path.dirname(__file__), 'admin_console.log')

app = Flask(__name__)

def log_console(user, cmd, reply):
    with open(CONSOLE_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"User: {user['username']} (ID: {user['id']}) | CMD: {cmd} | Bot Reply: {reply}\n")

def load_console_logs(lines=30):
    if not os.path.exists(CONSOLE_LOG_PATH):
        return []
    with open(CONSOLE_LOG_PATH, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
    return all_lines[-lines:]

def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, 'w') as f:
            json.dump({}, f)
    with open(DB_PATH, 'r') as f:
        db = json.load(f)
    # Assign token if missing
    changed = False
    for user in db.values():
        if not isinstance(user, dict):
            continue  # Skip non-user entries like 'groups'
        if 'token' not in user:
            user['token'] = str(random.randint(10**9, 10**10-1))
            changed = True
    if changed:
        save_db(db)
    return db

def save_db(db):
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2)

FREE_MONEY_PATH = os.path.join(os.path.dirname(__file__), 'free_money.json')

def load_free_money_settings():
    if not os.path.exists(FREE_MONEY_PATH):
        return []
    with open(FREE_MONEY_PATH, 'r') as f:
        return json.load(f)

def save_free_money_settings(settings):
    with open(FREE_MONEY_PATH, 'w') as f:
        json.dump(settings, f, indent=2)

@app.route('/', methods=['GET', 'POST'])
def index():
    db = load_db()
    users = [u for u in db.values() if isinstance(u, dict) and 'id' in u]
    groups = db.get('groups', [])
    broadcast_status = None

    # Add this line to count total users
    total_users = len(users)

    # --- Free Money Settings (Multiple) ---
    free_money_settings = load_free_money_settings()
    if request.method == 'POST' and 'add_free_money_cmd' in request.form:
        cmd = request.form['add_free_money_cmd'].strip().lstrip('/')
        try:
            money = int(request.form['add_free_money_money'])
        except Exception:
            money = 10000
        # Prevent duplicates
        if not any(fm['cmd'] == cmd for fm in free_money_settings):
            free_money_settings.append({'cmd': cmd, 'money': money})
            save_free_money_settings(free_money_settings)
            # Removed: owo_bot.reload_free_money_handlers()

    if request.method == 'POST' and 'remove_free_money_cmd' in request.form:
        cmd = request.form['remove_free_money_cmd']
        free_money_settings = [fm for fm in free_money_settings if fm['cmd'] != cmd]
        save_free_money_settings(free_money_settings)
        # Removed: owo_bot.reload_free_money_handlers()

    if request.method == 'POST' and 'broadcast_msg' in request.form:
        msg = request.form['broadcast_msg']
        # Send to all users
        sent_count = 0
        for user in users:
            try:
                bot.send_message(user['id'], msg)
                sent_count += 1
            except Exception:
                pass
        # Send to all groups
        for group_id in groups:
            try:
                bot.send_message(group_id, msg)
                sent_count += 1
            except Exception:
                pass
        broadcast_status = f"Broadcast sent to {sent_count} users/groups."

    # Admins list for display
    admins = []
    if "admins" in db:
        for uid in db["admins"]:
            user = db.get(str(uid))
            if user:
                admins.append(user)
            else:
                admins.append({"id": uid, "username": "(not found)"})

    console_logs = load_console_logs()

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Bot Admin Panel</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            body { background: #181a1b; color: #f8f9fa; }
            .container { margin-top: 40px; }
            h2 { margin-bottom: 30px; color: #fff; }
            table { background: #23272b; color: #f8f9fa; }
            .table-dark th, .table-dark td { background: #23272b; color: #f8f9fa; }
            .form-control { background: #23272b; color: #f8f9fa; border: 1px solid #444; }
            .form-control:focus { background: #23272b; color: #fff; }
            .modal-content { background: #23272b; color: #f8f9fa; }
            .btn-primary { background: #375a7f; border: none; }
            .btn-danger { background: #e74c3c; border: none; }
            .btn-success { background: #00bc8c; border: none; }
            .btn-secondary { background: #444; border: none; }
            .ban-btn { min-width: 80px; }
            .badge.bg-danger { background: #e74c3c; }
            .badge.bg-success { background: #00bc8c; }
            .navbar { background: #23272b; }
            .navbar-brand, .nav-link, .navbar-text { color: #f8f9fa !important; }
        </style>
    </head>
    <body>
    <!-- Navbar -->
    <nav class="navbar navbar-expand-lg navbar-dark">
      <div class="container-fluid">
        <a class="navbar-brand" href="#">Admin Panel</a>
        <div class="collapse navbar-collapse">
          <ul class="navbar-nav me-auto mb-2 mb-lg-0">
            <li class="nav-item">
              <a class="nav-link active" aria-current="page" href="#">Users</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="#broadcast">Broadcast</a>
            </li>
          </ul>
          <span class="navbar-text">
            Telegram OWO Bot
          </span>
        </div>
      </div>
    </nav>
    <div class="container">
        <h2 class="text-center">Telegram Bot Admin Panel</h2>
        <!-- Add this line to show total user count -->
        <div class="alert alert-info text-center" role="alert">
            Total Users: {{ total_users }}
        </div>
        <!-- Free Money Section (Add/Remove SMD) -->
        <div class="card bg-dark text-white mb-3">
            <div class="card-header">Free Money Commands</div>
            <div class="card-body">
                <form method="post" class="row g-3 align-items-center mb-3">
                    <div class="col-auto">
                        <label for="add_free_money_cmd" class="col-form-label">Command:</label>
                    </div>
                    <div class="col-auto">
                        <input type="text" class="form-control" id="add_free_money_cmd" name="add_free_money_cmd" placeholder="e.g. freecoin" required>
                    </div>
                    <div class="col-auto">
                        <label for="add_free_money_money" class="col-form-label">Money:</label>
                    </div>
                    <div class="col-auto">
                        <input type="number" class="form-control" id="add_free_money_money" name="add_free_money_money" placeholder="e.g. 10000" required>
                    </div>
                    <div class="col-auto">
                        <button type="submit" class="btn btn-success">Add Command</button>
                    </div>
                </form>
                <hr>
                <h6>Current Free Money Commands:</h6>
                <table class="table table-dark table-sm table-bordered">
                    <thead>
                        <tr>
                            <th>Command</th>
                            <th>Money</th>
                            <th>Remove</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for fm in free_money_settings %}
                        <tr>
                            <td>/{{ fm.cmd }}</td>
                            <td>{{ fm.money }}</td>
                            <td>
                                <form method="post" style="display:inline;">
                                    <input type="hidden" name="remove_free_money_cmd" value="{{ fm.cmd }}">
                                    <button type="submit" class="btn btn-danger btn-sm">Remove</button>
                                </form>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <hr>
                <h6>User Claim Counts:</h6>
                <table class="table table-dark table-sm table-bordered">
                    <thead>
                        <tr>
                            <th>User</th>
                            {% for fm in free_money_settings %}
                                <th>/{{ fm.cmd }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>{{ user['username'] }}</td>
                            {% for fm in free_money_settings %}
                                <td>{{ user.get('free_money_claims', {}).get(fm.cmd, 0) }}</td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <!-- Broadcast Section -->
        <div id="broadcast" class="mb-4">
            <div class="card bg-dark text-white mb-3">
                <div class="card-header">Broadcast Message</div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3">
                            <textarea class="form-control" name="broadcast_msg" rows="3" placeholder="Enter message to broadcast..." required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary">Send Broadcast</button>
                    </form>
                    {% if broadcast_status %}
                        <div class="alert alert-info mt-3">{{ broadcast_status }}</div>
                    {% endif %}
                </div>
            </div>
        </div>
        <table class="table table-bordered table-hover table-dark align-middle">
            <thead class="table-dark">
                <tr>
                    <th>User ID</th>
                    <th>Username</th>
                    <th>Balance</th>
                    <th>XP</th>
                    <th>Token</th>
                    <th>Banned</th>
                    <th>Ban Reason</th>
                    <th>Luck Mode</th> <!-- Add this -->
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
            {% for user in users %}
                <tr>
                <form method="post" action="{{ url_for('update', uid=user['id']) }}">
                    <td>{{ user['id'] }}</td>
                    <td>{{ user['username'] }}</td>
                    <td><input type="number" class="form-control" name="coins" value="{{ user['coins'] }}"></td>
                    <td><input type="number" class="form-control" name="xp" value="{{ user['xp'] }}"></td>
                    <td>{{ user['token'] }}</td>
                    <td class="text-center">
                        {% if user.get('banned', False) %}
                            <span class="badge bg-danger">Banned</span>
                        {% else %}
                            <span class="badge bg-success">Active</span>
                        {% endif %}
                    </td>
                    <td>
                        {% if user.get('banned', False) %}
                            {{ user.get('ban_reason', '') }}
                        {% endif %}
                    </td>
                    <td>
                        <select class="form-control" name="luck">
                            <option value="random" {% if user.get('luck', 'random') == 'random' %}selected{% endif %}>Random</option>
                            <option value="lose" {% if user.get('luck', 'random') == 'lose' %}selected{% endif %}>Lose</option>
                            <option value="win" {% if user.get('luck', 'random') == 'win' %}selected{% endif %}>Win</option>
                        </select>
                    </td>
                    <td>
                        <button type="submit" class="btn btn-primary btn-sm">Update</button>
                        {% if user.get('banned', False) %}
                            <a href="#" class="btn btn-success btn-sm ban-btn unban-btn" data-uid="{{ user['id'] }}" data-username="{{ user['username'] }}">Unban</a>
                        {% else %}
                            <a href="#" class="btn btn-danger btn-sm ban-btn ban-user-btn" data-uid="{{ user['id'] }}" data-username="{{ user['username'] }}">Ban</a>
                        {% endif %}
                    </td>
                </form>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        <!-- Admin Management Section -->
        <div class="card bg-dark text-white mb-3">
            <div class="card-header">Admin Management</div>
            <div class="card-body">
                <form method="post" action="{{ url_for('addadmin') }}" class="mb-3 d-flex">
                    <input type="text" class="form-control me-2" name="username" placeholder="Username to add as admin" required>
                    <button type="submit" class="btn btn-success">Add Admin</button>
                </form>
                <form method="post" action="{{ url_for('removeadmin') }}" class="mb-3 d-flex">
                    <input type="text" class="form-control me-2" name="username" placeholder="Username to remove from admin" required>
                    <button type="submit" class="btn btn-danger">Remove Admin</button>
                </form>
                <h5>Current Admins:</h5>
                <ul>
                    {% for admin in admins %}
                        <li>{{ admin.username }} (ID: {{ admin.id }})</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
    <!-- Console Section -->
    <div class="card bg-dark text-white mb-3">
        <div class="card-header d-flex justify-content-between align-items-center">
            <span>Console</span>
            <button class="btn btn-secondary btn-sm" onclick="location.reload()">Refresh</button>
        </div>
        <div class="card-body" style="max-height:300px; overflow-y:auto; font-family:monospace;">
            {% if console_logs %}
                <pre style="white-space: pre-wrap;">{{ console_logs|join('') }}</pre>
            {% else %}
                <p>No console logs yet.</p>
            {% endif %}
        </div>
    </div>
    <!-- Ban Reason Modal -->
    <div class="modal" tabindex="-1" id="banModal">
      <div class="modal-dialog">
        <div class="modal-content">
          <form id="banForm" method="post">
            <div class="modal-header">
              <h5 class="modal-title">Ban User: <span id="banUserName"></span></h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <label for="banReason" class="form-label">Reason for ban:</label>
              <input type="text" class="form-control" id="banReason" name="ban_reason" required>
              <input type="hidden" id="banUserId" name="uid">
            </div>
            <div class="modal-footer">
              <button type="submit" class="btn btn-danger">Ban</button>
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    $(document).ready(function(){
        var banModal = new bootstrap.Modal(document.getElementById('banModal'));
        $('.ban-user-btn').click(function(){
            var uid = $(this).data('uid');
            var username = $(this).data('username');
            $('#banUserId').val(uid);
            $('#banUserName').text(username);
            $('#banReason').val('');
            banModal.show();
        });
        $('#banForm').submit(function(e){
            e.preventDefault();
            var uid = $('#banUserId').val();
            var reason = $('#banReason').val();
            $.post('/toggle_ban/' + uid, {ban_reason: reason}, function(){
                location.reload();
            });
        });
        $('.unban-btn').click(function(){
            var uid = $(this).data('uid');
            $.post('/toggle_ban/' + uid, {}, function(){
                location.reload();
            });
        });
    });
    </script>
    </body>
    </html>
    ''', users=users, broadcast_status=broadcast_status, console_logs=console_logs, admins=admins, free_money_settings=free_money_settings, total_users=total_users)

### 2. Save Luck Mode on Update


@app.route('/update/<int:uid>', methods=['POST'])
def update(uid):
    db = load_db()
    user = db.get(str(uid))
    if user:
        old_coins = user['coins']
        old_xp = user['xp']
        user['coins'] = int(request.form['coins'])
        user['xp'] = int(request.form['xp'])
        user['xp'] += 100  # Give 100 XP for admin action
        # Save luck mode
        user['luck'] = request.form.get('luck', 'random')
        save_db(db)
        reply = f"User updated: coins {old_coins}->{user['coins']}, xp {old_xp}->{user['xp']}, luck: {user['luck']}"
        log_console(user, "update", reply)
    return redirect(url_for('index'))

@app.route('/toggle_ban/<int:uid>', methods=['POST'])
def toggle_ban(uid):
    db = load_db()
    user = db.get(str(uid))
    if user:
        if user.get('banned', False):
            user['banned'] = False
            user['ban_reason'] = ""
            user['xp'] += 100  # Give 100 XP for admin action
            save_db(db)
            reply = f"{user['username']} you are unbaned"
            log_console(user, "unban", reply)
            try:
                bot.send_message(user['id'], reply)
            except Exception:
                pass
        else:
            user['banned'] = True
            user['ban_reason'] = request.form.get('ban_reason', '')
            user['xp'] += 100  # Give 100 XP for admin action
            save_db(db)
            reply = f"{user['ban_reason']}\n{user['token']} {user['username']} you are baned from this game\nis you want any help then msg hum @samir2329"
            log_console(user, "ban", reply)
            try:
                bot.send_message(
                    user['id'],
                    reply
                )
            except Exception:
                pass
    return ('', 204)

@app.route('/addadmin', methods=['POST'])
def addadmin():
    db = load_db()
    username = request.form.get('username', '').strip()
    if not username:
        return redirect(url_for('index'))
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username', '').lower() == username.lower()), None)
    if user:
        admins = db.get("admins", [])
        if user['id'] not in admins:
            admins.append(user['id'])
            db["admins"] = admins
            save_db(db)
    return redirect(url_for('index'))

@app.route('/removeadmin', methods=['POST'])
def removeadmin():
    db = load_db()
    username = request.form.get('username', '').strip()
    if not username:
        return redirect(url_for('index'))
    user = next((u for u in db.values() if isinstance(u, dict) and u.get('username', '').lower() == username.lower()), None)
    if user:
        admins = db.get("admins", [])
        if user['id'] in admins:
            admins.remove(user['id'])
            db["admins"] = admins
            save_db(db)
    return redirect(url_for('index'))

# REMOVE this entire block:
# @bot.message_handler(commands=['freecoin'])
# def freecoin_cmd(message):
#     db = load_db()
#     user = db.get(str(message.from_user.id))
#     if not user:
#         bot.reply_to(message, "User not found in database.")
#         return
#     amount = random.randint(10000, 10000000)
#     user['coins'] += amount
#     save_db(db)
#     bot.reply_to(message, f"🎉 You received {amount} free coins!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


# --- OWO BOT SIDE: Add dynamic free money command handler ---
def register_free_money_handler(bot, load_db, save_db, get_user):
    from functools import partial
    import types

    def make_handler(cmd, money):
        @bot.message_handler(commands=[cmd])
        def free_money_cmd(message):
            db = load_db()
            user = get_user(db, message.from_user)
            # Ensure per-command claim tracking
            if 'free_money_claims' not in user:
                user['free_money_claims'] = {}
            if user['free_money_claims'].get(cmd, 0) >= 1:
                bot.reply_to(message, f"You have already claimed /{cmd}.")
                return
            user['coins'] += money
            user['free_money_claims'][cmd] = user['free_money_claims'].get(cmd, 0) + 1
            save_db(db)
            bot.reply_to(message, f"🎉 You received {money} free coins from /{cmd}!")
        return free_money_cmd

    # Remove old handlers for previous commands if any
    for handler in list(bot.message_handlers):
        if hasattr(handler['function'], '_is_free_money'):
            bot.message_handlers.remove(handler)

    settings = load_free_money_settings()
    # Support multiple commands
    for fm in settings:
        handler = make_handler(fm['cmd'], fm['money'])
        handler._is_free_money = True

# --- In your main bot file, after loading settings, call: ---
# import admin_panel
# admin_panel.register_free_money_handler(bot, load_db, save_db, get_user)