# tests/test_game_modes.py
"""Tests for game/game_modes.py — modify_roles, on_mission_end, on_game_start."""

import pytest
from unittest.mock import MagicMock
from game.game_modes import (
    LadyOfTheLake,
    Lancelot,
    Excalibur,
    create_mode,
    get_available_modes,
    MODE_CLASSES,
)


# ---------------------------------------------------------------------------
# Helper: minimal State stub
# ---------------------------------------------------------------------------

def make_state_stub(player_count: int = 5, leader_index: int = 0) -> MagicMock:
    """Return a MagicMock that looks enough like game_state.State for mode hooks."""
    state = MagicMock()
    player_ids = list(range(1, player_count + 1))
    state.players = {pid: f"Player{pid}" for pid in player_ids}
    state.current_leader_index = leader_index
    state.mode_data = {}
    return state


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_get_available_modes_returns_all_modes(self):
        modes = get_available_modes()
        assert set(modes) == {"lady_of_the_lake", "lancelot", "excalibur"}

    def test_create_mode_lady_of_the_lake(self):
        mode = create_mode("lady_of_the_lake")
        assert isinstance(mode, LadyOfTheLake)

    def test_create_mode_lancelot(self):
        mode = create_mode("lancelot")
        assert isinstance(mode, Lancelot)

    def test_create_mode_excalibur(self):
        mode = create_mode("excalibur")
        assert isinstance(mode, Excalibur)

    def test_create_mode_unknown_raises(self):
        with pytest.raises(KeyError):
            create_mode("unknown_mode")

    def test_mode_classes_keys_match_available(self):
        assert set(MODE_CLASSES.keys()) == set(get_available_modes())


# ---------------------------------------------------------------------------
# LadyOfTheLake
# ---------------------------------------------------------------------------

class TestLadyOfTheLake:
    def test_modify_roles_returns_roles_unchanged(self):
        mode = LadyOfTheLake()
        roles = ["Merlin", "LoyalServant", "Assassin"]
        assert mode.modify_roles(roles, player_count=3) == roles

    def test_on_game_start_sets_lady_holder(self):
        mode = LadyOfTheLake()
        state = make_state_stub(player_count=5, leader_index=0)
        mode.on_game_start(state)
        assert "lady_holder" in state.mode_data

    def test_on_game_start_lady_holder_is_valid_player(self):
        mode = LadyOfTheLake()
        state = make_state_stub(player_count=5, leader_index=2)
        mode.on_game_start(state)
        assert state.mode_data["lady_holder"] in state.players

    def test_on_game_start_lady_holder_is_right_of_leader(self):
        """Lady starts with the player to the right (index - 1 mod n) of the leader."""
        mode = LadyOfTheLake()
        for player_count in range(5, 11):
            for leader_index in range(player_count):
                state = make_state_stub(player_count=player_count, leader_index=leader_index)
                mode.on_game_start(state)
                player_ids = list(state.players.keys())
                expected_lady_index = (leader_index - 1) % player_count
                expected_holder = player_ids[expected_lady_index]
                assert state.mode_data["lady_holder"] == expected_holder

    def test_on_game_start_initialises_investigated_set(self):
        mode = LadyOfTheLake()
        state = make_state_stub()
        mode.on_game_start(state)
        assert "investigated" in state.mode_data
        assert state.mode_data["investigated"] == set()

    def test_on_mission_end_returns_investigate_on_missions_2_3_4(self):
        mode = LadyOfTheLake()
        state = make_state_stub()
        for mission in (2, 3, 4):
            assert mode.on_mission_end(state, mission) == "investigate"

    def test_on_mission_end_returns_none_on_missions_1_5(self):
        mode = LadyOfTheLake()
        state = make_state_stub()
        for mission in (1, 5):
            assert mode.on_mission_end(state, mission) is None


# ---------------------------------------------------------------------------
# Lancelot
# ---------------------------------------------------------------------------

