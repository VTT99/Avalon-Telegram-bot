# tests/test_game_state.py
"""Tests for game/game_state.py — mission logic, vote logic, role assignment."""

import pytest
from unittest.mock import patch
from game.game_state import State


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_state(player_count: int = 5, roles: list[str] = None,
               people_per_mission: list[int] = None,
               fails_required: list[int] = None) -> State:
    """Create a State with sequential player IDs and the given role list."""
    players = {i + 1: f"Player{i + 1}" for i in range(player_count)}
    if roles is None:
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
    if people_per_mission is None:
        people_per_mission = [2, 3, 2, 3, 3]
    return State(players, roles, people_per_mission, fails_required)


# ---------------------------------------------------------------------------
# Role assignment
# ---------------------------------------------------------------------------

class TestRoleAssignment:
    def test_every_player_gets_a_role(self):
        state = make_state(5)
        assert len(state.player_roles) == 5

    def test_all_roles_assigned(self):
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        state = make_state(5, roles=roles)
        assert sorted(state.player_roles.values()) == sorted(roles)

    def test_roles_assigned_to_correct_player_ids(self):
        state = make_state(5)
        assert set(state.player_roles.keys()) == set(state.players.keys())

    def test_six_player_role_assignment(self):
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant", "Assassin", "Morgana"]
        state = make_state(6, roles=roles)
        assert len(state.player_roles) == 6
        assert sorted(state.player_roles.values()) == sorted(roles)

    def test_seven_player_role_assignment(self):
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant", "Assassin", "Morgana", "Oberon"]
        state = make_state(7, roles=roles)
        assert len(state.player_roles) == 7

    def test_get_role_returns_assigned_role(self):
        state = make_state(5)
        for uid in state.players:
            assert state.get_role(uid) == state.player_roles[uid]

    def test_get_role_unknown_player(self):
        state = make_state(5)
        assert state.get_role(9999) == "Unknown"

    def test_good_evil_counts_5_players(self):
        roles = ["Merlin", "Percival", "LoyalServant", "Assassin", "Morgana"]
        state = make_state(5, roles=roles)
        evil = state.get_evil_players()
        good = state.get_good_players()
        assert len(evil) == 2
        assert len(good) == 3

    def test_good_evil_counts_7_players(self):
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant",
                 "Assassin", "Morgana", "Oberon"]
        state = make_state(7, roles=roles)
        assert len(state.get_evil_players()) == 3
        assert len(state.get_good_players()) == 4


# ---------------------------------------------------------------------------
# Mission success determination
# ---------------------------------------------------------------------------

class TestMissionSuccess:
    def test_zero_fails_succeeds(self):
        state = make_state()
        # mission_number=1, fails_required[0]=1 → 0 < 1 → success
        assert state.is_mission_successful(fails=0) is True

    def test_exactly_required_fails_fails_mission(self):
        state = make_state()
        # fails_required[0]=1, so 1 fail → 1 < 1 is False → fail
        assert state.is_mission_successful(fails=1) is False

    def test_more_than_required_fails_fails_mission(self):
        state = make_state()
        assert state.is_mission_successful(fails=2) is False

    def test_mission_4_needs_two_fails(self):
        # 7-player game has fails_required=[1,1,1,2,1]
        state = make_state(7,
                           roles=["Merlin","Percival","LoyalServant","LoyalServant",
                                  "Assassin","Morgana","Oberon"],
                           people_per_mission=[2,3,3,4,4],
                           fails_required=[1,1,1,2,1])
        state.mission_number = 4
        assert state.is_mission_successful(fails=1) is True  # 1 < 2
        assert state.is_mission_successful(fails=2) is False  # 2 < 2 is False

    def test_record_mission_success(self):
        state = make_state()
        team = [1, 2]
        state.record_mission(team, success=True)
        assert state.successful_missions == 1
        assert state.failed_missions == 0
        assert state.mission_history[-1]["result"] == "success"

    def test_record_mission_failure(self):
        state = make_state()
        team = [1, 2]
        state.record_mission(team, success=False)
        assert state.failed_missions == 1
        assert state.successful_missions == 0
        assert state.mission_history[-1]["result"] == "fail"

    def test_mission_history_records_team(self):
        state = make_state()
        team = [1, 2]
        state.record_mission(team, success=True)
        assert state.mission_history[-1]["team"] == team

    def test_mission_history_records_mission_number(self):
        state = make_state()
        state.record_mission([1], success=True)
        assert state.mission_history[-1]["mission"] == 1


# ---------------------------------------------------------------------------
# Vote logic
# ---------------------------------------------------------------------------

