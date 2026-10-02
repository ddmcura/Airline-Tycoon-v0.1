"""Desktop window preference, kept separate from touch/mobile layouts."""


def configure_startup_window(window, platform_name):
    if platform_name in {'win', 'linux', 'macosx'}:
        window.fullscreen = False
        window.maximize()
        return True
    return False
