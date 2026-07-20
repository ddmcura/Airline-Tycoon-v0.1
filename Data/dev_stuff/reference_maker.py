# dev_tools/compile_reference.py
import os
import shutil

# 📝 List target folders here. Add more paths if needed.
TARGET_FOLDERS = [
    "game/utils",
    "game/aircraft_market",
    "game/fleet_management",
    "game/hub_management",
    "game/route_management",
    "game/airports",
    "game/scheduling",
    "game/gui"
]

# 📝 List specific files to copy into the output folder
FILES_TO_COPY = [
    "main.py",
    "game/new_game.py",
    "game/game_state.py",
    "game/game_loop.py",
    "game/hub_selector.py"
]

# 📂 Output folder for compiled references
OUTPUT_DIR = "Data/dev_stuff/references"

# 🚫 Folders to exclude from folder tree recursion
EXCLUDED_FOLDERS = {"__pycache__", ".git", ".vscode", ".venv"}
EXCLUDED_FILES = set()

# 📂 Folders to show but skip files inside (for folder tree)
FOLDERS_SKIP_FILES_IN = {
    os.path.normpath("Data/Templates"),
    os.path.normpath("Data/dev_stuff"),
    os.path.normpath("Saves")
}

def compile_folder(folder_path):
    folder_name = os.path.basename(folder_path)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, f"{folder_name}_reference.txt")

    py_files = [f for f in os.listdir(folder_path) if f.endswith(".py") and f != "__init__.py"]
    py_files.sort()

    if not py_files:
        print(f"⚠️ No Python files in '{folder_path}', skipping...")
        return

    with open(output_file, "w", encoding="utf-8") as out:
        # Header
        out.write("# ===============================================\n")
        out.write(f"# 🛫 Airline Tycoon - {folder_name.title()} Bundle\n")
        out.write("# ===============================================\n")
        out.write(f"# This file contains all modules for:\n")
        out.write(f"# 📂 {folder_path}/\n#\n")
        out.write("# Included Modules:\n")
        for f in py_files:
            out.write(f"# - {f}\n")
        out.write("# ===============================================\n\n")

        # Each file’s content
        for file in py_files:
            file_path = os.path.join(folder_path, file)
            out.write("# ================================\n")
            out.write(f"# {folder_path}/{file} starts here\n")
            out.write("# ================================\n\n")
            with open(file_path, "r", encoding="utf-8") as src:
                out.write(src.read())
                out.write("\n\n")

    print(f"✅ Updated: {output_file}")

def copy_files_to_output():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("\n📂 Copying specified files to output folder...")
    for path in FILES_TO_COPY:
        if os.path.isfile(path):
            filename = os.path.basename(path)
            target_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(target_path):
                os.remove(target_path)  # Ensure overwrite
            shutil.copy2(path, target_path)
            print(f"✅ Copied file (overwritten if existed): {filename}")
        else:
            print(f"❌ File not found: {path}")

def generate_folder_tree(start_path='.', indent=''):
    tree_lines = []

    try:
        items = sorted(os.listdir(start_path))
        items = [item for item in items if item not in EXCLUDED_FOLDERS and item not in EXCLUDED_FILES]
    except PermissionError:
        return []

    for index, item in enumerate(items):
        path = os.path.join(start_path, item)
        is_last = (index == len(items) - 1)
        branch = '└── ' if is_last else '├── '
        tree_lines.append(indent + branch + item)

        if os.path.isdir(path):
            if os.path.normpath(path) not in FOLDERS_SKIP_FILES_IN:
                extension = '    ' if is_last else '│   '
                tree_lines.extend(generate_folder_tree(path, indent + extension))

    return tree_lines

def save_folder_tree():
    tree_output = os.path.join(OUTPUT_DIR, 'foldertree.txt')
    tree = generate_folder_tree()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(tree_output, 'w', encoding="utf-8") as f:
        f.write("📁 Folder Tree (Selective File Skip):\n\n")
        f.write('\n'.join(tree))
    print(f"💾 Folder tree saved to: {tree_output}")

def compile_all():
    print("🛠 Airline Tycoon Batch Reference Compiler")
    print("=" * 50)

    folders = TARGET_FOLDERS
    if not folders:
        # Auto-detect all folders in 'game/'
        game_dir = "game"
        folders = [
            os.path.join(game_dir, d)
            for d in os.listdir(game_dir)
            if os.path.isdir(os.path.join(game_dir, d))
        ]

    for folder in folders:
        if os.path.exists(folder):
            compile_folder(folder)
        else:
            print(f"❌ Folder '{folder}' does not exist. Skipping...")

    copy_files_to_output()
    save_folder_tree()
    print(f"\n🎉 Batch compilation complete. All references and files saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    compile_all()
