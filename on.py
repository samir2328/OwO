import subprocess
import time
import sys
import os

BOT_SCRIPT = "owo_bot.py"

while True:
    try:
        # Use sys.executable to ensure the same Python interpreter is used
        process = subprocess.Popen([sys.executable, BOT_SCRIPT])
        process.wait()
    except Exception as e:
        print(f"Bot crashed with error: {e}")
    print("Bot stopped. Restarting in 5 seconds...")
    time.sleep(5)