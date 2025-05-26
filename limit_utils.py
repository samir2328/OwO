import time

SEND_LIMIT_COOLDOWN_SECONDS = 10 * 60 * 60  # 10 hours in seconds

def is_in_limit_cooldown(user, now=None):
    if now is None:
        now = int(time.time())
    cooldown_until = user.get('limit_cooldown', 0)
    if cooldown_until > now:
        wait_seconds = cooldown_until - now
        wait_hours = wait_seconds // 3600
        wait_minutes = (wait_seconds % 3600) // 60
        return True, wait_hours, wait_minutes
    return False, 0, 0

def reset_send_window(user, now=None):
    if now is None:
        now = int(time.time())
    user['sent_window_start'] = now
    user['sent_in_window'] = 0

def check_and_update_send_limit(user, amount, limit, now=None):
    if now is None:
        now = int(time.time())
    window_start = user.get('sent_window_start', 0)
    sent_in_window = user.get('sent_in_window', 0)
    # Reset window if expired
    if now - window_start > SEND_LIMIT_COOLDOWN_SECONDS:
        reset_send_window(user, now)
        sent_in_window = 0
        window_start = now
    # Check if this transaction would exceed the limit
    if sent_in_window + amount > limit:
        user['limit_cooldown'] = now + SEND_LIMIT_COOLDOWN_SECONDS
        return False
    user['sent_in_window'] += amount
    return True

def check_and_update_receive_cooldown(user, now=None):
    if now is None:
        now = int(time.time())
    if user.get('limit_cooldown', 0) > 0:
        if now < user['limit_cooldown']:
            return False
        else:
            user['limit_cooldown'] = 0
            user['sent_in_window'] = 0
            user['sent_window_start'] = 0
    return True