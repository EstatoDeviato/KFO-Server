import random
from pathlib import Path

import yaml

from server.client_manager import ClientManager
from server.constants import derelative

from . import Arg, command, mod_only


__all__ = [
    "ooc_cmd_choose_fighter",
    "ooc_cmd_info_fighter",
    "ooc_cmd_create_fighter",
    "ooc_cmd_create_move",
    "ooc_cmd_modify_stat",
    "ooc_cmd_delete_fighter",
    "ooc_cmd_delete_move",
    "ooc_cmd_battle_config",
    "ooc_cmd_fight",
    "ooc_cmd_use_move",
    "ooc_cmd_battle_info",
    "ooc_cmd_refresh_battle",
    "ooc_cmd_remove_fighter",
    "ooc_cmd_surrender",
    "ooc_cmd_skip_move",
    "ooc_cmd_force_skip_move",
    "ooc_cmd_create_guild",
    "ooc_cmd_info_guild",
    "ooc_cmd_join_guild",
    "ooc_cmd_leave_guild",
    "ooc_cmd_battle_effects",
    "ooc_cmd_close_guild",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FIGHTER_STORAGE = Path("storage/battlesystem")

# Keep this as a tuple so the order shown by /battle_effects stays stable.
BATTLE_EFFECTS = (
    "atkraise",
    "sparaise",
    "defraise",
    "spdraise",
    "atkdown",
    "defdown",
    "spadown",
    "spddown",
    "speraise",
    "spedown",
    "heal",
    "poison",
    "paralysis",
    "atkall",
    "multishot",
    "atkraiseally",
    "defraiseally",
    "sparaiseally",
    "spdraiseally",
    "speraiseally",
    "stealatk",
    "stealdef",
    "stealspa",
    "stealspd",
    "stealspe",
    "stealmana",
    "burn",
    "freeze",
    "stunned",
    "confused",
    "enraged",
    "sleep",
    "healstatus",
)

# Effects that make a move supportive rather than offensive.
ALLY_EFFECTS = {
    "heal",
    "healstatus",
    "atkraiseally",
    "defraiseally",
    "sparaiseally",
    "spdraiseally",
    "speraiseally",
}

# Effect name -> (fighter attribute, human-readable label)
SELF_RAISE_EFFECTS = {
    "atkraise": ("atk", "attack"),
    "defraise": ("defe", "defense"),
    "sparaise": ("spa", "special attack"),
    "spdraise": ("spd", "special defense"),
    "speraise": ("spe", "speed"),
}

TARGET_LOWER_EFFECTS = {
    "atkdown": ("atk", "attack"),
    "defdown": ("defe", "defense"),
    "spadown": ("spa", "special attack"),
    "spddown": ("spd", "special defense"),
    "spedown": ("spe", "speed"),
}

ALLY_RAISE_EFFECTS = {
    "atkraiseally": ("atk", "attack"),
    "defraiseally": ("defe", "defense"),
    "sparaiseally": ("spa", "special attack"),
    "spdraiseally": ("spd", "special defense"),
    "speraiseally": ("spe", "speed"),
}

STEAL_EFFECTS = {
    "stealatk": ("atk", "the attack"),
    "stealdef": ("defe", "the defense"),
    "stealspa": ("spa", "the special attack"),
    "stealspd": ("spd", "the special defense"),
    "stealspe": ("spe", "the speed"),
    "stealmana": ("mana", "mana"),
}

STAT_NAMES = ("hp", "mana", "atk", "defe", "spa", "spd", "spe")

# Command-facing stat names -> YAML keys used by fighter definitions.
STAT_STORAGE_KEYS = {
    "hp": "HP",
    "mana": "MANA",
    "atk": "ATK",
    "defe": "DEF",
    "spa": "SPA",
    "spd": "SPD",
    "spe": "SPE",
}

BATTLE_CONFIG_FLOATS = {
    "critical_bonus": "battle_critical_bonus",
    "bonus_malus": "battle_bonus_malus",
    "poison_damage": "battle_poison_damage",
    "burn_damage": "battle_burn_damage",
    "freeze_damage": "battle_freeze_damage",
    "enraged_bonus": "battle_enraged_bonus",
    "stolen_stat": "battle_stolen_stat",
}

BATTLE_CONFIG_POSITIVE_INTS = {
    "paralysis_rate": "battle_paralysis_rate",
    "critical_rate": "battle_critical_rate",
    "confusion_rate": "battle_confusion_rate",
}

BATTLE_CONFIG_NON_NEGATIVE_INTS = {
    "min_multishot": "battle_min_multishot",
    "max_multishot": "battle_max_multishot",
}

# These values are used as divisors and therefore cannot be zero.
POSITIVE_FLOAT_CONFIGS = {
    "bonus_malus",
    "poison_damage",
    "burn_damage",
    "freeze_damage",
    "stolen_stat",
}

BATTLE_CONFIG_NAMES = (
    "paralysis_rate",
    "critical_rate",
    "critical_bonus",
    "bonus_malus",
    "poison_damage",
    "show_hp",
    "min_multishot",
    "max_multishot",
    "burn_damage",
    "freeze_damage",
    "confusion_rate",
    "enraged_bonus",
    "stolen_stat",
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _fighter_storage_path(name):
    """Return the sanitized path used for a fighter YAML file."""
    normalized_name = derelative(name.strip().lower())
    return FIGHTER_STORAGE / f"{normalized_name}.yaml"


def _fighter_exists(name):
    """Return True when a fighter YAML file exists."""
    return _fighter_storage_path(name).is_file()


def _load_fighter(name):
    """Load a fighter definition from YAML."""
    path = _fighter_storage_path(name)

    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def _save_fighter(name, fighter):
    """Persist a fighter definition to YAML using a deterministic format."""
    FIGHTER_STORAGE.mkdir(parents=True, exist_ok=True)
    path = _fighter_storage_path(name)

    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(
            fighter,
            stream,
            allow_unicode=True,
            sort_keys=False,
        )


def _battle_fighter_exists(client):
    """Return True when the client currently has a selected fighter."""
    return client.battle is not None


def _get_fighter_ids(area):
    """Build a quick client-id -> client lookup for the current area."""
    return {fighter.id: fighter for fighter in area.fighters}


def _finish_turn_if_ready(area):
    """
    Resolve the current turn once every fighter has selected an action.

    Both /use_move and /skip_move used to contain this exact block.
    Keeping it here prevents the two commands from drifting apart.
    """
    if area.num_selected_move != len(area.fighters):
        return

    area.fighters = start_battle_animation(area)
    area.num_selected_move = 0

    if not area.battle_started:
        area.battle_started = True

    # A finished battle leaves the fighter list empty.
    if not area.fighters:
        area.battle_started = False


def _send_fighter_message(client, include_moves=False):
    """Build and send a fighter information message."""
    battle = client.battle
    if battle is None:
        return

    lines = [f"\n👤 {battle.fighter} 👤:"]

    if battle.status is not None:
        lines.append(f"Status 🌈: {battle.status}")

    lines.extend(
        [
            "",
            f"HP 💗: {battle.hp:.2f}/{battle.maxhp}",
            f"MANA 💧: {battle.mana:.2f}",
            f"ATK 🗡️: {battle.atk:.2f}",
            f"DEF 🛡️: {battle.defe:.2f}",
            f"SPA ✨: {battle.spa:.2f}",
            f"SPD 🔮: {battle.spd:.2f}",
            f"SPE 💨: {battle.spe:.2f}",
            "",
        ]
    )

    if include_moves:
        for move_id, move in enumerate(battle.moves):
            lines.extend(
                [
                    f"🌠 [{move_id}]{move.name} 🌠:",
                    f"ManaCost 💧: {move.cost}",
                    f"Type 💠: {move.type}",
                    f"Power 💪: {move.power}",
                    f"Accuracy 🔎: {move.accuracy}%",
                ]
            )

            if move.effect:
                lines.append("Effects 🔰:")
                lines.extend(f"- {effect}" for effect in move.effect)

            lines.append("")

    client.send_ooc("\n".join(lines))


def send_info_fighter(client):
    """Send fighter stats and move information."""
    _send_fighter_message(client, include_moves=True)


def send_stats_fighter(client):
    """Send fighter stats without listing the moves."""
    _send_fighter_message(client, include_moves=False)


def find_guild(client):
    """
    Return the guild containing the client, or None when it belongs to none.
    """
    for guild_name, members in client.area.battle_guilds.items():
        if client in members:
            return guild_name
    return None


def _remove_from_guild(client, *, notify=False):
    """
    Remove a client from its current guild.

    Returns the guild name, or None if the client is not in a guild.
    """
    if client.battle is None or client.battle.guild is None:
        return None

    guild = client.battle.guild
    members = client.area.battle_guilds.get(guild)

    if members is not None and client in members:
        members.remove(client)

        if not members:
            client.area.battle_guilds.pop(guild, None)

    client.battle.guild = None

    if notify:
        client.send_ooc("You have been removed from the current guild")

    return guild


def _add_to_guild(client, guild):
    """Add a client to a guild and update the BattleChar reference."""
    client.area.battle_guilds.setdefault(guild, []).append(client)
    client.battle.guild = guild


def reload_fighter(client, char=None):
    """
    Rebuild client.battle from the fighter YAML definition.

    When ``char`` is supplied, it is used directly so a command can reload
    the battle object without reading the file a second time after saving.
    """
    if char is None:
        char = _load_fighter(client.battle.fighter)

    fighter_name = client.battle.fighter
    client.battle = ClientManager.BattleChar(client, fighter_name, char)
    client.battle.guild = find_guild(client)


# ---------------------------------------------------------------------------
# Fighter commands
# ---------------------------------------------------------------------------

@command(Arg("arg", rest=True, default="", help="fighter name"))
def ooc_cmd_choose_fighter(client, arg):
    """
    Choose a fighter from the server list.

    Usage: /choose_fighter NameFighter
    """
    fighter_name = derelative(arg.strip().lower())

    if not (FIGHTER_STORAGE / f"{fighter_name}.yaml").is_file():
        client.send_ooc("No fighter has this name!")
        return

    char = _load_fighter(fighter_name)
    client.battle = ClientManager.BattleChar(client, fighter_name, char)
    client.battle.guild = find_guild(client)
    send_info_fighter(client)


@command()
def ooc_cmd_info_fighter(client):
    """Send information about the currently selected fighter."""
    if _battle_fighter_exists(client):
        send_info_fighter(client)
    else:
        client.send_ooc("You have to choose a fighter first!")


@mod_only(hub_owners=True)
@command(
    Arg("name", help="fighter name"),
    Arg("hp", float),
    Arg("mana", float),
    Arg("atk", float),
    Arg("defe", float),
    Arg("spa", float),
    Arg("spd", float),
    Arg("spe", float),
)
def ooc_cmd_create_fighter(client, name, hp, mana, atk, defe, spa, spd, spe):
    """
    Create a fighter and customize its base stats.

    Usage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE
    """
    if hp <= 0 or any(stat < 0 for stat in (mana, atk, defe, spa, spd, spe)):
        client.send_ooc(
            "mana, atk, def, spa, spd, spe have to be greater than or equal to zero\n"
            "hp has to be greater than zero\n"
            "Usage: /create_fighter FighterName HP MANA ATK DEF SPA SPD SPE"
        )
        return

    FIGHTER_STORAGE.mkdir(parents=True, exist_ok=True)

    fighter_files = tuple(FIGHTER_STORAGE.glob("*.yaml"))
    if len(fighter_files) >= 1000:
        client.send_ooc(
            "Fighter storage is full! Please contact the server host to resolve this issue."
        )
        return

    fighter_name = derelative(name.strip().lower())
    if not fighter_name:
        client.send_ooc("Fighter name cannot be empty.")
        return

    if _fighter_exists(fighter_name):
        client.send_ooc("This fighter has already been created.")
        return

    fighter = {
        "HP": hp,
        "MANA": mana,
        "ATK": atk,
        "DEF": defe,
        "SPA": spa,
        "SPD": spd,
        "SPE": spe,
        "Moves": [],
    }

    _save_fighter(fighter_name, fighter)
    client.send_ooc(f"{fighter_name} has been created!")


@command(
    Arg("name", help="move name"),
    Arg("cost", float),
    Arg("type", choices=["atk", "spa"], help="atk or spa"),
    Arg("power", float),
    Arg("accuracy", float, help="1-100"),
    Arg("effects", variadic=True, default=[], help="battle effects"),
)
def ooc_cmd_create_move(client, name, cost, type, power, accuracy, effects):
    """
    Add a move to the currently selected fighter.

    Usage: /create_move MoveName ManaCost MovesType Power Accuracy Effects
    """
    if not _battle_fighter_exists(client):
        client.send_ooc(
            "You have to choose a fighter to create a move.\n"
            "/choose_fighter FighterName"
        )
        return

    if cost < 0:
        client.send_ooc(
            "ManaCost has to be greater than or equal to zero.\n"
            "Usage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if power < 0:
        client.send_ooc(
            "Power has to be greater than or equal to zero.\n"
            "Usage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    if not 0 < accuracy <= 100:
        client.send_ooc(
            "Accuracy must be a number between 1 and 100.\n"
            "Usage: /create_move MoveName ManaCost MovesType Power Accuracy Effects"
        )
        return

    fighter_name = client.battle.fighter
    char = _load_fighter(fighter_name)

    moves = char.setdefault("Moves", [])
    move_names = {current_move.get("Name", "").lower() for current_move in moves}

    move_name = name.strip().lower()
    if not move_name:
        client.send_ooc("Move name cannot be empty.")
        return

    if move_name in move_names:
        client.send_ooc("This move has already been created.")
        return

    valid_effects = []
    unknown_effects = []

    for effect in effects:
        normalized_effect = effect.lower()
        if normalized_effect in BATTLE_EFFECTS:
            valid_effects.append(normalized_effect)
        else:
            unknown_effects.append(effect)

    moves.append(
        {
            "Name": move_name,
            "ManaCost": cost,
            "MovesType": type.lower(),
            "Power": power,
            "Accuracy": accuracy,
            "Effects": valid_effects,
        }
    )

    _save_fighter(fighter_name, char)

    client.send_ooc(f"{move_name} has been added!")

    if unknown_effects:
        client.send_ooc(
            "Note: these effects were not recognized and were ignored: "
            + ", ".join(unknown_effects)
        )

    reload_fighter(client, char)


@mod_only(hub_owners=True)
@command(
    Arg("name", help="fighter name"),
    Arg("stat", choices=STAT_NAMES),
    Arg("value", float),
)
def ooc_cmd_modify_stat(client, name, stat, value):
    """Modify one of a fighter's base stats."""
    fighter_name = derelative(name.strip().lower())

    if not _fighter_exists(fighter_name):
        client.send_ooc("No fighter has this name!")
        return

    if value < 0:
        client.send_ooc(
            "The value has to be a number greater than or equal to zero."
        )
        return

    char = _load_fighter(fighter_name)
    char[STAT_STORAGE_KEYS[stat]] = value
    _save_fighter(fighter_name, char)

    client.send_ooc(
        f"{fighter_name}'s {stat} has been modified. "
        "Choose this fighter again to check the changes."
    )


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="fighter name"))
def ooc_cmd_delete_fighter(client, arg):
    """Delete a fighter YAML definition."""
    fighter_name = derelative(arg.strip().lower())
    path = FIGHTER_STORAGE / f"{fighter_name}.yaml"

    if path.is_file():
        path.unlink()
        client.send_ooc(f"{arg} has been deleted!")
    else:
        client.send_ooc(f"{arg} is not found in the fighter server list.")


@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="move name"))
def ooc_cmd_delete_move(client, arg):
    """Delete a move from the currently selected fighter."""
    if not _battle_fighter_exists(client):
        client.send_ooc("You have to choose the fighter first.")
        return

    fighter_name = client.battle.fighter
    char = _load_fighter(fighter_name)
    moves = char.setdefault("Moves", [])
    move_name = arg.strip().lower()

    for index, current_move in enumerate(moves):
        if current_move.get("Name", "").lower() == move_name:
            moves.pop(index)
            _save_fighter(fighter_name, char)
            reload_fighter(client, char)
            client.send_ooc(f"{arg} has been deleted!")
            return

    client.send_ooc(f"{arg} is not found in the fighter moves.")


