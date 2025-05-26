import json
import os

def save_db(db, path):
    # Don't save if db is empty
    if not db:
        print("Warning: Attempted to save empty DB. Operation aborted.")
        return
    tmp_path = path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)