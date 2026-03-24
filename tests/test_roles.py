# tests/test_roles.py
"""Tests for game/roles.py — alignment lookups and vision mechanics."""

import pytest
from game.roles import (
    ROLE_REGISTRY,
    get_alignment,
    is_evil,
    is_good,
    evil_role_names,
    good_role_names,
    get_vision,
)

# ---------------------------------------------------------------------------
# Alignment helpers
# ---------------------------------------------------------------------------

EVIL_ROLES = {"Assassin", "Mordred", "Morgana", "Oberon", "Minion", "Lancelot_Evil"}
GOOD_ROLES = {"Merlin", "Percival", "LoyalServant", "Guinevere", "Lancelot_Good"}


class TestAlignment:
    def test_evil_roles_are_evil(self):
        for role in EVIL_ROLES:
            assert is_evil(role), f"{role} should be evil"

    def test_good_roles_are_good(self):
        for role in GOOD_ROLES:
            assert is_good(role), f"{role} should be good"

    def test_evil_roles_are_not_good(self):
        for role in EVIL_ROLES:
            assert not is_good(role), f"{role} should not be good"

    def test_good_roles_are_not_evil(self):
        for role in GOOD_ROLES:
            assert not is_evil(role), f"{role} should not be evil"

    def test_unknown_role_defaults_to_good(self):
        assert is_good("UnknownRole")
        assert not is_evil("UnknownRole")

    def test_get_alignment_evil(self):
        for role in EVIL_ROLES:
            assert get_alignment(role) == "evil"

    def test_get_alignment_good(self):
        for role in GOOD_ROLES:
            assert get_alignment(role) == "good"

    def test_evil_role_names_set(self):
        result = evil_role_names()
        assert isinstance(result, set)
        assert result == EVIL_ROLES

    def test_good_role_names_set(self):
        result = good_role_names()
        assert isinstance(result, set)
        assert result == GOOD_ROLES

    def test_all_registry_roles_have_alignment(self):
        for role_name, cfg in ROLE_REGISTRY.items():
            assert "alignment" in cfg, f"{role_name} missing alignment"
            assert cfg["alignment"] in ("good", "evil")


# ---------------------------------------------------------------------------
# Vision mechanics
# ---------------------------------------------------------------------------

# A simple 5-player role assignment used in many vision tests
# UIDs: 1=Merlin, 2=Percival, 3=LoyalServant, 4=Assassin, 5=Morgana
FIVE_PLAYER_ROLES: dict[int, str] = {
    1: "Merlin",
    2: "Percival",
    3: "LoyalServant",
    4: "Assassin",
    5: "Morgana",
}


class TestMerlinVision:
    def test_merlin_sees_evil_players(self):
        result = get_vision("Merlin", FIVE_PLAYER_ROLES, observer_uid=1)
        # Merlin should see Assassin (4) and Morgana (5), not Mordred
        assert set(result["sees"]) == {4, 5}

    def test_merlin_does_not_see_mordred(self):
        roles = {1: "Merlin", 2: "Mordred", 3: "Assassin"}
        result = get_vision("Merlin", roles, observer_uid=1)
        assert 2 not in result["sees"]
        assert 3 in result["sees"]

    def test_merlin_does_not_see_self(self):
        result = get_vision("Merlin", FIVE_PLAYER_ROLES, observer_uid=1)
        assert 1 not in result["sees"]

    def test_merlin_message_key(self):
        result = get_vision("Merlin", FIVE_PLAYER_ROLES, observer_uid=1)
        assert result["message_key"] == "merlin_sees"

    def test_merlin_no_message_key_when_no_evil(self):
        roles = {1: "Merlin", 2: "LoyalServant"}
        result = get_vision("Merlin", roles, observer_uid=1)
        assert result["sees"] == []
        assert result["message_key"] is None


class TestPercivalVision:
    def test_percival_sees_merlin_and_morgana(self):
        result = get_vision("Percival", FIVE_PLAYER_ROLES, observer_uid=2)
        assert set(result["sees"]) == {1, 5}  # Merlin=1, Morgana=5

    def test_percival_does_not_see_self(self):
        roles = {1: "Percival", 2: "Merlin", 3: "Morgana"}
        result = get_vision("Percival", roles, observer_uid=1)
        assert 1 not in result["sees"]

    def test_percival_message_key(self):
        result = get_vision("Percival", FIVE_PLAYER_ROLES, observer_uid=2)
        assert result["message_key"] == "percival_sees"

    def test_percival_without_morgana(self):
        roles = {1: "Percival", 2: "Merlin", 3: "Assassin"}
        result = get_vision("Percival", roles, observer_uid=1)
        assert 2 in result["sees"]
        assert 3 not in result["sees"]


class TestGuenevereVision:
    def test_guinevere_sees_both_lancelots(self):
        roles = {
            1: "Guinevere",
            2: "Lancelot_Good",
            3: "Lancelot_Evil",
            4: "Merlin",
        }
        result = get_vision("Guinevere", roles, observer_uid=1)
        assert set(result["sees"]) == {2, 3}

    def test_guinevere_does_not_see_self(self):
        roles = {1: "Guinevere", 2: "Lancelot_Good"}
        result = get_vision("Guinevere", roles, observer_uid=1)
        assert 1 not in result["sees"]

    def test_guinevere_message_key(self):
        roles = {1: "Guinevere", 2: "Lancelot_Good", 3: "Lancelot_Evil"}
        result = get_vision("Guinevere", roles, observer_uid=1)
        assert result["message_key"] == "guinevere_sees"


class TestEvilVision:
    def test_assassin_sees_fellow_evil(self):
        roles = {1: "Assassin", 2: "Morgana", 3: "Merlin"}
        result = get_vision("Assassin", roles, observer_uid=1)
        assert 2 in result["sees"]
        assert 3 not in result["sees"]

    def test_evil_does_not_see_oberon(self):
        roles = {1: "Assassin", 2: "Oberon", 3: "Morgana"}
        result = get_vision("Assassin", roles, observer_uid=1)
        assert 2 not in result["sees"]  # Oberon hidden from evil
        assert 3 in result["sees"]

    def test_evil_does_not_see_self(self):
        roles = {1: "Assassin", 2: "Morgana"}
        result = get_vision("Assassin", roles, observer_uid=1)
        assert 1 not in result["sees"]

    def test_evil_message_key(self):
        roles = {1: "Assassin", 2: "Morgana"}
        result = get_vision("Assassin", roles, observer_uid=1)
        assert result["message_key"] == "evil_sees"

    def test_oberon_sees_nothing(self):
        roles = {1: "Oberon", 2: "Assassin", 3: "Merlin"}
        result = get_vision("Oberon", roles, observer_uid=1)
        assert result["sees"] == []
        assert result["message_key"] is None


class TestNoVision:
    def test_loyal_servant_sees_nothing(self):
        result = get_vision("LoyalServant", FIVE_PLAYER_ROLES, observer_uid=3)
        assert result["sees"] == []
        assert result["message_key"] is None

    def test_mordred_sees_other_evil(self):
        roles = {1: "Mordred", 2: "Assassin", 3: "Merlin"}
        result = get_vision("Mordred", roles, observer_uid=1)
        assert 2 in result["sees"]

    def test_lancelot_evil_sees_other_evil(self):
        roles = {1: "Lancelot_Evil", 2: "Assassin", 3: "Merlin"}
        result = get_vision("Lancelot_Evil", roles, observer_uid=1)
        assert 2 in result["sees"]