# ---------------------------------------------------------------------------
# Battle configuration
# ---------------------------------------------------------------------------

@mod_only(hub_owners=True)
@command(
    Arg("parameter", default="", help="setting name (blank lists all)"),
    Arg("value", default="", help="new value"),
)
def ooc_cmd_battle_config(client, parameter, value):
    """
    Customize battle settings for the current area.

    Usage: /battle_config <parameter> <value>
    """
    if not parameter:
        client.send_ooc(", ".join(BATTLE_CONFIG_NAMES))
        return

    parameter = parameter.lower()

    if parameter == "show_hp":
        normalized_value = value.lower()
        if normalized_value not in {"true", "false"}:
            client.send_ooc("value must be true or false")
            return

        client.area.battle_show_hp = normalized_value == "true"
        client.send_ooc(f"{parameter} has been changed to {normalized_value}")
        return

    if parameter in BATTLE_CONFIG_POSITIVE_INTS:
        try:
            parsed_value = int(value)
        except ValueError:
            client.send_ooc("value must be a whole number")
            return

        if parsed_value <= 0:
            client.send_ooc("value has to be greater than zero")
            return

        setattr(client.area, BATTLE_CONFIG_POSITIVE_INTS[parameter], parsed_value)

    elif parameter in BATTLE_CONFIG_NON_NEGATIVE_INTS:
        try:
            parsed_value = int(value)
        except ValueError:
            client.send_ooc("value must be a whole number")
            return

        if parsed_value < 0:
            client.send_ooc("value has to be greater than or equal to zero")
            return

        # Reject an invalid range instead of storing a configuration that
        # would later make random.randint(min, max) crash.
        min_multishot = (
            parsed_value
            if parameter == "min_multishot"
            else client.area.battle_min_multishot
        )
        max_multishot = (
            parsed_value
            if parameter == "max_multishot"
            else client.area.battle_max_multishot
        )

        if min_multishot > max_multishot:
            client.send_ooc(
                "min_multishot cannot be greater than max_multishot."
            )
            return

        setattr(
            client.area,
            BATTLE_CONFIG_NON_NEGATIVE_INTS[parameter],
            parsed_value,
        )

    elif parameter in BATTLE_CONFIG_FLOATS:
        try:
            parsed_value = float(value)
        except ValueError:
            client.send_ooc("value must be a number")
            return

        if parameter in POSITIVE_FLOAT_CONFIGS and parsed_value <= 0:
            client.send_ooc("value has to be greater than zero")
            return

        if parsed_value < 0:
            client.send_ooc("value cannot be negative")
            return

        setattr(client.area, BATTLE_CONFIG_FLOATS[parameter], parsed_value)

    else:
        client.send_ooc("value is not valid")
        return

    client.send_ooc(f"{parameter} has been changed to {value}")


