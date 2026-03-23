# game/roles.py
"""
Role registry — loads role metadata from TOML, provides alignment lookups
and vision computation. Module-level singleton (not stored on pickled objects).
"""

from pathlib import Path
import toml

_CONF_PATH = Path(__file__).parent.parent / "conf" / "roles.toml"
ROLE_REGISTRY: dict[str, dict] = toml.load(str(_CONF_PATH))


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

    elif observer_role == "Percival":
        # Sees Merlin and Morgana (doesn't know which is which)
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if role in ("Merlin", "Morgana") and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "percival_sees"

    elif is_evil(observer_role) and observer_role != "Oberon":
        # Sees fellow evil (except Oberon and self)
        result["sees"] = [uid for uid, role in all_player_roles.items()
                          if is_evil(role) and role != "Oberon" and uid != observer_uid]
        if result["sees"]:
            result["message_key"] = "evil_sees"

    return result
