"""Compatibility launcher for the modern PH Kivy frontend.

New GUI code lives in app.gui; this historical path never loads legacy state.
"""

from app.gui.app import AirlineTycoonApp, main


if __name__ == '__main__':
    raise SystemExit(main())
