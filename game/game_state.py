# game/game_state.py

import random
from game.roles import is_evil as _is_evil_role, is_good as _is_good_role


class State:
    def __init__(self, players: dict[int, object],
                 roles: list[str],
                 number_of_players_per_mission: list[int],
                 fails_required: list[int] = None):
        self.players = players  # {user_id: name}
        self.roles = roles  # list of roles
        self.player_roles = self.assign_roles()
        self.current_leader_index = random.randint(0, len(players) - 1)
        self.number_of_players_per_mission = number_of_players_per_mission
        self.fails_required = fails_required if fails_required else [1] * 5

        self.mission_number = 1
        self.successful_missions = 0
        self.failed_missions = 0
        self.failed_vote_count = 0

        self.mission_history = []
        self.mode_data: dict = {}  # arbitrary storage for game modes

    def is_assassin_present(self) -> bool:
        return "Assassin" in self.roles

    def assign_roles(self):
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        return {pid: role for pid, role in zip(player_ids, self.roles)}

    def get_role(self, user_id: int) -> str:
        return self.player_roles.get(user_id, "Unknown")

    def get_merlin(self) -> int | None:
        for user_id, role in self.player_roles.items():
            if role == "Merlin":
                return user_id
        return None

    def get_merlin_pure(self) -> int | None:
        for user_id, role in self.player_roles.items():
            if role == "MerlinPure":
                return user_id
        return None

    def get_assassin(self) -> int | None:
        for user_id, role in self.player_roles.items():
            if role == "Assassin":
                return user_id
        return None

    def is_evil(self, user_id: int) -> bool:
        return _is_evil_role(self.player_roles.get(user_id, ""))

    def get_evil_players(self) -> list[int]:
        return [uid for uid, role in self.player_roles.items() if _is_evil_role(role)]

    def get_good_players(self) -> list[int]:
        return [uid for uid, role in self.player_roles.items() if _is_good_role(role)]

    def next_leader(self):
        self.current_leader_index = (self.current_leader_index + 1) % len(self.players)

    def record_mission(self, team: list[int], success: bool):
        self.mission_history.append({
            "mission": self.mission_number,
            "team": team,
            "result": "success" if success else "fail",
            "leader": self.get_current_leader()
        })
        if success:
            self.successful_missions += 1
        else:
            self.failed_missions += 1

    def is_mission_successful(self, fails: int) -> bool:
        return fails < self.fails_required[self.mission_number - 1]

    def is_votes_successful(self, votes: list[bool]) -> bool:
        return votes.count(True) > len(votes) / 2

    def process_vote(self, votes: list[bool]) -> bool:
        if self.is_votes_successful(votes):
            return True
        else:
            self.failed_vote_count += 1
            self.next_leader()
            return False

    def next_mission(self):
        self.mission_number += 1
        self.reset_vote_count()
        self.next_leader()

    def reset_vote_count(self):
        self.failed_vote_count = 0

    def get_current_leader(self) -> int:
        return list(self.players.keys())[self.current_leader_index]

    def get_team_size(self) -> int:
        if self.mission_number <= len(self.number_of_players_per_mission):
            return self.number_of_players_per_mission[self.mission_number - 1]
        return 0

    def is_game_over(self) -> bool:
        return self.successful_missions == 3 or self.failed_missions == 3 or self.failed_vote_count >= 5
