def os_cmd(message):
    db = load_db()
    user = get_user(db, message.from_user)
    # ... argument checks ...
    win = False
    if user.get('luck') == 'win':
        win = random.randint(1, 11) != 1
    elif user.get('luck') == 'lose':
        win = random.randint(1, 10) == 1
    else:
        win = random.choice([True, False])
    # ... use win variable to decide outcome ...