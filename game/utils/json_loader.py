# game/utils/json_loader.py

import os
import json

def load_json_files(directory):
    """
    Loads all JSON files in a directory into a list of dictionaries.
    """
    data_list = []
    if not os.path.exists(directory):
        print(f"⚠️ Directory {directory} does not exist.")
        return data_list

    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            path = os.path.join(directory, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data_list.append(data)
            except Exception as e:
                print(f"❌ Failed to load {filename}: {e}")
    return data_list
