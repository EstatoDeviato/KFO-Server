# Battle Commands — User Guide

A practical guide to fighters, moves, battles, guilds, and GM administration.

Based on the current battle command implementation and the command list supplied with the project.

*September 22, 2026*

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [Fighter Management](#2-fighter-management)
3. [Creating and Managing Moves](#3-creating-and-managing-moves)
4. [Joining and Playing a Battle](#4-joining-and-playing-a-battle)
5. [Battle Effects Reference](#5-battle-effects-reference)
6. [Guilds](#6-guilds)
7. [GM and Battle Administration](#7-gm-and-battle-administration)
8. [Practical Example: One Complete Round](#8-practical-example-one-complete-round)
9. [Command Cheat Sheet](#9-command-cheat-sheet)

---

## 1. Before You Start

All commands shown in this guide use the server command prefix `/`. Replace placeholders such as `FighterName` or `Target_ID` with actual values.

**GM** means the command is restricted to the configured hub owners / game masters.

**Client IDs** are the numeric IDs displayed by battle information and guild information. They are used when a command asks for `Target_ID`.

**Names** are generally normalized to lowercase by the implementation. For move lookup, use either the move name or its numeric ID shown by `/info_fighter`.

### Quick start

1. Choose a fighter with `/choose_fighter <NameFighter>`.
2. Check the fighter with `/info_fighter` and note the move IDs.
3. Enter the battle with `/fight`.
4. During each turn, choose a move with `/use_move <MoveName-or-ID> <Target_ID>`, or use `/skip_move`.
5. Use `/battle_info` to see the current participants and, when enabled, their HP percentages.

### Important compatibility note

`/use_move` currently accepts a missing target automatically for moves carrying the `atkall` effect. A normal healing move still goes through the target-validation path unless it is also configured as an `atkall` move. The original command description says that heal moves need no target; the current implementation should be treated as authoritative for actual server behavior.

---

## 2. Fighter Management

### `/choose_fighter`

Choose a fighter from the server list and immediately display its stats and moves.

**Example**
```
/choose_fighter Knight
```

### `/info_fighter`

Display the currently selected fighter, its current battle status, HP, mana, combat stats, and all available moves.

**Example**
```
/info_fighter
```

### `/create_fighter` (GM)

Create a new fighter definition. HP must be greater than zero; the other base values must be zero or greater. New fighters start with no moves.

**Example**
```
/create_fighter Knight 100 50 20 15 10 12 18
```

### `/modify_stat` (GM)

Change one fighter base stat. Accepted stat names are `HP`, `MANA`, `ATK`, `DEF`, `SPA`, `SPD`, and `SPE`. Values cannot be negative.

**Example**
```
/modify_stat Knight hp 120
```

### `/delete_fighter` (GM)

Delete the fighter YAML definition from server storage.

**Example**
```
/delete_fighter Knight
```

### Fighter stat reference

| Stat | Meaning |
|------|---------|
| HP | Health. Reaching 0 removes the fighter from the active battle. |
| MANA | Resource consumed when a move is selected. |
| ATK | Physical attack stat used by ATK moves. |
| DEF | Physical defense stat used to mitigate ATK damage. |
| SPA | Special attack stat used by SPA moves. |
| SPD | Special defense stat used to mitigate SPA damage. |
| SPE | Speed. Fighters act in descending speed order. |

---

## 3. Creating and Managing Moves

### `/create_move`

Add a move to the currently selected fighter. The move type must be `atk` or `spa`. Mana cost and power must be non-negative; accuracy must be greater than 0 and at most 100. Unknown effect names are ignored and reported back to the user.

**Example**
```
/create_move Slash 10 atk 30 95
```

### `/delete_move` (GM)

Remove a move from the currently selected fighter.

**Example**
```
/delete_move Slash
```

### `/battle_effects`

Display the complete list of effect identifiers accepted by the battle system.

**Example**
```
/battle_effects
```

### How a move is defined

| Field | How to use it |
|-------|----------------|
| MoveName | A unique move name within the fighter. The implementation stores it in lowercase. |
| ManaCost | Mana consumed immediately when the move is successfully selected. |
| MovesType | `atk` uses ATK against the target DEF. `spa` uses SPA against the target SPD. |
| Power | Base move power used in the damage or healing calculation. |
| Accuracy | Percentage from 1 to 100. The move can miss before damage or effects are applied. |
| Effects | One or more identifiers from `/battle_effects`. Invalid names are ignored. |

### Example move recipes

- **Basic attack:** `/create_move Slash 8 atk 30 95`
- **Special attack:** `/create_move Fireball 12 spa 35 90 burn`
- **Self buff:** `/create_move Focus 6 atk 0 100 atkraise`
- **Multi-target attack:** `/create_move Volley 15 atk 20 85 atkall`
- **Multi-shot attack:** `/create_move Barrage 18 atk 15 80 multishot`

*These examples describe syntax and effect combinations; exact balance depends on the area configuration.*

---

## 4. Joining and Playing a Battle

### `/fight`

Join the active battle, or reconnect to a previously occupied fighter slot after a disconnect. You must have a selected fighter and be in an area where battles are allowed.

**Example**
```
/fight
```

### `/battle_info`

Display the current battle roster. Fighters are grouped by guild where applicable, and a HP percentage is shown when the area setting `show_hp` is enabled.

**Example**
```
/battle_info
```

### `/use_move [Target_ID]`

Select a move for the current turn. Use the move name or the numeric ID shown by `/info_fighter`. A target is required for ordinary single-target moves; an `atkall` move can omit the target.

**Example**
```
/use_move 0 42
```

### `/skip_move`

Skip the current turn. The turn resolves when every active fighter has selected an action.

**Example**
```
/skip_move
```

### `/surrender`

Leave the battle voluntarily. If you have not selected an action, you are removed immediately; otherwise your fighter is treated as defeated before being reset.

**Example**
```
/surrender
```

### Turn sequence

1. Players select a move or skip.
2. When everyone has selected an action, the fighters are sorted by SPE, fastest first.
3. Each selected action is resolved in that order.
4. End-of-turn poison, burn, and freeze damage is applied.
5. Defeated fighters are removed and their fighter state is reset from the stored definition.
6. If only one fighter remains, that fighter wins. A surviving guild can also win when all remaining fighters belong to the same guild.

### Targeting tips

Use `/battle_info` to identify the numeric client ID of the fighter you want to target. Guild membership affects area-of-effect ally/enemy targeting for moves carrying `atkall`.

---

## 5. Battle Effects Reference

The following descriptions are based on the current effect-handling code. Some effects are meaningful mainly because they are paired with a move type or another effect.

| Effect | Behavior |
|--------|----------|
| atkraise | Raise the user's ATK. |
| sparaise | Raise the user's SPA. |
| defraise | Raise the user's DEF. |
| spdraise | Raise the user's SPD. |
| speraise | Raise the user's SPE. |
| atkdown | Lower the target's ATK. |
| defdown | Lower the target's DEF. |
| spadown | Lower the target's SPA. |
| spddown | Lower the target's SPD. |
| spedown | Lower the target's SPE. |
| heal | Heal a target. Healing is capped at max HP. |
| healstatus | Remove the target's current status. Removing burn also restores the defensive stats reduced by burn. |
| poison | Apply poison if the target has no current status. |
| paralysis | Apply paralysis if the target has no current status. |
| burn | Apply burn if the target has no current status and reduce SPD and DEF. |
| freeze | Apply freeze if the target has no current status; freeze also deals end-of-turn damage. |
| stunned | Apply stunned if the target has no current status; the next action is lost. |
| confused | Apply confusion if the target has no current status; future turns use the area confusion rate. |
| sleep | Apply a sleep sequence. Sleeping fighters lose turns before waking. |
| enraged | Store an enraged status on the user; the next successful attack uses the area enraged multiplier. |
| atkall | Make the move area-targeted. For enemy moves it targets opponents; for ally moves it targets allies in the user's guild, or all fighters if unguilded. |
| multishot | Perform multiple target hits based on the configured min/max multishot values. Target selection behavior depends on whether atkall is also present. |
| atkraiseally | Raise an ally's ATK. |
| defraiseally | Raise an ally's DEF. |
| sparaiseally | Raise an ally's SPA. |
| spdraiseally | Raise an ally's SPD. |
| speraiseally | Raise an ally's SPE. |
| stealatk | Transfer part of the target's ATK to the user. |
| stealdef | Transfer part of the target's DEF to the user. |
| stealspa | Transfer part of the target's SPA to the user. |
| stealspd | Transfer part of the target's SPD to the user. |
| stealspe | Transfer part of the target's SPE to the user. |
| stealmana | Transfer part of the target's mana to the user. |

---

## 6. Guilds

### `/create_guild`

Create a guild. The creator automatically becomes the first member and therefore the guild leader.

**Example**
```
/create_guild Guardians
```

### `/info_guild`

Display the current guild, its leader, and its members.

**Example**
```
/info_guild
```

### `/join_guild`

Used by the guild leader to invite a fighter into the guild. The target must have a selected fighter and must not already belong to a guild.

**Example**
```
/join_guild 42
```

### `/leave_guild [Target_ID]`

Leave your current guild with no argument. A GM/area owner can remove a target, and the guild leader can remove another member.

**Example**
```
/leave_guild
/leave_guild 42
```

### `/close_guild [GuildName]` (GM)

Close every guild when no name is supplied, or close one named guild. Guild references on members are cleared when all guilds are closed; closing one guild removes that guild from the guild registry.

**Example**
```
/close_guild Guardians
```

### Guild leader rule

The first client in the guild member list is treated as the guild leader. The `/join_guild` command checks against that first member.

---

## 7. GM and Battle Administration

### `/battle_config` (GM)

Change battle settings for the current area. Running `/battle_config` without a parameter lists the accepted parameter names.

**Example**
```
/battle_config critical_rate 20
```

### `/refresh_battle` (GM)

Reset the current battle lobby: selected moves and targets are cleared, the fighter list is emptied, and the battle is marked as not started.

**Example**
```
/refresh_battle
```

### `/remove_fighter` (GM)

Force a fighter to leave. A fighter that has already selected an action is treated as defeated; otherwise it is simply removed from the active fighter list.

**Example**
```
/remove_fighter 42
```

### `/force_skip_move` (GM)

Force a fighter to skip the current turn. This counts as that fighter having selected an action.

**Example**
```
/force_skip_move 42
```

### Battle configuration parameters

| Parameter | Value type | Purpose |
|-----------|-----------|---------|
| paralysis_rate | Positive integer | Controls the random paralysis skip check. |
| critical_rate | Positive integer | Controls the random critical-hit check. |
| critical_bonus | Non-negative float | Multiplier applied to critical damage. |
| bonus_malus | Positive float | Multiplier used by stat buffs and debuffs. |
| poison_damage | Non-negative float; effectively used as divisor | End-of-turn poison damage is max HP divided by this value. |
| show_hp | true / false | Shows or hides HP percentage in battle information. |
| min_multishot | Non-negative integer | Minimum number of shots for multishot. |
| max_multishot | Non-negative integer | Maximum number of shots for multishot. |
| burn_damage | Non-negative float; effectively used as divisor | End-of-turn burn damage is max HP divided by this value. |
| freeze_damage | Non-negative float; effectively used as divisor | End-of-turn freeze damage is max HP divided by this value. |
| confusion_rate | Positive integer | Controls the confusion random roll. |
| enraged_bonus | Non-negative float | Damage multiplier consumed by the next successful attack while enraged. |
| stolen_stat | Positive float | Divisor used to determine how much of a target stat is transferred by steal effects. |

> **Important:** the current implementation rejects a multishot configuration where `min_multishot > max_multishot`. Also note that the implementation parameter is spelled `show_hp`, not "show hp".

---

## 8. Practical Example: One Complete Round

Imagine two fighters are already in the battle. One fighter has move ID `0` = Slash and move ID `1` = Fireball; the opponent has client ID `42`.

**Step 1** — Check your fighter:
```
/info_fighter
```

**Step 2** — Check the battle roster and target IDs:
```
/battle_info
```

**Step 3** — Select a move:
```
/use_move 0 42
```

**Step 4** — The opponent selects their action. When every active fighter has selected an action, the turn starts automatically.

**Step 5** — Actions resolve from highest SPE to lowest SPE. A move can miss, be blocked by paralysis/confusion/sleep/stun, deal damage, apply secondary effects, and then trigger end-of-turn status damage.

**Step 6** — Use `/battle_info` and `/info_fighter` after the round to inspect the new state.

### Common troubleshooting

| Message | Meaning / fix |
|---------|----------------|
| "You have to choose a fighter first!" | Run `/choose_fighter` before entering battle or creating a move. |
| "You are not ready to fight!" | Run `/fight` before selecting a move. |
| "There is no move with that ID!" | Re-run `/info_fighter` and use the numeric move ID shown there. |
| "Your target is not in the fighter list" | Re-run `/battle_info`; the target must currently be an active fighter. |
| "Not enough argument to attack" | Supply a `Target_ID` unless the move is configured with `atkall`. |
| "You don't have enough mana" | Pick a cheaper move or restore/reset the fighter state. |

---

## 9. Command Cheat Sheet

| Command | Typical permission |
|---------|---------------------|
| `/choose_fighter` | Player |
| `/info_fighter` | Player |
| `/create_fighter <...>` | GM |
| `/create_move <...>` | Player / builder |
| `/modify_stat <...>` | GM |
| `/delete_fighter` | GM |
| `/delete_move` | GM |
| `/battle_config` | GM |
| `/fight` | Player |
| `/use_move [Target_ID]` | Player |
| `/battle_info` | Player |
| `/refresh_battle` | GM |
| `/remove_fighter` | GM |
| `/surrender` | Player |
| `/skip_move` | Player |
| `/force_skip_move` | GM |
| `/create_guild` | Player |
| `/info_guild` | Player |
| `/join_guild` | Guild leader |
| `/leave_guild [Target_ID]` | Player / leader / GM |
| `/close_guild [GuildName]` | GM |
| `/battle_effects` | Player |

---

*This guide focuses on the command interface. It intentionally does not define game balance values beyond what can be inferred from the current implementation and configuration parameters.*
