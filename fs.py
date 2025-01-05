# fs.py
import os
import shutil

def ensure_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def hide_folder(folder_path):
    """On macOS, could rename or chflags hidden. We'll do nothing."""
    pass

def set_hidden_file(file_path, hide=True):
    """Stub."""
    pass

def delete_file(file_path):
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            print(f"Failed to delete {file_path}: {e}")

def delete_folder(folder_path):
    try:
        shutil.rmtree(folder_path)
    except OSError as e:
        print(f"Failed to delete {folder_path}: {e}")
