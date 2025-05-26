import os
import time
import shutil
from datetime import datetime

DB_PATH = r'c:\Users\khans\OneDrive\Desktop\nitroogen2\playerdb.json'
BACKUP_DIR = r'c:\Users\khans\OneDrive\Desktop\nitroogen2\backups'

def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def backup_db():
    ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'playerdb_backup_{timestamp}.json')
    shutil.copy2(DB_PATH, backup_file)
    print(f'Backup created: {backup_file}')

if __name__ == '__main__':
    while True:
        backup_db()
        # Sleep for 24 hours (86400 seconds)
        time.sleep(86400)