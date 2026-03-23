from game.game_controller import Controller
from utils.language import get_message


def format_player_list(game: Controller) -> str:
    lang = game.language
    if not game.players:
        return get_message("no_players_yet", lang=lang)

    lines = [get_message("current_players", lang=lang)]
    for i, username in enumerate(game.players.values(), 1):
        lines.append(f"{i}. {username}")
    return "\n".join(lines)
