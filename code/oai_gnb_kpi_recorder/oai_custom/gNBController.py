import json
import time
import random
from datetime import datetime

class RMMPolicyController:
    def __init__(self, update_interval: int = 300, max_slices: int = 5, last_n_ues: int = 2):
        self.rmmpolicy_path = "rrmPolicy_sub.json"
        self.update_interval = update_interval
        self.max_slices = max_slices
        self.last_n_ues = last_n_ues

    def load_json(self, file_path):
        """Load JSON file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None

    def save_json(self, data, file_path):
        """Save JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Successfully saved file: {file_path}")
        except Exception as e:
            print(f"Error saving file {file_path}: {str(e)}")

    def generate_new_slice(self):
        """Generate new slice configuration"""
        return {
            "sST": 1,
            "sD_flag": 0,
            "sD": 1,
            "min_ratio": random.randint(0, 40),
            "max_ratio": random.randint(60, 100)
        }

    def update_rmmpolicy(self):
        """Update RMM policy file"""
        data = self.load_json(self.rmmpolicy_path)
        if not data:
            return

        # Get list of available sub-slice IDs
        available_sub_slices = [slice["sub_slice_id"] for slice in data["subSlicePolicy"]["subSlices"]]
        if not available_sub_slices:
            return

        # Get number of uplink slices
        up_slices_count = len(data.get("up_rrmPolicyRatio", []))
        if up_slices_count == 0:
            return

        # Get current Slice_Config value
        slice_config = str(data.get("Slice_Config", "1234"))
        if len(slice_config) >= 4:
            current_target_sub_slice = int(slice_config[-2])
            current_up_target_sub_slice = int(slice_config[-1])
        else:
            current_target_sub_slice = 1
            current_up_target_sub_slice = 1

        # Calculate next target_sub_slice (cycle through available_sub_slices)
        current_index = available_sub_slices.index(current_target_sub_slice) if current_target_sub_slice in available_sub_slices else -1
        next_index = (current_index + 1) % len(available_sub_slices)
        next_target_sub_slice = available_sub_slices[next_index]

        # Calculate next up_target_sub_slice (cycle between 1 and up_slices_count)
        next_up_target_sub_slice = (current_up_target_sub_slice % up_slices_count) + 1

        # Update mapping for last N UEs
        ue_keys = list(data["ueSliceMapping"].keys())
        if len(ue_keys) >= self.last_n_ues:
            for ue_key in ue_keys[-self.last_n_ues:]:
                mapping = data["ueSliceMapping"][ue_key]
                mapping["target_sub_slice"] = next_target_sub_slice
                mapping["up_target_sub_slice"] = next_up_target_sub_slice

        # Update Slice_Config
        slice_config_list = list(slice_config)
        if len(slice_config_list) >= 2:
            slice_config_list[-2] = str(next_target_sub_slice)
            slice_config_list[-1] = str(next_up_target_sub_slice)
            data["Slice_Config"] = int("".join(slice_config_list))

        self.save_json(data, self.rmmpolicy_path)

    def run(self):
        """Run configuration controller"""
        print(f"Slice controller started...")
        print(f"Update interval: {self.update_interval} seconds")
        
        while True:
            try:
                print(f"\nStarting RMMPolicy update - {datetime.now()}")
                self.update_rmmpolicy()
                print(f"Waiting {self.update_interval} seconds for next update...")
                time.sleep(self.update_interval)
            except KeyboardInterrupt:
                print("\nSlice controller terminated")
                break
            except Exception as e:
                print(f"Error occurred: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    controller = RMMPolicyController(
        update_interval=30,
        max_slices=10,
        last_n_ues=1
    )
    controller.run()