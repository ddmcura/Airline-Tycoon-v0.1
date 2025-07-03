def country_flag(code):
    if not code or len(code) != 2 or not code.isalpha():
        return "🏳️"  # fallback flag
    return ''.join(chr(127397 + ord(char.upper())) for char in code)