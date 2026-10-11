import sys

# Remove our explicit development flag before Kivy parses framework arguments.
quarterly_development = '--quarterly-dev' in sys.argv
if quarterly_development:
    sys.argv.remove('--quarterly-dev')

from .app import main


raise SystemExit(main(quarterly_development=quarterly_development))
