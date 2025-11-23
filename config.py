import os, json

CONFIG_FILE = "last_folder.json"

def load_last_folder():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f).get("last_folder", os.path.expanduser("~"))
        except Exception:
            return os.path.expanduser("~")
    return os.path.expanduser("~")

def save_last_folder(folder_path):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"last_folder": folder_path}, f)
