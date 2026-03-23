from game.game_controller import Controller


def format_player_list(game: Controller) -> str:
    if not game.players:
        return "No players have joined yet."

    lines = ["👥 Current Players:"]
    for i, username in enumerate(game.players.values(), 1):
        lines.append(f"{i}. {username}")
    return "\n".join(lines)
