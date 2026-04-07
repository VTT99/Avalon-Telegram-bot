# game/roles.py
"""
Role registry — loads role metadata from TOML, provides alignment lookups
and vision computation. Module-level singleton (not stored on pickled objects).
"""

from pathlib import Path
import toml

_CONF_PATH = Path(__file__).parent.parent / "conf" / "roles.toml"
ROLE_REGISTRY: dict[str, dict] = toml.load(str(_CONF_PATH))


def get_role_display_name(role_name: str, lang: str = None) -> str:
    """Get translated role name. Falls back to the internal name."""
    from utils.language import get_message
    translated = get_message(f"role_name_{role_name}", lang=lang)
    # If key not found, get_message returns "[role_name_X]" — fall back to raw name
    if translated.startswith("["):
        return role_name
    return translated


def get_alignment(role_name: str) -> str:
    entry = ROLE_REGISTRY.get(role_name)
    if entry:
        return entry["alignment"]
    return "good"  # fallback for unknown roles


def is_evil(role_name: str) -> bool:
    return get_alignment(role_name) == "evil"


def is_good(role_name: str) -> bool:
    return get_alignment(role_name) == "good"


def evil_role_names() -> set[str]:
    return {name for name, cfg in ROLE_REGISTRY.items() if cfg["alignment"] == "evil"}


def good_role_names() -> set[str]:
    return {name for name, cfg in ROLE_REGISTRY.items() if cfg["alignment"] == "good"}


def get_vision(observer_role: str, all_player_roles: dict[int, str], observer_uid: int) -> dict:
    """
    Compute what an observer sees given all player-role assignments.

    Returns:
        {
            "sees": [uid, ...],          # player IDs visible to this observer
            "message_key": str | None,   # i18n key for the vision description
        }
    """
    result = {"sees": [], "message_key": None}

    if observer_role == "Merlin":
        # Sees all evil except Mordred
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if is_evil(role) and role != "Mordred" and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "merlin_sees"

    elif observer_role == "MerlinPure":
        # Sees ALL evil players including Mordred and Oberon
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if is_evil(role) and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "merlin_pure_sees"

    elif observer_role == "Percival":
        # Sees Merlin/MerlinPure and Morgana (doesn't know which is which)
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if role in ("Merlin", "MerlinPure", "Morgana") and uid != observer_uid]
        if result["sees"]:
            has_merlin_pure = any(all_player_roles.get(uid) == "MerlinPure" for uid in result["sees"])
            result["message_key"] = "percival_sees_pure" if has_merlin_pure else "percival_sees"

    elif observer_role == "Guinevere":
        # Sees both Lancelots (doesn't know which is good/evil)
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if role in ("Lancelot_Good", "Lancelot_Evil") and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "guinevere_sees"

    elif is_evil(observer_role) and observer_role != "Oberon":
        # Sees fellow evil (except Oberon and self)
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if is_evil(role) and role != "Oberon" and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "evil_sees"

    return result
