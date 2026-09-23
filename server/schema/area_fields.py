"""
Single source of truth for the area fields/prefs the GM panel exposes.

Declares, exactly once: the scalar fields the Areas-tab inspector shows, which
of them are editable, how the frontend should render each (input control type),
which boolean prefs a CM may toggle (vs. GM-only), and how each editable field
is written back through the real command layer.

Consumers that derive from this table instead of re-declaring it:

- ``server/commands/hubs.py`` ``ooc_cmd_area_pref``  -- the ``cm_allowed`` gate
- ``server/web_view/gm_panel`` serializers           -- field lists + meta + pref badges
- ``server/web_view/gm_panel`` ``AreaRoutes.handle_edit_area`` -- write dispatch
  (previously a ~130-line if/elif chain; now a single registry lookup)

Adding an editable area field therefore means: (1) the real ``Area`` attribute
and its command (if any) in ``server/``, and (2) ONE ``AREA_WRITE_STRATEGIES``
entry (+ optionally a ``AREA_FIELD_META`` entry for its control type). The
serializer and route handler pick it up automatically.

This module is a LEAF: it imports only ``server.exceptions`` (itself a leaf) so
``area.py``, the command layer, ``scripting.py`` and the web view can all import
it without circular imports. Write strategies duck-type ``session`` (they never
import ``GMSession``).
"""

from server.exceptions import ClientError


# =============================================================================
# Boolean area prefs: one source of truth for /area_pref, the GM Panel badge
# and the generated docs/auto/prefs.md (`AREA_PREFS_META` below).
# =============================================================================

