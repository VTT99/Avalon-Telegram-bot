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
        self.timeout_minutes = 30  # default slow (30 min)

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

    def add_player(self, user_id, name):
        if self.status != "pre_game_lobby":
            return False, "Game already started."
        if user_id in self.players:
            return False, "You already joined."
        if len(self.players) >= self.max_players:
            return False, "Player limit reached. Ask the game master to /startgame."
        self.players[user_id] = name
        return True, f"{name} joined the game."

    def remove_player(self, user_id):
        if self.status != "pre_game_lobby":
            return False, "Can't leave after game started."
        if user_id not in self.players:
            return False, "You're not in the game."
        name = self.players.pop(user_id)
        return True, f"{name} left the game."

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

    def player_list_text(self):
        return "\n".join(f"- {name}" for name in self.players.values())

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
