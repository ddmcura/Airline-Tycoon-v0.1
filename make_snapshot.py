import os
import zipfile
from datetime import datetime

# 🛑 Folders and files to exclude from the snapshot
SKIP_FOLDERS = [
    'Saves',
    '__pycache__',
    '.git',
    'Snapshots',  # don’t snapshot snapshots
    'dev_stuff'   # optional: skip your dev folder
]

SKIP_FILES = [
    '.DS_Store',
    '*.pyc',
    '*.pyo'
]

def should_skip(path):
    """Determine if a path should be skipped."""
    for skip_folder in SKIP_FOLDERS:
        if skip_folder in path.split(os.sep):
            return True
    filename = os.path.basename(path)
    for pattern in SKIP_FILES:
        if pattern.startswith('*.') and filename.endswith(pattern[1:]):
            return True
        if filename == pattern:
            return True
    return False

def make_snapshot(base_dir):
    """Create a snapshot zip from the given base directory."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    snapshot_dir = os.path.join(base_dir, 'Snapshots')
    os.makedirs(snapshot_dir, exist_ok=True)

    zip_filename = f'AirlineTycoon_{timestamp}.zip'
    zip_path = os.path.join(snapshot_dir, zip_filename)

    print(f'📦 Creating snapshot: {zip_path}')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(base_dir):
            if should_skip(foldername):
                continue
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                if should_skip(file_path):
                    continue
                rel_path = os.path.relpath(file_path, base_dir)
                zipf.write(file_path, rel_path)
                print(f'✅ Added: {rel_path}')
    print(f'🎉 Snapshot complete → {zip_filename}')

if __name__ == '__main__':
    here = os.path.abspath(os.getcwd())
    print(f"📂 Current folder: {here}")
    print("📌 This will snapshot *everything* in this folder.")
    confirm = input("Continue? (y/n): ").strip().lower()
    if confirm == 'y':
        make_snapshot(here)
    else:
        print("❌ Snapshot canceled.")