# ---------------------------------------------------------------------------
# Battle information and lobby
# ---------------------------------------------------------------------------

def _fighter_battle_line(area, fighter):
    """Return one formatted fighter line for /battle_info."""
    emoji = "🔎" if fighter.battle.selected_move == -1 else "⚔️"

    show_hp = ""
    if area.battle_show_hp and fighter.battle.maxhp:
        hp_percentage = round(fighter.battle.hp * 100 / fighter.battle.maxhp, 2)
        show_hp = f": {hp_percentage}%"

    return (
        f"{emoji} [{fighter.id}]{fighter.battle.fighter} "
        f"({fighter.showname}){show_hp} {emoji}"
    )


def send_battle_info(client):
    """Build and return the formatted state of all fighters in the battle."""
    area = client.area
    lines = ["\n⚔️🛡️ Battle Fighters Info 🛡️⚔️:"]

    for guild, members in area.battle_guilds.items():
        lines.extend([f"\n⛩{guild} GUILD⛩:"])

        for fighter in members:
            if fighter in area.fighters:
                lines.append(_fighter_battle_line(area, fighter))

        lines.append("")

    guilded_fighter_ids = {
        id(fighter)
        for members in area.battle_guilds.values()
        for fighter in members
    }

    for fighter in area.fighters:
        if id(fighter) not in guilded_fighter_ids:
            lines.append(_fighter_battle_line(area, fighter))

    return "\n".join(lines)


