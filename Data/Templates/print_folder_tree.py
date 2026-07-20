import os

EXCLUDED_FOLDERS = {"__pycache__", ".git", ".vscode"}
EXCLUDED_FILES = set()

# Folders to show but skip files inside
FOLDERS_SKIP_FILES_IN = {
    os.path.normpath("Data/Templates"),
    os.path.normpath("Data/dev_stuff"),
    os.path.normpath("Saves")
}

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

        # Only recurse if it's a directory and NOT in the skip set
        if os.path.isdir(path):
            if os.path.normpath(path) not in FOLDERS_SKIP_FILES_IN:
                extension = '    ' if is_last else '│   '
                tree_lines.extend(generate_folder_tree(path, indent + extension))

    return tree_lines

def save_folder_tree_to_file(start_path='.', output_file='Data/Templates/foldertree.txt'):
    tree = generate_folder_tree(start_path)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("📁 Folder Tree (Selective File Skip):\n\n")
        f.write('\n'.join(tree))
    print(f"\n💾 Folder tree saved to: {output_file}\n")

if __name__ == "__main__":
    save_folder_tree_to_file('.')