# Each entry explains one boolean `Area` attribute (server/area.py).
#    description -- what the pref does (rendered in docs/auto/prefs.md).
#    note        -- optional extra guidance, e.g. "used by /X -- do not change
#                   directly" (rendered verbatim).
#    cm_allowed  -- True: any CM may toggle it (GM Panel shows no "[gm]" badge).
#                   False: only hub owners (GMs)/mods may toggle it.
#    internal    -- True: system/runtime state, grouped under "do not change
#                   directly" in the docs rather than as a togglable pref.
#
# The generator cross-validates these keys against the live boolean attributes
# of `Area`, so a new/missing/renamed pref fails the docs build.
#
# `AREA_PREF_CM_ALLOWED` is re-derived from `cm_allowed` and is mirrored by
# `ooc_cmd_area_pref`'s gate (server/commands/hubs.py), which imports it here.
AREA_PREFS_META = {
    "showname_changes_allowed": {
        "description": (
            "If True, users are allowed to change their showname. If False, "
            "only CMs and above are allowed to change their showname."
        ),
        "cm_allowed": True,
    },
    "shouts_allowed": {
        "description": (
            "If True, users are allowed to use Objection/Hold It/Take "
            "That/Custom shouts. If False, only CMs and above can use shouts."
        ),
        "cm_allowed": True,
    },
    "jukebox": {
        "description": (
            "If True, the Jukebox is in play for this area, acting like a "
            "playlist of music to keep the area DJed automatically. If False, "
            "music has to be chosen manually."
        ),
        "cm_allowed": True,
    },
    "non_int_pres_only": {
        "description": (
            "If True, all preanimations process the text immediately with no "
            "delay, equivalent to forcing the 'immediate' checkbox to always "
            "be on. CMs and above bypass this restriction. If False, "
            "preanimations stop text processing unless 'immediate' is ticked "
            "by the user."
        ),
        "cm_allowed": True,
    },
    "blankposting_allowed": {
        "description": (
            "If True, messages are not filtered for blankposting and may "
            "contain no message or just whitespace. If False, every message "
            "must contain at least some text. CMs and above bypass this "
            "restriction."
        ),
        "cm_allowed": True,
    },
    "blankposting_forced": {
        "description": (
            "If True, players may only send blankposts in IC, like the "
            "per-player /force_blankpost command. If False, normal posting "
            "rules apply."
        ),
        "cm_allowed": True,
    },
    "hide_clients": {
        "description": (
            "If True, the number of clients present in the area is hidden "
            "from the client's area list for normal users. This does not "
            "affect /getarea. If False, the client count is displayed."
        ),
        "cm_allowed": True,
    },
    "music_autoplay": {
        "description": (
            "If True, the current track plays automatically for any user that "
            "enters the area. If False, the user must use /getmusic to play "
            "the area's track."
        ),
        "cm_allowed": True,
    },
    "replace_music": {
        "description": (
            "If True, this area's music list completely overwrites the server "
            "or hub music list. If False, the music lists are stacked."
        ),
        "cm_allowed": True,
    },
    "client_music": {
        "description": (
            "If True, clients are allowed to load a custom music list on the "
            "client side. If False, client-side music lists are not allowed."
        ),
        "cm_allowed": True,
    },
    "can_dj": {
        "description": (
            "If True, normal users can choose songs in this area. If False, "
            "only CMs and above can choose songs."
        ),
        "cm_allowed": True,
    },
    "music_locked": {
        "description": (
            "If True, no one can choose songs in this area, regardless of the "
            "can_dj setting. If False, songs change depending on can_dj."
        ),
        "cm_allowed": True,
    },
    "can_radio": {
        "description": (
            "If True, the /radio command is usable in this area (still "
            "respecting the other music prefs like can_dj and music_locked). "
            "If False, radio playback is disabled."
        ),
        "cm_allowed": True,
    },
    "hidden": {
        "description": (
            "If True, this area is hidden from the client area lists. If "
            "False, the area is visible in the client area lists."
        ),
        "cm_allowed": True,
    },
    "can_whisper": {
        "description": (
            "If True, users are allowed to whisper to each other using the IC "
            "command /w. If False, only CMs and above can use the IC command."
        ),
        "cm_allowed": True,
    },
    "can_wtce": {
        "description": (
            "If True, anyone can use Witness Testimony/Cross Examination/etc. "
            "judge buttons. If False, only CMs and above may use the judge "
            "buttons."
        ),
        "cm_allowed": True,
    },
    "can_spectate": {
        "description": (
            "If True, anyone can switch to a Spectator, a character that "
            "doesn't permit speaking and hides you from /getarea etc. If "
            "False, only CMs and above are allowed to be a Spectator."
        ),
        "cm_allowed": True,
    },
    "can_getarea": {
        "description": (
            "If True, anyone can use /getarea to see the players present in "
            "the area. If False, only CMs and above may use /getarea."
        ),
        "cm_allowed": True,
    },
    "can_cross_swords": {
        "description": (
            "If True, the Cross Swords trial minigame can be started by "
            "players through IC or /cs. If False, the minigame is disabled."
        ),
        "cm_allowed": True,
    },
    "can_scrum_debate": {
        "description": (
            "If True, a Cross Swords debate can evolve into a Scrum Debate "
            "minigame. If False, the minigame is disabled."
        ),
        "cm_allowed": True,
    },
    "can_panic_talk_action": {
        "description": (
            "If True, the Panic Talk Action trial minigame can be started by "
            "players through IC or /pta. If False, the minigame is disabled."
        ),
        "cm_allowed": True,
    },
    "bg_lock": {
        "description": (
            "If True, this area's background cannot be changed by anyone who "
            "is not a CM or above. If False, normal users can change the "
            "background, provided they're not muted/spectating and the area "
            "is not dark."
        ),
        "cm_allowed": True,
    },
    "force_sneak": {
        "description": (
            "If True, all area OOC enter/leave messages are hidden. If False, "
            "area OOC enter/leave messages are shown unless the player is "
            "hidden, sneaking, a spectator, etc."
        ),
        "cm_allowed": True,
    },
    "present_reveals_evidence": {
        "description": (
            "If True, presenting a piece of evidence reveals it to everyone. "
            "If False, evidence visibility rules are stricter."
        ),
        "cm_allowed": True,
    },
    "ooc_actions_enabled": {
        "description": (
            "If True, IC action messages (asterisk/color-3) are mirrored to "
            "OOC. If False, they are not. Toggleable per-area with "
            "/ooc_actions."
        ),
        "cm_allowed": True,
    },
    "can_switch_pos": {
        "description": (
            "If True, players can switch positions manually. If False, "
            "positions can only be changed via links or /forcepos."
        ),
        "cm_allowed": True,
    },
    "medieval_mode": {
        "description": (
            "If True, all IC messages in the area are transformed into Ye "
            "Olde English. If False, messages are sent as-is."
        ),
        "cm_allowed": True,
    },
    "public_votes": {
        "description": (
            "If True, the /vote command will also reveal who you voted for. "
            "If False, /vote only tells others that you voted, not your "
            "target."
        ),
        "cm_allowed": True,
    },
    "can_cm": {
        "description": "Whether or not someone can become a Case Maker in this area.",
        "cm_allowed": False,
    },
    "locking_allowed": {
        "description": (
            "If True, normal users are allowed to lock this area using /lock. "
            "If False, only CMs or above, or users with the appropriate keys, "
            "can lock the area."
        ),
        "cm_allowed": False,
    },
    "iniswap_allowed": {
        "description": (
            "If True, users can change to custom char.ini files not recognized "
            "by the server's base content. If False, only base content "
            "characters and char.ini files may be used."
        ),
        "cm_allowed": False,
    },
    "can_change_status": {
        "description": (
            "If True, this area's /status can be changed by normal users. If "
            "False, it can only be changed by a CM or above."
        ),
        "cm_allowed": False,
    },
    "use_backgrounds_yaml": {
        "description": (
            "If True, the area is only allowed backgrounds from the server's "
            "backgrounds.yaml configuration file. If False, any custom BG "
            "name is allowed."
        ),
        "cm_allowed": False,
    },
    "auto_pair": {
        "description": (
            "If True, clients in the same position can pair directly without "
            "using commands (see also auto_pair_max). If False, pairing "
            "requires commands."
        ),
        "cm_allowed": False,
    },
    "auto_pair_cycle": {
        "description": (
            "If True and auto_pair is enabled, the currently speaking player "
            "is always shown in the center. If False, the pairing layout is "
            "static."
        ),
        "cm_allowed": False,
    },
    "overlay_lock": {
        "description": (
            "If True, only CMs and above can change this area's overlay with "
            "/overlay. If False, normal users may change it."
        ),
        "cm_allowed": False,
    },
    "passing_msg": {
        "description": (
            "If True, an IC message is sent when a player changes areas in "
            "this hub. Toggled per-hub by GMs with /toggle_passing_ic."
        ),
        "cm_allowed": False,
    },
    "locked": {
        "description": "Whether or not the area is locked.",
        "note": "Used by /area_lock and /area_unlock. Do not change this directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "muted": {
        "description": "Whether or not this area is muted.",
        "note": "Used by /area_mute and /area_unmute. Do not change this directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "dark": {
        "description": "Whether the area is dark or not.",
        "note": "Used by the /lights command. Do not change this directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "old_muted": {
        "description": (
            "The remembered mute status of the area before a trial minigame "
            "swapped it; the area returns to this state once the minigame is "
            "over."
        ),
        "note": "Do not change this directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "recording": {
        "description": (
            "Whether the area is currently recording testimony, i.e. a "
            "Witness Testimony has been started by a CM."
        ),
        "note": "Do not change this directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "battle_started": {
        "description": "Runtime state of the battle minigame.",
        "note": "Advanced battle-system flag. Do not change directly!",
        "cm_allowed": False,
        "internal": True,
    },
    "can_battle": {
        "description": "Whether the battle minigame may start in this area.",
        "note": "Advanced battle-system flag; prefer /battle_config.",
        "cm_allowed": False,
        "internal": True,
    },
    "battle_show_hp": {
        "description": "Whether battle HP bars are displayed.",
        "note": "Advanced battle-system flag; set via /battle_config.",
        "cm_allowed": False,
        "internal": True,
    },
}