@command()
def ooc_cmd_battle_info(client):
    """Send information about the current battle."""
    if client in client.area.fighters:
        client.send_ooc(send_battle_info(client))
    else:
        client.send_ooc("You are not fighting!")


@command()
def ooc_cmd_fight(client):
    """
    Join the battle or reconnect to an existing fighter slot.

    Usage: /fight
    """
    area = client.area

    # Reconnection path.
    if area.fighters and area.battle_started:
        fighter_by_name = {
            fighter.battle.fighter: fighter
            for fighter in area.fighters
            if fighter.battle.current_client is not None
        }

        if client in area.fighters:
            index = area.fighters.index(client)
            client.battle = area.fighters[index].battle
            client.battle.current_client = client
            return

        if fighter_by_name:
            if client.battle is not None and client.battle.fighter in fighter_by_name:
                # Reconnect to the exact fighter slot already associated with this client.
                target = fighter_by_name[client.battle.fighter]
            else:
                _, target = random.choice(list(fighter_by_name.items()))

            client.battle = target.battle
            client.battle.current_client = client

            if client.battle.guild is not None:
                members = area.battle_guilds[client.battle.guild]
                index = members.index(target)
                members[index] = client

            area.fighters.remove(target)
            area.fighters.append(client)

            message = send_battle_info(client)
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is ready to fight (reconnected)",
            )

            for fighter in area.fighters:
                fighter.send_ooc(message)

            return

    if not area.can_battle:
        client.send_ooc("You cannot fight in this area!")
        return

    if client.battle is None:
        client.send_ooc("You have to choose a fighter to start a battle!")
        return

    if client in area.fighters:
        client.send_ooc("You are already in battle!")
        return

    if area.battle_started:
        client.send_ooc("The battle is already started!")
        return

    area.fighters.append(client)

    message = send_battle_info(client)
    for fighter in area.fighters:
        fighter.send_ooc(message)

    area.broadcast_ooc(
        f"⚔️{client.battle.fighter} ({client.showname}) is ready to fight!⚔️"
    )
    battle_send_ic(client, msg=f"~{client.battle.fighter}~ is ready to fight")


@mod_only(hub_owners=True)
@command()
def ooc_cmd_refresh_battle(client):
    """Reset the current battle and return to the lobby."""
    area = client.area

    # Restore every fighter from YAML so temporary battle changes such as
    # buffs, debuffs, mana consumption and statuses do not leak into the next
    # battle after an admin refresh.
    for fighter in area.fighters:
        fighter.battle.selected_move = -1
        fighter.battle.target = None
        reload_fighter(fighter)

    area.fighters = []
    area.num_selected_move = 0
    area.battle_started = False

    client.send_ooc("The battle has been refreshed!")


@command()
def ooc_cmd_surrender(client):
    """Surrender from the current battle."""
    area = client.area

    if client not in area.fighters:
        client.send_ooc("You are not fighting at the moment!")
        return

    if client.battle.selected_move == -1:
        area.fighters.remove(client)
    else:
        client.battle.hp = 0
        client.battle.selected_move = -1
        client.battle.target = None

    battle_send_ic(
        client,
        msg=f"~{client.battle.fighter}~ decides to surrender",
        offset=100,
    )

    reload_fighter(client)

    if not area.fighters:
        area.battle_started = False


@mod_only(hub_owners=True)
@command(Arg("id", int, help="target client ID"))
def ooc_cmd_remove_fighter(client, id):
    """Force a fighter to leave the battle."""
    area = client.area
    fighter_ids = _get_fighter_ids(area)

    if id not in fighter_ids:
        client.send_ooc("Target not found!")
        return

    target = fighter_ids[id]

    if target.battle.selected_move == -1:
        area.fighters.remove(target)
    else:
        target.battle.hp = 0
        target.battle.selected_move = -1
        target.battle.target = None

    battle_send_ic(
        client,
        msg=f"~{target.battle.fighter}~ ran out of hp! (forced to leave the battle)",
        offset=100,
    )
    reload_fighter(target)

    if not area.fighters:
        area.battle_started = False


# ---------------------------------------------------------------------------
# Turn selection
# ---------------------------------------------------------------------------

@mod_only(hub_owners=True)
@command(Arg("id", int, help="target client ID"))
def ooc_cmd_force_skip_move(client, id):
    """Force a fighter to skip the current turn."""
    area = client.area
    fighter_ids = _get_fighter_ids(area)

    if id not in fighter_ids:
        client.send_ooc("The target is not in the fighter list")
        return

    target = fighter_ids[id]

    if target.battle.selected_move == -1:
        area.num_selected_move += 1

    target.battle.selected_move = -2

    target.send_ooc("You have been forced to skip the turn")
    client.send_ooc(f"{target.battle.fighter} has chosen to skip the turn")
    area.broadcast_ooc(f"{target.battle.fighter} has chosen a move")

    _finish_turn_if_ready(area)


