# game/game_modes.py
"""
Game mode system. Each mode is a Python class with hooks that modify
role composition and inject phases into the game flow.
"""

import random
from pathlib import Path
import toml

_CONF_PATH = Path(__file__).parent.parent / "conf" / "game_modes.toml"
MODE_METADATA: dict = toml.load(str(_CONF_PATH))


class GameMode:
    """Base class for game modes."""
    name: str = ""
    min_players: int = 0

    def modify_roles(self, roles: list[str], player_count: int) -> list[str]:
        """Optionally modify the role list before assignment."""
        return roles

    def on_game_start(self, state) -> None:
        """Called after roles are assigned."""
        pass

    def on_mission_end(self, state, mission_number: int) -> str | None:
        """Called after a mission resolves.
        Return a phase name string to inject, or None.
        """
        return None


class LadyOfTheLake(GameMode):
    name = "lady_of_the_lake"
    min_players = 7

    def on_game_start(self, state) -> None:
        # Lady starts with the player to the right of the first leader
        player_ids = list(state.players.keys())
        lady_index = (state.current_leader_index - 1) % len(player_ids)
        state.mode_data["lady_holder"] = player_ids[lady_index]
        state.mode_data["investigated"] = set()

    def on_mission_end(self, state, mission_number: int) -> str | None:
        if mission_number in (2, 3, 4):
            return "investigate"
        return None


class Lancelot(GameMode):
    name = "lancelot"
    min_players = 5

    def modify_roles(self, roles: list[str], player_count: int) -> list[str]:
        """Add Lancelot_Good, Lancelot_Evil, and Guinevere (7+ players).
        Replaces: LoyalServant→Lancelot_Good, generic evil→Lancelot_Evil,
        and (if 7+) another LoyalServant→Guinevere.
        """
        new_roles = list(roles)

        # Replace one LoyalServant with Lancelot_Good
        if "LoyalServant" in new_roles:
            new_roles[new_roles.index("LoyalServant")] = "Lancelot_Good"
        else:
            return new_roles  # can't apply without a LoyalServant

        # Replace one evil with Lancelot_Evil
        # Priority: Minion > Oberon > Morgana > any duplicate evil
        from game.roles import is_evil
        replaced_evil = False
        for evil_target in ("Minion", "Oberon", "Morgana"):
            if evil_target in new_roles:
                new_roles[new_roles.index(evil_target)] = "Lancelot_Evil"
                replaced_evil = True
                break
        if not replaced_evil:
            for i, r in enumerate(new_roles):
                if is_evil(r) and r != "Assassin":
                    new_roles[i] = "Lancelot_Evil"
                    replaced_evil = True
                    break

        # Add Guinevere for 7+ players (replaces another LoyalServant)
        if player_count >= 7 and "LoyalServant" in new_roles:
            new_roles[new_roles.index("LoyalServant")] = "Guinevere"

        return new_roles

    def on_game_start(self, state) -> None:
        # 5 loyalty cards: 2 Switch, 3 No Switch — shuffled
        cards = ["switch", "switch", "no_switch", "no_switch", "no_switch"]
        random.shuffle(cards)
        state.mode_data["loyalty_cards"] = cards
        state.mode_data["loyalty_card_index"] = 0

    def on_mission_end(self, state, mission_number: int) -> str | None:
        if mission_number in (2, 4):
            return "loyalty_switch"
        return None


class Excalibur(GameMode):
    name = "excalibur"
    min_players = 5

    def on_mission_end(self, state, mission_number: int) -> str | None:
        # Excalibur activates BEFORE mission result is revealed
        # This is handled specially in resolve_mission — see game_playflow.py
        return None


# --- Registry ---

MODE_CLASSES: dict[str, type[GameMode]] = {
    "lady_of_the_lake": LadyOfTheLake,
    "lancelot": Lancelot,
    "excalibur": Excalibur,
}


def get_available_modes() -> list[str]:
    return list(MODE_CLASSES.keys())


def get_mode_min_players(mode_name: str) -> int:
    """Return the minimum player count required for the given mode."""
    cls = MODE_CLASSES.get(mode_name)
    if cls is None:
        return 0
    return cls.min_players


def create_mode(mode_name: str) -> GameMode:
    return MODE_CLASSES[mode_name]()