# Mirrored by `ooc_cmd_area_pref`'s `cm_allowed` gate (server/commands/hubs.py),
# which imports this exact set instead of keeping its own copy.
AREA_PREF_CM_ALLOWED = frozenset(
    name for name, meta in AREA_PREFS_META.items() if meta.get("cm_allowed")
)


# =============================================================================
# Boolean hub prefs: same shape as AREA_PREFS_META, for AreaManager
# (server/area_manager.py). All hub prefs are GM-tier; `note` typically names
# the toggle command. Cross-validated by the docs generator against the live
# boolean attributes of `AreaManager`.
# =============================================================================

HUB_PREFS_META = {
    "arup_enabled": {
        "description": (
            "Whether the ARea UPdate system is enabled for this hub, i.e. the "
            "extra information displayed in the A/M area list and the ability "
            "to set a /status."
        ),
        "note": "Toggled with /arup_enable and /arup_disable.",
    },
    "hide_clients": {
        "description": (
            "If True, the playercounts of this hub's areas are hidden from "
            "normal users. If False, playercounts are displayed."
        ),
        "note": "Toggled with /hide_clients and /unhide_clients.",
    },
    "can_gm": {
        "description": "Whether players may become Game Masters in this hub.",
        "note": "Managed through the hub's GM list (/gm, /ungm).",
    },
    "remote_gm_only": {
        "description": (
            "Whether only remote/system GMs are permitted in this hub, with "
            "no in-game GM promotion."
        ),
    },
    "replace_music": {
        "description": (
            "If True, the hub music list replaces the server's music list "
            "entirely. If False, the lists are stacked."
        ),
        "note": "Toggled with /toggle_replace_music.",
    },
    "client_music": {
        "description": (
            "If True, clients are allowed to load a custom music list on the "
            "client side in this hub. If False, client-side music lists are "
            "not allowed."
        ),
    },
    "single_cm": {
        "description": (
            "If True, a hub keeps at most a single Case Maker per area; once "
            "the last CM leaves, the area resets to its saved originals."
        ),
    },
    "censor_ic": {
        "description": (
            "If True, in-character chat in this hub is censored using the "
            "server's censors.yaml."
        ),
    },
    "censor_ooc": {
        "description": (
            "If True, out-of-character chat in this hub is censored using the "
            "server's censors.yaml."
        ),
    },
    "can_spectate": {
        "description": (
            "If True, non-GMs may use a Spectator character in this hub. If "
            "False, spectator play is restricted."
        ),
        "note": "Toggled with /toggle_spectate.",
    },
    "can_getareas": {
        "description": (
            "If True, normal players may use /getareas in this hub. If False, "
            "it is restricted to GMs and above."
        ),
        "note": "Toggled with /toggle_getareas.",
    },
    "passing_msg": {
        "description": (
            "If True, an IC message is sent when a player changes areas in "
            "this hub. If False, none is sent."
        ),
        "note": "Toggled with /toggle_passing_ic.",
    },
    "autokick_to_latest_area": {
        "description": (
            "If True, switching to a character instantly kicks the player to "
            "that character's latest occupied area. If False, no such kick "
            "happens."
        ),
        "note": "Toggled with /toggle_autokick.",
    },
}


