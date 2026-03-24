from game.game_state import State
from game.game_modes import create_mode
from conf.game_setting import CONFIG
import random


class Controller:
    def __init__(self, group_id, master_id, config, chat_data=None):
        self.group_id = group_id
        self.master_id = master_id
        self.players = {}
        self.status = "pre_game_lobby"
        self.min_players = config["min_players"]
        self.max_players = config["max_players"]
        self.lobby_message_id = None
        self.state = None

        # Per-stage timeouts (minutes, 0 = no limit)
        self.timeouts: dict[str, int] = {
            "lobby": 2,
            "team_select": 30,
            "team_vote": 30,
            "mission_vote": 30,
            "assassin_guess": 30,
            "investigate": 30,
            "discussion": 0,  # 0 = disabled by default
        }
        self.allow_extend = False
        self.extend_used = False  # reset each phase

        # Language: prefer group-persisted, fall back to config default
        default_lang = config.get("default_language", "en")
        self.language = chat_data.get("lang", default_lang) if chat_data else default_lang

        # Game modes
        self.enabled_modes: list[str] = []
        self.active_modes: list = []  # instantiated GameMode objects

        # Round tracking
        self.selected_team: list[int] = []
        self.team_message_id: int | None = None
        self.team_votes: dict[int, bool] = {}
        self.mission_votes: dict[int, bool] = {}
        self.assassin_guess_message_id: int | None = None
        self.vote_history: list[dict] = []
        self.show_roles_in_group: bool = True  # whether to announce role list at game start

        # Spectators: user_id -> name
        self.spectators: dict[int, str] = {}

    def add_player(self, user_id, name):
        if self.status != "pre_game_lobby":
            return False, "game_already_started"
        if user_id in self.players:
            return False, "already_joined"
        if len(self.players) >= self.max_players:
            return False, "player_limit_reached"
        self.players[user_id] = name
        return True, "player_joined"

    def remove_player(self, user_id):
        if self.status != "pre_game_lobby":
            return False, "cant_leave_started"
        if user_id not in self.players:
            return False, "not_in_game"
        name = self.players.pop(user_id)
        return True, "player_left"

    def is_game_master(self, user_id):
        return user_id == self.master_id

    def can_start(self):
        return len(self.players) >= self.min_players

    # --- Variant selection ---

    def get_available_setups(self) -> tuple[bool, str, list]:
        """Get all valid role variants for the current player count."""
        player_count = len(self.players)
        variants_by_count = CONFIG.get("roles_by_player_count", {})
        role_variants = variants_by_count.get(str(player_count), [])

        if not role_variants:
            return False, f"No valid role variants configured for {player_count} players.", []

        valid = []
        for variant in role_variants:
            roles = variant.get("roles", [])
            ppm = variant.get("people_per_mission", [])
            fr = variant.get("fails_required", [])
            if roles and len(roles) == player_count and len(ppm) == 5 and len(fr) == 5:
                valid.append(variant)

        if not valid:
            return False, "No valid role variants for this player count.", []

        return True, f"{len(valid)} variant(s) available.", valid

    def start_game(self, variant_index: int = 0) -> tuple[bool, str]:
        """Start the game with a specific variant index."""
        success, error_msg, variants = self.get_available_setups()
        if not success:
            return False, error_msg

        if variant_index < 0 or variant_index >= len(variants):
            variant_index = 0

        variant = variants[variant_index]
        roles = list(variant["roles"])
        player_count = len(self.players)

        # Apply mode role modifications
        self.active_modes = [create_mode(m) for m in self.enabled_modes]
        for mode in self.active_modes:
            roles = mode.modify_roles(roles, player_count)

        game_setup = {
            "roles": roles,
            "number_of_players_per_mission": variant["people_per_mission"],
            "fails_required": variant["fails_required"],
        }

        self.status = "team_select"
        self.state = State(self.players, **game_setup)

        # Let modes initialize
        for mode in self.active_modes:
            mode.on_game_start(self.state)

        return True, "Game started"

    def start_game_custom(self, roles: list[str]) -> tuple[bool, str]:
        """Start the game with a custom role list chosen by GM."""
        player_count = len(self.players)
        if len(roles) != player_count:
            return False, "Role count mismatch"

        # Get mission config from first available variant for this player count
        _, _, variants = self.get_available_setups()
        if variants:
            ppm = variants[0]["people_per_mission"]
            fr = variants[0]["fails_required"]
        else:
            # Fallback: generate default mission config
            ppm = [min(2 + i, player_count) for i in range(5)]
            fr = [1, 1, 1, (2 if player_count >= 7 else 1), 1]

        # Apply mode modifications (Lancelot won't double-apply since GM already picked roles)
        self.active_modes = [create_mode(m) for m in self.enabled_modes
                             if m != "lancelot"]  # skip lancelot modify_roles for custom
        # But still instantiate lancelot for its on_game_start/on_mission_end hooks
        if "lancelot" in self.enabled_modes:
            self.active_modes.append(create_mode("lancelot"))

        game_setup = {
            "roles": roles,
            "number_of_players_per_mission": ppm,
            "fails_required": fr,
        }

        self.status = "team_select"
        self.state = State(self.players, **game_setup)

        for mode in self.active_modes:
            mode.on_game_start(self.state)

        return True, "Game started"

    def player_list_text(self):
        return "\n".join(f"- {name}" for name in self.players.values())

    def add_spectator(self, user_id: int, name: str) -> tuple[bool, str]:
        if user_id in self.players:
            return False, "spectator_is_player"
        if user_id in self.spectators:
            return False, "already_spectating"
        self.spectators[user_id] = name
        return True, "spectator_added"

    def remove_spectator(self, user_id: int) -> tuple[bool, str]:
        if user_id not in self.spectators:
            return False, "not_spectating"
        self.spectators.pop(user_id)
        return True, "spectator_removed"

    # --- Mode helpers ---

    def toggle_mode(self, mode_name: str) -> bool:
        """Toggle a mode on/off. Returns True if now enabled."""
        if mode_name in self.enabled_modes:
            self.enabled_modes.remove(mode_name)
            return False
        else:
            self.enabled_modes.append(mode_name)
            return True

    def check_mode_phases(self, mission_number: int) -> str | None:
        """Check if any active mode wants to inject a phase after this mission."""
        for mode in self.active_modes:
            phase = mode.on_mission_end(self.state, mission_number)
            if phase:
                return phase
        return None

    # --- Round tracking helpers ---

    def toggle_team_member(self, user_id: int) -> bool:
        if user_id in self.selected_team:
            self.selected_team.remove(user_id)
            return False
        else:
            self.selected_team.append(user_id)
            return True

    def is_team_complete(self) -> bool:
        return len(self.selected_team) == self.state.get_team_size()

    def reset_round(self):
        self.selected_team = []
        self.team_message_id = None
        self.team_votes = {}
        self.mission_votes = {}

    def all_team_votes_in(self) -> bool:
        return len(self.team_votes) == len(self.players)

    def all_mission_votes_in(self) -> bool:
        return len(self.mission_votes) == len(self.selected_team)

    def record_team_vote(self, user_id: int, approve: bool):
        self.team_votes[user_id] = approve

    def record_mission_vote(self, user_id: int, success: bool):
        self.mission_votes[user_id] = success
