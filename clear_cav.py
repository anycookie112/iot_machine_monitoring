import shutil
import os

def clear_pycache(directory):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                full_path = os.path.join(root, dir_name)
                print(f"Deleting: {full_path}")
                shutil.rmtree(full_path)

clear_pycache(".")  # Run from the root of your project