class TestLancelot:
    # --- modify_roles ---

    def test_modify_roles_replaces_loyal_servant_with_lancelot_good(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Lancelot_Good" in result
        # One fewer LoyalServant
        assert result.count("LoyalServant") == roles.count("LoyalServant") - 1

    def test_modify_roles_replaces_evil_with_lancelot_evil(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Lancelot_Evil" in result

    def test_modify_roles_5_players_no_guinevere(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Guinevere" not in result

    def test_modify_roles_7_players_adds_guinevere(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant",
                 "Assassin", "Morgana", "Oberon"]
        result = mode.modify_roles(roles, player_count=7)
        assert "Guinevere" in result

    def test_modify_roles_prefers_minion_as_lancelot_evil(self):
        mode = Lancelot()
        roles = ["Merlin", "LoyalServant", "Assassin", "Minion", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        # Minion should become Lancelot_Evil (highest priority)
        assert "Lancelot_Evil" in result
        assert "Minion" not in result

    def test_modify_roles_uses_oberon_when_no_minion(self):
        mode = Lancelot()
        roles = ["Merlin", "LoyalServant", "Assassin", "Oberon", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Lancelot_Evil" in result
        assert "Oberon" not in result

    def test_modify_roles_uses_morgana_when_no_minion_or_oberon(self):
        mode = Lancelot()
        roles = ["Merlin", "LoyalServant", "Assassin", "Morgana", "Mordred"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Lancelot_Evil" in result
        assert "Morgana" not in result

    def test_modify_roles_fallback_replaces_non_assassin_evil(self):
        """When Minion/Oberon/Morgana are absent, any non-Assassin evil is replaced."""
        mode = Lancelot()
        roles = ["Merlin", "LoyalServant", "Assassin", "Mordred", "LoyalServant"]
        result = mode.modify_roles(roles, player_count=5)
        assert "Lancelot_Evil" in result
        assert "Mordred" not in result

    def test_modify_roles_without_loyal_servant_returns_unchanged(self):
        """If no LoyalServant exists, the mode cannot apply — return unchanged."""
        mode = Lancelot()
        roles = ["Merlin", "Percival", "Percival", "Assassin", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert result == roles

    def test_modify_roles_preserves_role_count(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        result = mode.modify_roles(roles, player_count=5)
        assert len(result) == len(roles)

    def test_modify_roles_7_preserves_role_count(self):
        mode = Lancelot()
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant",
                 "Assassin", "Morgana", "Oberon"]
        result = mode.modify_roles(roles, player_count=7)
        assert len(result) == len(roles)

    # --- on_game_start ---

    def test_on_game_start_sets_loyalty_cards(self):
        mode = Lancelot()
        state = make_state_stub()
        mode.on_game_start(state)
        assert "loyalty_cards" in state.mode_data

    def test_on_game_start_loyalty_cards_count(self):
        mode = Lancelot()
        state = make_state_stub()
        mode.on_game_start(state)
        assert len(state.mode_data["loyalty_cards"]) == 5

    def test_on_game_start_loyalty_cards_composition(self):
        mode = Lancelot()
        state = make_state_stub()
        mode.on_game_start(state)
        cards = state.mode_data["loyalty_cards"]
        assert cards.count("switch") == 2
        assert cards.count("no_switch") == 3

    def test_on_game_start_sets_card_index_to_zero(self):
        mode = Lancelot()
        state = make_state_stub()
        mode.on_game_start(state)
        assert state.mode_data["loyalty_card_index"] == 0

    # --- on_mission_end ---

    def test_on_mission_end_returns_loyalty_switch_on_missions_2_4(self):
        mode = Lancelot()
        state = make_state_stub()
        for mission in (2, 4):
            assert mode.on_mission_end(state, mission) == "loyalty_switch"

    def test_on_mission_end_returns_none_on_missions_1_3_5(self):
        mode = Lancelot()
        state = make_state_stub()
        for mission in (1, 3, 5):
            assert mode.on_mission_end(state, mission) is None


# ---------------------------------------------------------------------------
# Excalibur
# ---------------------------------------------------------------------------

class TestExcalibur:
    def test_modify_roles_returns_roles_unchanged(self):
        mode = Excalibur()
        roles = ["Merlin", "LoyalServant", "Assassin"]
        assert mode.modify_roles(roles, player_count=3) == roles

    def test_on_mission_end_always_returns_none(self):
        mode = Excalibur()
        state = make_state_stub()
        for mission in range(1, 6):
            assert mode.on_mission_end(state, mission) is None

    def test_on_game_start_does_not_raise(self):
        mode = Excalibur()
        state = make_state_stub()
        mode.on_game_start(state)  # base class no-op — should not raise


# ---------------------------------------------------------------------------
# Base GameMode (via Excalibur which doesn't override)
# ---------------------------------------------------------------------------

class TestGameModeBase:
    def test_base_modify_roles_is_identity(self):
        mode = Excalibur()
        roles = ["Merlin", "Assassin"]
        assert mode.modify_roles(roles, player_count=2) == roles

    def test_all_modes_have_name_attribute(self):
        for mode_cls in MODE_CLASSES.values():
            instance = mode_cls()
            assert hasattr(instance, "name")
            assert instance.name != ""