class TestVoteLogic:
    def test_majority_approve_succeeds(self):
        state = make_state()
        assert state.is_votes_successful([True, True, True, False, False]) is True

    def test_majority_reject_fails(self):
        state = make_state()
        assert state.is_votes_successful([False, False, False, True, True]) is False

    def test_exact_tie_fails(self):
        # Tie (equal True/False) requires strictly more than half → fails
        state = make_state()
        assert state.is_votes_successful([True, True, False, False]) is False

    def test_all_approve_succeeds(self):
        state = make_state()
        assert state.is_votes_successful([True, True, True, True, True]) is True

    def test_all_reject_fails(self):
        state = make_state()
        assert state.is_votes_successful([False, False, False, False, False]) is False

    def test_process_vote_success_returns_true(self):
        state = make_state()
        result = state.process_vote([True, True, True, False, False])
        assert result is True

    def test_process_vote_failure_returns_false(self):
        state = make_state()
        result = state.process_vote([False, False, False, True, True])
        assert result is False

    def test_process_vote_failure_increments_counter(self):
        state = make_state()
        state.process_vote([False, False, False, True, True])
        assert state.failed_vote_count == 1

    def test_process_vote_success_does_not_increment_counter(self):
        state = make_state()
        state.process_vote([True, True, True, False, False])
        assert state.failed_vote_count == 0

    def test_failed_vote_advances_leader(self):
        state = make_state()
        original_leader = state.get_current_leader()
        state.process_vote([False, False, False, True, True])
        assert state.get_current_leader() != original_leader

    def test_successful_vote_does_not_advance_leader(self):
        state = make_state()
        original_leader = state.get_current_leader()
        state.process_vote([True, True, True, False, False])
        assert state.get_current_leader() == original_leader


# ---------------------------------------------------------------------------
# Game-over conditions
# ---------------------------------------------------------------------------

class TestGameOver:
    def test_not_over_at_start(self):
        state = make_state()
        assert state.is_game_over() is False

    def test_three_successful_missions_ends_game(self):
        state = make_state()
        state.successful_missions = 3
        assert state.is_game_over() is True

    def test_three_failed_missions_ends_game(self):
        state = make_state()
        state.failed_missions = 3
        assert state.is_game_over() is True

    def test_five_failed_votes_ends_game(self):
        state = make_state()
        state.failed_vote_count = 5
        assert state.is_game_over() is True

    def test_two_of_each_not_over(self):
        state = make_state()
        state.successful_missions = 2
        state.failed_missions = 2
        assert state.is_game_over() is False


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

class TestNavigation:
    def test_next_mission_increments_number(self):
        state = make_state()
        state.next_mission()
        assert state.mission_number == 2

    def test_next_mission_resets_vote_count(self):
        state = make_state()
        state.failed_vote_count = 3
        state.next_mission()
        assert state.failed_vote_count == 0

    def test_next_mission_advances_leader(self):
        state = make_state()
        original_leader = state.get_current_leader()
        state.next_mission()
        assert state.get_current_leader() != original_leader

    def test_leader_wraps_around(self):
        state = make_state(5)
        all_leaders = set()
        for _ in range(5):
            all_leaders.add(state.get_current_leader())
            state.next_leader()
        assert all_leaders == set(state.players.keys())

    def test_get_team_size_mission_1(self):
        state = make_state(people_per_mission=[2, 3, 2, 3, 3])
        assert state.get_team_size() == 2

    def test_get_team_size_out_of_bounds(self):
        state = make_state(people_per_mission=[2, 3, 2, 3, 3])
        state.mission_number = 6
        assert state.get_team_size() == 0


# ---------------------------------------------------------------------------
# Assassin / Merlin helpers
# ---------------------------------------------------------------------------

class TestSpecialRoleFinders:
    def test_get_merlin_finds_merlin(self):
        state = make_state(5)
        merlin_uid = state.get_merlin()
        assert merlin_uid is not None
        assert state.player_roles[merlin_uid] == "Merlin"

    def test_get_merlin_returns_none_when_absent(self):
        roles = ["LoyalServant", "LoyalServant", "LoyalServant", "Assassin", "Morgana"]
        state = make_state(5, roles=roles)
        assert state.get_merlin() is None

    def test_get_assassin_finds_assassin(self):
        state = make_state(5)
        assassin_uid = state.get_assassin()
        assert assassin_uid is not None
        assert state.player_roles[assassin_uid] == "Assassin"

    def test_is_assassin_present_true(self):
        state = make_state(5)
        assert state.is_assassin_present() is True

    def test_is_assassin_present_false(self):
        roles = ["Merlin", "Percival", "LoyalServant", "LoyalServant", "Morgana"]
        state = make_state(5, roles=roles)
        assert state.is_assassin_present() is False

    def test_is_evil_player(self):
        state = make_state(5)
        for uid, role in state.player_roles.items():
            from game.roles import is_evil
            assert state.is_evil(uid) == is_evil(role)
