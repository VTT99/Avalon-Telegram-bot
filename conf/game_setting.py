# conf/game_setting.py
import os
import toml

_debug = os.environ.get("AVALON_DEBUG", "0") == "1"
_config_file = "conf/game_setting_debug.toml" if _debug else "conf/game_setting.toml"
CONFIG = toml.load(_config_file)