# =============================================================================
# Scalar fields exposed in the inspector (read-only + editable)
# =============================================================================

# Every field name here must exist on ``Area`` (server/area.py) either as an
# instance attribute set in ``__init__`` or as a computed ``@property``.
AREA_SCALAR_FIELDS = (
    "name", "background", "background_suffix", "overlay", "dark",
    "locked", "status", "doc", "desc", "move_delay", "max_players",
    "evidence_mod", "pos_lock", "abbreviation", "ambience", "broadcast_list",
    "background_dark", "pos_dark", "desc_dark", "msg_delay", "music_ref",
    "hp_def", "hp_pro", "music", "password", "triggers",
    "cross_swords_song_start", "cross_swords_song_end", "cross_swords_song_concede",
    "scrum_debate_song_start", "scrum_debate_song_end", "scrum_debate_song_concede",
    "panic_talk_action_song_start", "panic_talk_action_song_end",
    "panic_talk_action_song_concede",
)


# =============================================================================
# Input-control metadata for the frontend (editable fields only; `pos_lock` is
# special-cased in the frontend and deliberately absent)
# =============================================================================

AREA_FIELD_META = {
    "name": {"input": "text"},
    "desc": {"input": "text"},
    "doc": {"input": "text"},
    "max_players": {"input": "number"},
    "status": {"input": "text"},
    "dark": {"input": "checkbox"},
    "locked": {"input": "checkbox"},
    "background_suffix": {"input": "text"},
    "background_dark": {"input": "text"},
    "pos_dark": {"input": "text"},
    "desc_dark": {"input": "text"},
    "password": {"input": "text"},
    "move_delay": {"input": "number"},
    "msg_delay": {"input": "number"},
    "hp_def": {"input": "number", "min": 0, "max": 10},
    "hp_pro": {"input": "number", "min": 0, "max": 10},
    "evidence_mod": {"input": "select", "options": ["FFA", "CM", "Mods", "HiddenCM"]},
    "music_ref": {"input": "select", "options": [], "clearable": True},
    "triggers": {"input": "triggers"},
    "cross_swords_song_start": {"input": "text"},
    "cross_swords_song_end": {"input": "text"},
    "cross_swords_song_concede": {"input": "text"},
    "scrum_debate_song_start": {"input": "text"},
    "scrum_debate_song_end": {"input": "text"},
    "scrum_debate_song_concede": {"input": "text"},
    "panic_talk_action_song_start": {"input": "text"},
    "panic_talk_action_song_end": {"input": "text"},
    "panic_talk_action_song_concede": {"input": "text"},
}


