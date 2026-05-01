import json
import time
from datetime import datetime

POLICY_PATH = "rrmPolicy_uplink.json"
MAX_RATIO_SEQUENCE = [70,60,50]
UPDATE_INTERVAL = 120

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

def run():
    index = 0
    print(f"UplinkController started, update interval: {UPDATE_INTERVAL}s")
    print(f"max_ratio sequence: {MAX_RATIO_SEQUENCE}")

    while True:
        try:
            max_ratio = MAX_RATIO_SEQUENCE[index]
            data = load_json(POLICY_PATH)
            data["slice2"]["min_ratio"] = 0
            data["slice2"]["max_ratio"] = max_ratio
            save_json(data, POLICY_PATH)
            print(f"[{datetime.now()}] slice2 updated: min_ratio=0, max_ratio={max_ratio}")
            index = (index + 1) % len(MAX_RATIO_SEQUENCE)
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    run()