@command()
def ooc_cmd_skip_move(client):
    """Skip the current turn."""
    area = client.area

    if client not in area.fighters:
        client.send_ooc("You cannot skip the turn if you are not in the fight!")
        return

    if client.battle.selected_move != -1:
        client.send_ooc("You already selected a move!")
        return

    client.battle.selected_move = -2
    area.num_selected_move += 1

    client.send_ooc("You have chosen to skip the turn")
    area.broadcast_ooc(f"{client.battle.fighter} has chosen a move")

    _finish_turn_if_ready(area)


# ---------------------------------------------------------------------------
# Guild commands
# ---------------------------------------------------------------------------

@mod_only(hub_owners=True)
@command(Arg("arg", rest=True, default="", help="guild name (blank closes all)"))
def ooc_cmd_close_guild(client, arg):
    """
    Close all guilds, or one specific guild.

    Usage: /close_guild <GuildName>
    """
    area = client.area
    guild_name = arg.strip()

    if not guild_name:
        for members in area.battle_guilds.values():
            for member in members:
                if member.battle is not None:
                    member.battle.guild = None

        area.battle_guilds.clear()
        area.broadcast_ooc("All guilds have been closed!")
        return

    members = area.battle_guilds.get(guild_name)
    if members is None:
        client.send_ooc("Guild not found!")
        return

    # Clear the BattleChar guild reference too; otherwise members would keep
    # a stale guild name after the dictionary entry was removed.
    for member in members:
        member.send_ooc(f"'{guild_name}' Guild has been closed")
        if member.battle is not None:
            member.battle.guild = None

    area.battle_guilds.pop(guild_name, None)


@command()
def ooc_cmd_battle_effects(client):
    """Show all available battle effects."""
    lines = ["Available Battle Effects:"]
    lines.extend(f"- {effect}" for effect in BATTLE_EFFECTS)
    client.send_ooc("\n".join(lines))


@command(
    Arg("id", int, default=None, help="target client ID (blank leaves yourself"),
)
def ooc_cmd_leave_guild(client, id):
    """
    Leave the current guild, or remove another member when authorized.

    Usage: /leave_guild <Target_ID>
    """
    area = client.area

    if id is None:
        if client.battle is None or client.battle.guild is None:
            client.send_ooc("You are not in any guilds!")
            return

        _remove_from_guild(client, notify=True)
        return

    # Area owners can remove any client from a guild.
    if client in area.area_manager.owners:
        area_ids = {fighter.id: fighter for fighter in area.clients}

        if id not in area_ids:
            client.send_ooc("Target not found!")
            return

        target = area_ids[id]
        if target.battle is None or target.battle.guild is None:
            client.send_ooc("Target has no fighter or is not in a guild!")
            return

        guild = target.battle.guild
        _remove_from_guild(target)

        client.send_ooc(f"Target has been removed from '{guild}' Guild")
        target.send_ooc(f"You have been removed from '{guild}' Guild")
        return

    # Guild leader can remove another guild member.
    if (
        client.battle is not None
        and client.battle.guild is not None
        and client == client.area.battle_guilds[client.battle.guild][0]
    ):
        guild = client.battle.guild
        guild_ids = {fighter.id: fighter for fighter in area.battle_guilds[guild]}

        if id not in guild_ids:
            client.send_ooc("Target not found!")
            return

        target = guild_ids[id]
        _remove_from_guild(target)

        client.send_ooc(f"Target has been removed from '{guild}' Guild")
        target.send_ooc(f"You have been removed from '{guild}' Guild")
        return

    client.send_ooc("You are not a GM or a Guild Leader")


@command(Arg("id", int, help="target client ID"))
def ooc_cmd_join_guild(client, id):
    """Invite another fighter to the guild you lead."""
    area = client.area

    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if client.battle.guild is None:
        client.send_ooc("You are not in any guilds!")
        return

    guild = client.battle.guild
    members = area.battle_guilds[guild]

    if client != members[0]:
        client.send_ooc(
            "You are not the guild leader; you cannot choose who joins the guild."
        )
        return

    area_ids = {fighter.id: fighter for fighter in area.clients}

    if id not in area_ids:
        client.send_ooc("Target not found!")
        return

    target = area_ids[id]

    if target.battle is None:
        client.send_ooc(f"{target.showname} has to choose a fighter first!")
        return

    if target.battle.guild is not None:
        client.send_ooc(f"{target.battle.fighter} is already in a guild!")
        return

    _add_to_guild(target, guild)

    client.send_ooc(f"{target.battle.fighter} joined the {guild} Guild!")
    target.send_ooc(f"You joined the {guild} Guild!")

    for member in members:
        send_info_guild(member)


@command(Arg("arg", rest=True, default="", help="guild name"))
def ooc_cmd_create_guild(client, arg):
    """Create a guild and become its leader."""
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    guild = arg.strip()
    if not guild:
        client.send_ooc("Guild name cannot be empty.")
        return

    if guild in client.area.battle_guilds:
        client.send_ooc("There is already a guild with this name!")
        return

    client.area.battle_guilds[guild] = [client]
    client.battle.guild = guild

    client.send_ooc(f"{guild} Guild has been created!")
    send_info_guild(client)


@command()
def ooc_cmd_info_guild(client):
    """Send information about the current guild."""
    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if client.battle.guild is None:
        client.send_ooc("You are not in any guilds!")
        return

    send_info_guild(client)


def send_info_guild(client):
    """Build and send information about the client's current guild."""
    guild = client.battle.guild
    members = client.area.battle_guilds[guild]
    guild_leader = members[0]

    lines = [
        f"\n⚔️🛡️{guild} GUILD🛡️⚔️:",
        "",
        (
            "Guild Leader: "
            f"⛩[{guild_leader.id}]{guild_leader.battle.fighter} "
            f"({guild_leader.showname})⛩"
        ),
    ]

    if len(members) > 1:
        lines.extend(["", "👤Members👤:", ""])

        for member in members[1:]:
            lines.append(
                f"⚔️[{member.id}]{member.battle.fighter} "
                f"({member.showname})⚔️"
            )

    client.send_ooc("\n".join(lines))


# ---------------------------------------------------------------------------
# Move selection
# ---------------------------------------------------------------------------

