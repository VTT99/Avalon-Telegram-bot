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

    def modify_roles(self, roles: list[str], player_count: int) -> list[str]:
        """Replace one LoyalServant with Lancelot_Good and one Minion with Lancelot_Evil."""
        new_roles = list(roles)
        if "LoyalServant" in new_roles and "Minion" in new_roles:
            new_roles[new_roles.index("LoyalServant")] = "Lancelot_Good"
            new_roles[new_roles.index("Minion")] = "Lancelot_Evil"
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


def create_mode(mode_name: str) -> GameMode:
    return MODE_CLASSES[mode_name]()
