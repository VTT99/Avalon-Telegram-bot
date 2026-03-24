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

    def on_mission_end(self, state, mission_number: int) -> str | None:
        # Excalibur activates BEFORE mission result is revealed
        # This is handled specially in resolve_mission — see game_playflow.py
        return None


# --- Plot card definitions ---

# Each card has a unique id, a type ("usable", "instant", or "effect"),
# and a translation key prefix used to look up messages.

PLOT_CARD_DEFS: list[dict] = [
    # Usable cards — holder keeps them and may play during their turn
    {"id": "lead_to_victory",     "type": "usable",  "key": "plot_lead_to_victory"},
    {"id": "ambush",              "type": "usable",  "key": "plot_ambush"},
    {"id": "king_returns",        "type": "usable",  "key": "plot_king_returns"},
    {"id": "we_found_you",        "type": "usable",  "key": "plot_we_found_you"},
    # Instant cards — take effect immediately when drawn
    {"id": "restore_your_honor",  "type": "instant", "key": "plot_restore_your_honor"},
    {"id": "show_your_strength",  "type": "instant", "key": "plot_show_your_strength"},
    {"id": "show_your_true_nature", "type": "instant", "key": "plot_show_your_true_nature"},
    {"id": "are_you_the_one",     "type": "instant", "key": "plot_are_you_the_one"},
    # Effect cards — passive effects that modify the next round
    {"id": "charge",              "type": "effect",  "key": "plot_charge"},
]

def _get_card_def(card_id: str) -> dict | None:
    for c in PLOT_CARD_DEFS:
        if c["id"] == card_id:
            return c
    return None


def _build_plot_deck(player_count: int) -> list[str]:
    """Build and shuffle a plot card deck appropriate for the player count."""
    # Small games get a 7-card deck, larger games get 15 cards
    if player_count <= 6:
        deck_size = 7
    else:
        deck_size = 15

    # Build the pool by cycling through all card ids
    all_ids = [c["id"] for c in PLOT_CARD_DEFS]
    deck = []
    idx = 0
    while len(deck) < deck_size:
        deck.append(all_ids[idx % len(all_ids)])
        idx += 1
    random.shuffle(deck)
    return deck


class PlotCards(GameMode):
    name = "plot_cards"

    def on_game_start(self, state) -> None:
        pc = len(state.players)
        state.mode_data["plot_deck"] = _build_plot_deck(pc)
        state.mode_data["plot_deck_index"] = 0
        # How many cards the leader distributes each round
        if pc <= 6:
            state.mode_data["plot_cards_per_round"] = 1
        elif pc <= 8:
            state.mode_data["plot_cards_per_round"] = 2
        else:
            state.mode_data["plot_cards_per_round"] = 3
        # Cards currently held by players: {user_id: [card_id, ...]}
        state.mode_data["plot_hands"] = {}
        # Flag: if Charge! is active, next team vote is public
        state.mode_data["plot_public_vote"] = False

    def on_mission_end(self, state, mission_number: int) -> str | None:
        deck = state.mode_data.get("plot_deck", [])
        deck_idx = state.mode_data.get("plot_deck_index", 0)
        if deck_idx < len(deck):
            return "plot_card_distribution"
        return None


# --- Registry ---

MODE_CLASSES: dict[str, type[GameMode]] = {
    "lady_of_the_lake": LadyOfTheLake,
    "lancelot": Lancelot,
    "excalibur": Excalibur,
    "plot_cards": PlotCards,
}


def get_available_modes() -> list[str]:
    return list(MODE_CLASSES.keys())


def create_mode(mode_name: str) -> GameMode:
    return MODE_CLASSES[mode_name]()