# =============================================================================
# Write strategies: field -> callable(session, area, value, extra) -> output list
# =============================================================================

def _as_int(value, err_label):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(err_label)


def _in_area(cmd, clear_cmd=None, arg_fn=None):
    """A strategy that runs a command on the (shadowed) target area."""
    def strategy(session, area, value, extra):
        if clear_cmd is not None and value == "":
            return session.execute_command_in_area(area, clear_cmd, "")
        arg = arg_fn(value) if arg_fn is not None else value
        return session.execute_command_in_area(area, cmd, arg)
    return strategy


def _validated_in_area(cmd, err_label, arg_fn=None, range_check=None):
    """Like `_in_area`, but validates `value` as an int first (passing it on)."""
    def strategy(session, area, value, extra):
        try:
            n = _as_int(value, err_label)
            if range_check is not None and not range_check(n):
                raise ValueError(err_label)
        except ValueError as ex:
            return [f"[ERROR] {ex}"]
        arg = arg_fn(n) if arg_fn is not None else value
        return session.execute_command_in_area(area, cmd, arg)
    return strategy


def _direct_set(attr, key=None, coerce=None, note=None):
    """A strategy that writes the attribute directly via `session.set_area_direct`."""
    def strategy(session, area, value, extra):
        val = value
        if coerce is not None:
            try:
                val = coerce(value)
            except ValueError as ex:
                return [f"[ERROR] {ex}"]
        try:
            if not session.set_area_direct(area, attr, val, key=key):
                return ["[ERROR] Could not update area field."]
            return [f"{attr} updated." if note is None else note]
        except ClientError as ex:
            return [f"[ERROR] {ex}"]
    return strategy