def _resolve_move(client, move_arg):
    """
    Resolve a move name or numeric move ID.

    Returns ``(move_id, move)`` or ``(None, None)`` when invalid.
    """
    moves = client.battle.moves

    if move_arg.isnumeric():
        move_id = int(move_arg)
        if move_id >= len(moves):
            client.send_ooc("There is no move with that ID!")
            return None, None
        return move_id, moves[move_id]

    normalized_name = move_arg.lower()
    move_names = [current_move.name.lower() for current_move in moves]

    if normalized_name not in move_names:
        client.send_ooc("There is no move with this name!")
        return None, None

    move_id = move_names.index(normalized_name)
    return move_id, moves[move_id]


@command(
    Arg("move", help="move name or ID"),
    Arg("target", int, default=None, help="target client ID"),
)
def ooc_cmd_use_move(client, move, target):
    """
    Select a move for the current battle turn.

    AttAll moves do not need a target.

    Usage: /use_move MoveName/Move_ID Target_ID
    """
    area = client.area

    if client.battle is None:
        client.send_ooc("You have to choose a fighter first!")
        return

    if client not in area.fighters:
        client.send_ooc("You are not ready to fight!")
        return

    if client.battle.selected_move != -1:
        client.send_ooc("You already selected a move!")
        return

    if client.battle.current_client is None:
        client.battle.current_client = client

    move_id, selected_move = _resolve_move(client, move)
    if selected_move is None:
        return

    if selected_move.cost > client.battle.mana:
        client.send_ooc("You don't have enough mana to use this move!")
        return

    # A move is only registered after every validation succeeds.
    if target is not None:
        fighter_ids = _get_fighter_ids(area)

        if target not in fighter_ids:
            client.send_ooc("Your target is not in the fighter list")
            return

        client.battle.target = fighter_ids[target]
    elif "atkall" in selected_move.effect:
        client.battle.target = "all"
    else:
        client.send_ooc("Not enough argument to attack")
        return

    client.battle.selected_move = move_id
    client.battle.mana -= selected_move.cost

    client.send_ooc(f"You have chosen {selected_move.name}")
    area.broadcast_ooc(f"{client.battle.fighter} has chosen a move")

    area.num_selected_move += 1
    _finish_turn_if_ready(area)


# ---------------------------------------------------------------------------
# Battle presentation
# ---------------------------------------------------------------------------

def battle_send_ic(client, msg, effect="", shake=0, offset=0):
    """
    Send a battle event to the current IC scene.

    ``effect`` is the visual battle effect name.
    ``shake`` enables a screenshake.
    ``offset`` selects the alive/dead sprite offset.
    """
    offset = 100 if offset else client.offset_pair

    if effect:
        sfx = f"sfx-{effect}"
    else:
        sfx = ""

    other_offset = 0
    other_emote = ""
    other_flip = 0
    other_folder = ""

    if client.charid_pair != -1:
        client_ids = {fighter.char_id: fighter for fighter in client.area.clients}
        target = client_ids.get(client.charid_pair)

        if target is None:
            client.charid_pair = -1
        else:
            other_offset = target.offset_pair
            other_emote = target.last_sprite
            other_flip = target.flip
            other_folder = target.claimed_folder

    client.area.send_ic(
        pre=client.last_pre,
        folder=client.claimed_folder,
        anim=client.last_sprite,
        msg=msg,
        pos=client.pos,
        emote_mod=1,
        flip=client.flip,
        color=3,
        charid_pair=client.charid_pair,
        offset_pair=offset,
        other_offset=other_offset,
        other_emote=other_emote,
        other_flip=other_flip,
        other_folder=other_folder,
        screenshake=shake,
        effect=f"{effect}|BattleEffects|{sfx}",
    )


# ---------------------------------------------------------------------------
# Battle engine helpers
# ---------------------------------------------------------------------------

def _is_ally_move(client, move):
    return any(effect in move.effect for effect in ALLY_EFFECTS)


def _get_move_targets(client, move, is_ally_move):
    """
    Resolve the target list for a move.

    Targeting behavior intentionally follows the original command:
    - atkall hits either allies or enemies depending on move effects.
    - multishot against a single target repeats that target.
    - multishot + atkall randomly selects from valid targets.
    """
    area = client.area

    if "atkall" in move.effect:
        if is_ally_move:
            if client.battle.guild is None:
                targets = list(area.fighters)
            else:
                members = area.battle_guilds[client.battle.guild]
                targets = [fighter for fighter in members if fighter in area.fighters]
        else:
            if client.battle.guild is None:
                targets = [fighter for fighter in area.fighters if fighter != client]
            else:
                guild_members = area.battle_guilds[client.battle.guild]
                targets = [
                    fighter
                    for fighter in area.fighters
                    if fighter not in guild_members
                ]

            if "multishot" in move.effect and targets:
                shots = random.randint(
                    area.battle_min_multishot,
                    area.battle_max_multishot,
                )
                targets = random.choices(targets, k=shots)

    elif "multishot" in move.effect:
        shots = random.randint(
            area.battle_min_multishot,
            area.battle_max_multishot,
        )
        targets = [client.battle.target for _ in range(shots)]

    else:
        targets = [client.battle.target]

    return targets


def _calculate_damage(client, target, move):
    """Calculate base damage and the matching IC animation effect."""
    if move.type == "atk":
        if target.battle.defe != 0:
            damage = move.power * client.battle.atk / target.battle.defe
        else:
            damage = target.battle.maxhp
        animation = "attack"
    else:
        if target.battle.spd != 0:
            damage = move.power * client.battle.spa / target.battle.spd
        else:
            damage = target.battle.maxhp
        animation = "specialattack"

    return round(damage, 2), animation


def _apply_target_stat_downs(client, target, move, area):
    for effect_name, (stat, label) in TARGET_LOWER_EFFECTS.items():
        if effect_name not in move.effect:
            continue

        setattr(
            target.battle,
            stat,
            getattr(target.battle, stat) / area.battle_bonus_malus,
        )
        battle_send_ic(
            target,
            msg=f"The {label} of ~{target.battle.fighter}~ goes down",
            effect="statdown",
        )


