# TODO — Avalon Telegram Bot

> Feature roadmap for future development. Each item is self-contained and can be implemented independently.

---

## New Roles (Good)

- [ ] **Tristan & Iseult (The Lovers)** — Two good roles that know each other. They see each other at the start but have no other special powers. Must be added as a pair. Tristan is good, Iseult is good.
- [ ] **Cleric** — Good role. At the start of the game, the Cleric learns the alignment (good/evil) of the first leader. Provides early-game information.
- [ ] **Merlin Pure** — Variant of Merlin. Sees ALL evil players including Mordred, but if Merlin Pure is assassinated, evil wins. Higher risk, higher reward.
- [ ] **Revealer** — Good role. Can reveal their own loyalty card to another player once per game. Useful for building trust.

## New Roles (Evil)

- [ ] **Trickster** — Evil role. Appears as a random good role when investigated by Lady of the Lake or Cleric. Makes investigation unreliable.
- [ ] **Lunatic** — Evil role. Believes they are Merlin (receives Merlin's vision info) but is actually evil. Creates confusion if they act on false confidence.
- [ ] **Brute** — Evil role. When on a mission, can force the mission to fail regardless of votes (overrides normal mission mechanics). Powerful but reveals their evil nature.
- [ ] **Witch** — Evil role. Can look at one player's role card once per game (not just alignment — the actual role).

## New Expansions / Game Modes

- [ ] **Lady of the Sea** — Variant of Lady of the Lake. When investigating an evil player, the holder sees their **specific role** (not just alignment). When investigating a good player, only sees "good". Creates more information but also more bluffing opportunities. Implement as a new GameMode.
- [ ] **Plot Cards** — Major expansion. At the start of each round, the leader draws plot cards and distributes them to other players:
  - 5-6 players: 1 card/round (7 cards in deck)
  - 7-8 players: 2 cards/round (15 cards)
  - 9-10 players: 3 cards/round (15 cards)
  - Card types:
    - **Usable cards**: "Lead to Victory" (become leader), "Ambush" (examine mission cards), "King Returns" (reject approved team), "We Found You" (force open play)
    - **Instant cards**: "Restore Your Honor" (steal a plot card), "Show Your Strength" (leader reveals loyalty), "Show Your True Nature" (reveal your loyalty), "Are You the One" (check neighbor's loyalty)
    - **Effects cards**: "Charge!" (force public voting)
  - Implement as a GameMode that injects a "plot_card_distribution" phase before each team selection
- [ ] **Sorcerers and Rogues** — Expansion adding new faction dynamics. Research specific rules.
- [ ] **Messengers** — Expansion module from Big Box edition. Research specific rules.
- [ ] **Excalibur variant: Holder rotates** — Instead of the leader always wielding Excalibur, the Excalibur holder rotates (like Lady of the Lake token).

## Game Settings & Quality of Life

- [ ] **Save/Load custom game presets** — Let GM save their custom role composition + mode + timeout settings as a named preset in `chat_data`. Load with `/loadpreset <name>`. Delete with `/deletepreset <name>`. List with `/presets`.
- [ ] **Anonymous voting option** — Config toggle to only show approve/reject counts in team vote results, not who voted what. Adds more mystery.
- [ ] **Help command** — `/help` listing all commands grouped by context (lobby / in-game / info). Translatable.
- [ ] **Game log export** — `/export` dumps full game history (roles, missions, votes, discussion timestamps) as a text file or formatted message.
- [ ] **Spectator mode** — `/watch` for non-players to follow the game. Spectators see public info but can't vote or act.
- [ ] **MVP vote** — After game ends, players vote for "best player" (just for fun). Track in stats.
- [ ] **Achievements** — "Won 3 games as Merlin", "Assassinated Merlin", "Won with 0 failed missions", etc. Stored in `chat_data`, shown in `/stats`.
- [ ] **Rematch with shuffle** — `/rematch` after game ends to quickly create a new game with the same players (reshuffled roles).
- [ ] **Player count validation per mode** — Automatically disable/warn about modes that don't make sense for the player count (e.g., Lancelot needs 5+, Lady needs 7+, Excalibur needs 5+).
- [ ] **Configurable good/evil balance warning** — When using custom roles, warn GM if the good/evil ratio is significantly off from standard (e.g., all evil, or 1 good vs 4 evil).

## Technical / Infrastructure

- [ ] **Error handler** — Register a global error handler in `main.py` to catch and log unhandled exceptions instead of "No error handlers are registered".
- [ ] **Logging** — Replace `print()` statements with proper Python `logging` module. Add log levels.
- [ ] **Database migration from Pickle** — PicklePersistence breaks on class structure changes. Consider migrating to SQLite or JSON-based persistence for production use.
- [ ] **Unit tests** — Add tests for `game_state.py` (mission logic, vote logic, role assignment), `roles.py` (vision, alignment), `game_modes.py` (modify_roles, on_mission_end).
- [ ] **Rate limiting** — Telegram has rate limits on message editing. Add debouncing for rapid team selection toggles.
- [ ] **Docker support** — Add `Dockerfile` and `docker-compose.yml` for easy self-hosting.
- [ ] **Webhook mode** — Option to run with webhooks instead of polling for production deployment.
- [ ] **Admin commands** — Bot admin (not GM) commands: `/broadcast`, `/shutdown`, `/resetgroup`.

## i18n

- [ ] **Japanese (ja)** — Add Japanese translation.
- [ ] **Simplified Chinese (zh-CN)** — Add Simplified Chinese translation.
- [ ] **Role name localization in game_setting.toml** — Show localized role names in variant picker even for preset variants.
- [ ] **Translatable error messages from controller** — Some controller error strings are still raw English (e.g., "No valid role variants"). Move to i18n keys.

---

## References

- [Avalon Official Roles](https://avalon-game.com/wiki/roles/)
- [Avalon Expansions](https://avalon-game.com/wiki/expansions/)
- [Plot Cards](https://avalon-game.com/en/wiki/expansions/plot_cards/)
- [Lady of the Sea](https://avalon-game.com/en/wiki/expansions/lady_sea/)
- [Excalibur](https://avalon-game.com/wiki/expansions/excalibur/)
- [Avalon Big Box](https://indieboardsandcards.com/our-games/avalon-big-box/)
- [THavalon (Extended Ruleset)](https://github.com/jtc2/THavalon)
