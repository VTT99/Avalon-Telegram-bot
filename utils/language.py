from conf.game_setting import CONFIG
import os
import toml
LANG_PATH = "languages"
DEFAULT_LANG = CONFIG["default_language"]

def get_user_language(user_data) -> str:
    return user_data.get("lang", DEFAULT_LANG)

def set_user_language(user_data, lang_code: str):
    user_data["lang"] = lang_code


def load_toml(lang: str, file: str) -> dict:
    path = os.path.join(LANG_PATH, lang, f"{file}.toml")
    if os.path.exists(path):
        return toml.load(path)
    # fallback to default language
    fallback = os.path.join(LANG_PATH, DEFAULT_LANG, f"{file}.toml")
    return toml.load(fallback) if os.path.exists(fallback) else {}

def get_message(key: str, context=None, lang: str = None, **kwargs) -> str:
    if lang is None:
        lang = get_user_language(context.user_data) if context else DEFAULT_LANG
    messages = load_toml(lang, "message")
    msg = messages.get(key) or load_toml(DEFAULT_LANG, "message").get(key, f"[{key}]")
    return msg.format(**kwargs)

def get_button_text(key: str, context=None, lang: str = None) -> str:
    if lang is None:
        lang = get_user_language(context.user_data) if context else DEFAULT_LANG
    buttons = load_toml(lang, "button")
    return buttons.get(key) or load_toml(DEFAULT_LANG, "button").get(key, f"[{key}]")