def _apply_steal_effects(client, target, move, area):
    for effect_name, (stat, label) in STEAL_EFFECTS.items():
        if effect_name not in move.effect:
            continue

        stolen = getattr(target.battle, stat) / area.battle_stolen_stat

        setattr(
            client.battle,
            stat,
            getattr(client.battle, stat) + stolen,
        )
        setattr(
            target.battle,
            stat,
            getattr(target.battle, stat) - stolen,
        )

        if stat == "mana":
            message = (
                f"~{client.battle.fighter}~ steals mana "
                f"from ~{target.battle.fighter}~"
            )
        else:
            message = (
                f"~{client.battle.fighter}~ steals {label} "
                f"of ~{target.battle.fighter}~"
            )

        battle_send_ic(target, msg=message, effect="stealstat")


def _apply_status_effects(client, target, move, area):
    """
    Apply status effects.

    Status effects are only applied when the target does not already have one,
    matching the original behavior.
    """
    if move.effect and "poison" in move.effect and target.battle.status is None:
        target.battle.status = "poison"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is affected by poisoning",
            effect="poison",
            shake=1,
        )

    if move.effect and "paralysis" in move.effect and target.battle.status is None:
        target.battle.status = "paralysis"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is affected by paralysis",
            effect="paralysis",
            shake=1,
        )

    if move.effect and "burn" in move.effect and target.battle.status is None:
        target.battle.status = "burn"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is burned",
            effect="burn",
            shake=1,
        )

        target.battle.spd /= area.battle_bonus_malus
        target.battle.defe /= area.battle_bonus_malus

        battle_send_ic(
            target,
            msg=f"and ~{target.battle.fighter}~'s defensive statistics go down",
            effect="statdown",
        )

    if move.effect and "freeze" in move.effect and target.battle.status is None:
        target.battle.status = "freeze"
        target.battle.spe /= area.battle_bonus_malus

        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is frozen",
            effect="freeze",
            shake=1,
        )
        battle_send_ic(
            target,
            msg=f"and ~{target.battle.fighter}~'s speed goes down",
            effect="statdown",
        )

    if move.effect and "stunned" in move.effect and target.battle.status is None:
        target.battle.status = "stunned"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is stunned",
            shake=1,
        )

    if move.effect and "confused" in move.effect and target.battle.status is None:
        target.battle.status = "confused"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is confused",
            effect="confused",
        )

    if move.effect and "sleep" in move.effect and target.battle.status is None:
        target.battle.status = "sleep-1"
        battle_send_ic(
            target,
            msg=f"~{target.battle.fighter}~ is sleeping",
            effect="sleep",
        )


def _apply_ally_move(client, target, move, area, *, single_target):
    """Apply healing and ally buffs to one target."""
    if target.battle.hp <= 0:
        if single_target:
            battle_send_ic(
                client,
                msg="and tries to help but the target is already down",
            )
        return

    if "heal" in move.effect:
        if move.type == "atk":
            heal = (move.power + client.battle.atk) * 0.25
        else:
            heal = (move.power + client.battle.spa) * 0.25

        target.battle.hp = min(target.battle.maxhp, target.battle.hp + heal)

        if target == client:
            battle_send_ic(
                client,
                msg=f"and heals itself of ~{heal}~ hp",
                effect="lifeup",
            )
        else:
            battle_send_ic(
                target,
                msg=f"and heals ~{target.battle.fighter}~ of ~{heal}~ hp",
                effect="lifeup",
            )

    if "healstatus" in move.effect:
        if target.battle.status is None:
            battle_send_ic(
                target,
                msg=(
                    f"and tries to remove status from ~{target.battle.fighter}~ "
                    f"but ~{target.battle.fighter}~ is healthy"
                ),
            )
        else:
            status = target.battle.status
            display_status = "sleep" if "sleep" in status else status
            target.battle.status = None

            # Restore temporary stat penalties associated with the status.
            if display_status == "burn":
                target.battle.spd *= area.battle_bonus_malus
                target.battle.defe *= area.battle_bonus_malus
            elif display_status == "freeze":
                target.battle.spe *= area.battle_bonus_malus

            battle_send_ic(
                target,
                msg=f"and removed {display_status} from ~{target.battle.fighter}~",
            )

    for effect_name, (stat, label) in ALLY_RAISE_EFFECTS.items():
        if effect_name not in move.effect:
            continue

        setattr(
            target.battle,
            stat,
            getattr(target.battle, stat) * area.battle_bonus_malus,
        )
        battle_send_ic(
            target,
            msg=f"and raises the {label} of ~{target.battle.fighter}~",
            effect="statup",
        )


def _apply_self_buffs(client, move, area):
    """Apply self-targeted stat increases and the enraged status."""
    for effect_name, (stat, label) in SELF_RAISE_EFFECTS.items():
        if effect_name not in move.effect:
            continue

        setattr(
            client.battle,
            stat,
            getattr(client.battle, stat) * area.battle_bonus_malus,
        )
        battle_send_ic(
            client,
            msg=f"The {label} of ~{client.battle.fighter}~ goes up",
            effect="statup",
        )

    if "enraged" in move.effect:
        client.battle.status = "enraged"
        battle_send_ic(
            client,
            msg=f"~{client.battle.fighter}~ is preparing for the next attack",
            effect="enraged",
        )


