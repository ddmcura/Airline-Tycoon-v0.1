# dev_tools/compile_reference.py
import os

# 📝 List target folders here. Add more paths if needed.
TARGET_FOLDERS = [
    "game/utils",
    "game/aircraft_market",
    "game/fleet_management",
    "game/hub_management",
    "game/route_management"
]

# 📂 Output folder for compiled references
OUTPUT_DIR = "Data/dev_stuff/references"


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

    print(f"✅ Updated: {output_file}")  # 🔄 Updated label


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

    print(f"\n🎉 Batch compilation complete. References saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    compile_all()
