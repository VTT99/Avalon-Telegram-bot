class AvalonGame:
    def __init__(self, group_id, master_id, config):
        self.group_id = group_id
        self.master_id = master_id
        self.players = {}
        self.status = "pre_game_lobby"
        self.min_players = config["min_players"]
        self.max_players = config["max_players"]

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

    def start_game(self):
        self.status = "in_game"

    def player_list_text(self):
        return "\n".join(f"- {name}" for name in self.players.values())
