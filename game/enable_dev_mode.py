import sys
import os

def enable_dev_mode():
    """
    Adds the project root (one level up from this file) to sys.path
    so you can import modules like `from game.something import ...`
    while testing inside `game/`.
    """
    root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
