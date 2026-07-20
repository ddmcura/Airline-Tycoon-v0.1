"""USD accounting with configurable display-currency conversion."""

BASE_CURRENCY = "USD"
DEFAULT_DISPLAY_CURRENCY = "USD"
EXCHANGE_RATES = {
    "USD": 1.00,
    "PHP": 58.00,
    "EUR": 0.86,
    "GBP": 0.75,
    "JPY": 158.00,
}
CURRENCY_SYMBOLS = {
    "USD": "$",
    "PHP": "P",
    "EUR": "EUR ",
    "GBP": "GBP ",
    "JPY": "JPY ",
}


def available_currencies():
    return tuple(EXCHANGE_RATES)


def get_display_currency(game_state):
    return game_state.get("settings", {}).get(
        "display_currency", DEFAULT_DISPLAY_CURRENCY
    )


def set_display_currency(game_state, currency_code):
    currency_code = currency_code.upper()
    if currency_code not in EXCHANGE_RATES:
        raise ValueError(f"Unsupported currency: {currency_code}")
    settings = game_state.setdefault("settings", {})
    settings["base_currency"] = BASE_CURRENCY
    settings["display_currency"] = currency_code


def convert_from_usd(game_state, amount):
    currency = get_display_currency(game_state)
    rates = game_state.get("settings", {}).get("exchange_rates", {})
    rate = float(rates.get(currency, EXCHANGE_RATES.get(currency, 1.0)))
    return float(amount) * rate


def format_money(game_state, amount, decimals=2):
    currency = get_display_currency(game_state)
    converted = convert_from_usd(game_state, amount)
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{converted:,.{decimals}f}"
