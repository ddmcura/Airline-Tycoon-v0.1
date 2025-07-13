import os

EXCLUDED_FOLDERS = {"__pycache__", ".git", ".vscode"}
EXCLUDED_FILES = set()

def generate_folder_tree(start_path='.', indent=''):
    tree_lines = []
    try:
        items = sorted(os.listdir(start_path))
        items = [item for item in items if item not in EXCLUDED_FOLDERS and item not in EXCLUDED_FILES]
    except PermissionError:
        return []  # skip folders you can't access

    for index, item in enumerate(items):
        path = os.path.join(start_path, item)
        is_last = (index == len(items) - 1)
        branch = '└── ' if is_last else '├── '
        tree_lines.append(indent + branch + item)
        if os.path.isdir(path):
            extension = '    ' if is_last else '│   '
            tree_lines.extend(generate_folder_tree(path, indent + extension))
    return tree_lines

def save_folder_tree_to_file(start_path='.', output_file='Data/Templates/foldertree.txt'):
    tree = generate_folder_tree(start_path)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("📁 Folder Tree:\n\n")
        f.write('\n'.join(tree))
    print(f"\n💾 Folder tree saved to: {output_file}\n")

if __name__ == "__main__":
    save_folder_tree_to_file('.')