def _process_fighter_action(client, area):
    """Resolve one fighter's selected action."""
    if client.battle.hp <= 0:
        return

    if client.battle.selected_move == -2:
        battle_send_ic(
            client,
            msg=f"~{client.battle.fighter}~ decides to skip the turn",
        )
        return

    if client.battle.status == "stunned":
        client.battle.status = None
        battle_send_ic(
            client,
            msg=f"~{client.battle.fighter}~ is stunned and cannot fight",
        )
        return

    if client.battle.status == "confused":
        confusion = random.randint(1, area.battle_confusion_rate)

        if confusion == 1:
            client.battle.status = None
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ snaps out of confusion",
            )
        elif confusion == area.battle_confusion_rate:
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is confused and misses the target",
                effect="confused",
            )
            return
        else:
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is confused but focuses on the target",
                effect="confused",
            )

    if client.battle.status is not None and "sleep" in client.battle.status:
        if client.battle.status == "sleep-1":
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is sleeping",
                effect="sleep",
            )
            client.battle.status = "sleep-2"
            return

        if client.battle.status == "sleep-2":
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is sleeping",
                effect="sleep",
            )
            client.battle.status = "sleep-3"
            return

        client.battle.status = None
        battle_send_ic(client, msg=f"~{client.battle.fighter}~ wakes up")

    move = client.battle.moves[client.battle.selected_move]

    # Accuracy check happens before paralysis, matching the original order.
    if random.randint(1, 100) > move.accuracy:
        battle_send_ic(
            client,
            msg=f"~{client.battle.fighter}~ misses the target",
        )
        return

    if (
        client.battle.status == "paralysis"
        and random.randint(1, area.battle_paralysis_rate)
        == area.battle_paralysis_rate
    ):
        battle_send_ic(
            client,
            msg=f"~{client.battle.fighter}~ is affected by paralysis and cannot fight",
            effect="paralysis",
            shake=1,
        )
        return

    is_ally_move = _is_ally_move(client, move)
    targets = _get_move_targets(client, move, is_ally_move)

    battle_send_ic(
        client,
        msg=f"~{client.battle.fighter}~ uses ~{move.name}~",
    )

    if is_ally_move:
        single_target = len(targets) == 1
        for target in targets:
            _apply_ally_move(
                client,
                target,
                move,
                area,
                single_target=single_target,
            )
        return

    enraged_multiplier = 1
    if client.battle.status == "enraged":
        client.battle.status = None
        enraged_multiplier = area.battle_enraged_bonus
        battle_send_ic(client, msg="focuses all strength")

    for target in targets:
        if target is None:
            continue

        if target.battle.hp <= 0:
            if len(targets) == 1:
                battle_send_ic(client, msg="but the target is already down")
            continue

        damage, animation = _calculate_damage(client, target, move)

        critical_message = ""
        if random.randint(1, area.battle_critical_rate) == area.battle_critical_rate:
            critical_message = " with a critical"
            damage *= area.battle_critical_bonus

        damage *= enraged_multiplier
        target.battle.hp -= damage

        if damage == 0:
            battle_send_ic(
                target,
                msg=f"on ~{target.battle.fighter}~",
                effect=animation,
                shake=1,
            )
        else:
            battle_send_ic(
                target,
                msg=(
                    f"and attacks ~{target.battle.fighter}~{critical_message} "
                    f"dealing a damage of ~{damage}~"
                ),
                effect=animation,
                shake=1,
            )

        # Damage wakes a sleeping target before further effects are applied.
        if target.battle.status is not None and "sleep" in target.battle.status:
            target.battle.status = None
            battle_send_ic(target, msg=f"~{target.battle.fighter}~ wakes up")

        # A defeated target no longer receives secondary effects. This avoids
        # stealing stats from or applying a new status to a dead fighter.
        if target.battle.hp > 0:
            # Preserve the original order: stat changes, steals, then status.
            _apply_target_stat_downs(client, target, move, area)
            _apply_steal_effects(client, target, move, area)
            _apply_status_effects(client, target, move, area)

        if target.battle.hp <= 0:
            battle_send_ic(
                target,
                msg=f"~{target.battle.fighter}~ ran out of hp!",
                offset=100,
            )

    _apply_self_buffs(client, move, area)


def _apply_end_of_turn_statuses(area):
    """Apply poison, burn and freeze damage at the end of the turn."""
    for client in area.fighters:
        if client.battle.hp <= 0:
            continue

        if client.battle.status == "poison":
            damage = client.battle.maxhp / area.battle_poison_damage
            client.battle.hp -= damage
            battle_send_ic(
                client,
                msg=(
                    f"~{client.battle.fighter}~ is affected by poisoning "
                    f"and loses {damage} hp"
                ),
                effect="poison",
                shake=1,
            )

        if client.battle.status == "burn" and client.battle.hp > 0:
            damage = client.battle.maxhp / area.battle_burn_damage
            client.battle.hp -= damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is burned and loses {damage} hp",
                effect="burn",
                shake=1,
            )

        if client.battle.status == "freeze" and client.battle.hp > 0:
            damage = client.battle.maxhp / area.battle_freeze_damage
            client.battle.hp -= damage
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ is frozen and loses {damage} hp",
                effect="freeze",
                shake=1,
            )

        if client.battle.hp <= 0 and client.battle.status in {
            "poison",
            "burn",
            "freeze",
        }:
            battle_send_ic(
                client,
                msg=f"~{client.battle.fighter}~ ran out of hp!",
                offset=100,
            )


def _cleanup_dead_fighters(area):
    """Reset turn state and reload fighters removed from the battle."""
    last_processed = None

    for client in list(area.fighters):
        last_processed = client
        client.battle.selected_move = -1
        client.battle.target = None

        if client.battle.hp <= 0:
            area.fighters.remove(client)
            reload_fighter(client)

    return last_processed


def _resolve_battle_outcome(area, last_processed):
    """Resolve winner/draw state and prepare the next turn."""
    if len(area.fighters) == 1:
        winner = area.fighters[0]
        battle_send_ic(
            winner,
            msg=f"~{winner.battle.fighter}~ wins the battle!",
        )
        reload_fighter(winner)
        area.fighters = []
        return

    if not area.fighters:
        if last_processed is not None:
            battle_send_ic(
                last_processed,
                msg="~Everyone~ is down...",
                offset=100,
            )
        return

    guild_names = {fighter.battle.guild for fighter in area.fighters}
    if len(guild_names) == 1 and None not in guild_names:
        guild_name = next(iter(guild_names))
        winner_guild = area.battle_guilds[guild_name]

        battle_send_ic(
            winner_guild[0],
            msg=f"~{guild_name}~ wins the battle!",
        )

        area.fighters = []
        for winner in winner_guild:
            reload_fighter(winner)
        return

    # Nobody has won yet; show the state before the next turn.
    for client in area.fighters:
        send_stats_fighter(client)
        client.send_ooc(send_battle_info(client))


# ---------------------------------------------------------------------------
# Battle engine
# ---------------------------------------------------------------------------

def start_battle_animation(area):
    """
    Execute one complete battle turn.

    Order:
    1. Sort by speed.
    2. Resolve each selected action.
    3. Apply end-of-turn status damage.
    4. Remove defeated fighters and restore their base state.
    5. Resolve winner/draw/next turn.
    """
    # Fastest fighter acts first.
    area.fighters = sorted(
        area.fighters,
        key=lambda client: client.battle.spe,
        reverse=True,
    )

    for client in area.fighters:
        _process_fighter_action(client, area)

    _apply_end_of_turn_statuses(area)
    last_processed = _cleanup_dead_fighters(area)
    _resolve_battle_outcome(area, last_processed)

    return area.fighters
