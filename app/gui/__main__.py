import sys

# Remove our explicit development flag before Kivy parses framework arguments.
quarterly_development = '--quarterly-dev' in sys.argv
if quarterly_development:
    sys.argv.remove('--quarterly-dev')
closed_owner = '--closed-owner' in sys.argv
if closed_owner:
    sys.argv.remove('--closed-owner')
scoped_completion = '--scoped-completion' in sys.argv
if scoped_completion:
    sys.argv.remove('--scoped-completion')

from .app import main


raise SystemExit(main(quarterly_development=quarterly_development, closed_owner=closed_owner,
                     scoped_completion=scoped_completion))