def _triggers_strategy(session, area, value, extra):
    trigger = str(extra.get("trigger", "")).strip()
    if trigger not in area.triggers:
        return [f"[ERROR] Invalid trigger: {trigger}"]
    if value == "":
        return _direct_set("triggers", key=trigger, note=f"Cleared trigger '{trigger}'.")(
            session, area, value, extra
        )
    return session.execute_command_in_area(area, "trigger", f"{trigger} {value}")


_MINIGAME_CODE = {"cross_swords": "cs", "scrum_debate": "sd", "panic_talk_action": "pta"}
_MINIGAME_CONDITIONS = ("start", "end", "concede")


def _minigame_song_strategy(field, code, condition):
    def strategy(session, area, value, extra):
        if value == "":
            return _direct_set(field)(session, area, value, extra)
        return session.execute_command_in_area(area, f"minigame_{condition}_song", f"{code} {value}")
    return strategy


def _hp_strategy(side):
    def strategy(session, area, value, extra):
        try:
            hp = _as_int(value, "HP must be an integer between 0 and 10.")
            if not 0 <= hp <= 10:
                raise ValueError("HP must be between 0 and 10.")
        except ValueError as ex:
            return [f"[ERROR] {ex}"]
        return session.execute_command_in_area(area, "hpset", f"{side} {hp}")
    return strategy


AREA_WRITE_STRATEGIES = {
    "name": lambda s, area, value, extra: s.execute_command("area_rename", f"{area.id} {value}"),
    "desc": _in_area("desc", clear_cmd="desc_clear"),
    "doc": _in_area("doc", clear_cmd="cleardoc"),
    "max_players": _validated_in_area("max_players", "max_players must be an integer."),
    "pos_lock": _in_area("pos_lock", clear_cmd="pos_lock_clear"),
    "status": _in_area("status"),
    "dark": _in_area("lights", arg_fn=lambda v: "off" if v == "true" else "on"),
    "locked": lambda s, area, value, extra: s.execute_command("unlock" if value == "false" else "lock", str(area.id)),
    "desc_dark": _in_area("desc_dark", clear_cmd="desc_dark_clear"),
    "background_suffix": _in_area("bg_suffix"),
    "move_delay": _validated_in_area(
        "area_move_delay", "Move delay must be an integer between -1800 and 1800.",
        range_check=lambda n: -1800 <= n <= 1800,
    ),
    "evidence_mod": lambda s, area, value, extra: (
        [f"[ERROR] Invalid evidence mod. Use FFA, CM, Mods or HiddenCM."]
        if value not in ("FFA", "CM", "Mods", "HiddenCM")
        else s.execute_command_in_area(area, "evidence_mod", value)
    ),
    "music_ref": _in_area("area_musiclist"),
    "password": lambda s, area, value, extra: s.execute_command("setpw", f"{area.id} {value}".rstrip()),
    "hp_def": _hp_strategy("def"),
    "hp_pro": _hp_strategy("pro"),
    "triggers": _triggers_strategy,
    "background_dark": _direct_set("background_dark"),
    "pos_dark": _direct_set("pos_dark"),
    "msg_delay": _direct_set("msg_delay", coerce=lambda v: _as_int(v, "msg_delay must be an integer.")),
}


# Minigame song scalars are generated from the same declaration table so a new
# minigame or song slot only needs one `_MINIGAME_CODE` entry.
for _minigame, _code in _MINIGAME_CODE.items():
    for _condition in _MINIGAME_CONDITIONS:
        _field = f"{_minigame}_song_{_condition}"
        AREA_WRITE_STRATEGIES[_field] = _minigame_song_strategy(_field, _code, _condition)


# Editable fields == the set of fields with a write strategy.
AREA_EDITABLE_FIELDS = frozenset(AREA_WRITE_STRATEGIES)

