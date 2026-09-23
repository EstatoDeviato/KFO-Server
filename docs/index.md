# KFO Server Documentation

This site explains [KFO Server](https://github.com/Crystalwarrior/KFO-Server),
the server software behind [Killing Fever Online](https://killingfeveronline.com/).
These pages are made from the server's own files, so they always match the
server as it actually works. (If you are looking for the Community Wiki
instead, please head to [wiki.killingfeveronline.com](https://wiki.killingfeveronline.com/)!)

## The pages on this site

- **[Commands](auto/commands.md)** - every command you can type in the chat
  box for talking out of character (OOC), what each one does, and who may use
  it.
- **[Area Prefs](auto/prefs.md)** - the small settings you can turn on or off
  for one area (`/area_pref`), what each one does, and who is allowed to
  change it.
- **[Hub Prefs](auto/hub_prefs.md)** - the same kind of settings, but for a
  whole hub at once, plus the command that changes each one.
- **[In-Character Commands](in_character.md)** - things you type inside the
  in-character chat while playing, such as `/a`, `/s`, `/w` and the testimony
  markers.
- **[Demo Scripting](demo_scripting.md)** - how to set up recorded scenes
  ("demos") and automatic triggers.

## How to read a command

On the [Commands](auto/commands.md) page:

- `<>` means you must fill it in. `[]` means you can leave it out. You don't
  type the brackets themselves.
- The tag in parentheses tells you who may use the command: *(CM)* means Case
  Makers and above, *(GM)* means Game Masters and above, *(Mod)* means
  moderators only. No tag means everyone can use it.
- Some commands have other names too. Those come from
  [`config/command_aliases.yaml`](https://github.com/Killing-Fever-Online/KFO-Server/blob/config_sample/command_aliases.yaml)
  and can differ from server to server, so only the real name is shown here.

In the game, type `/help <command>` to see the description again.

## Want to help improve these pages?

The descriptions come from the files that make the server:

- To fix a command's text, edit its description in [`server/commands`](https://github.com/Killing-Fever-Online/KFO-Server/blob/master/server/commands).
- To fix a setting's text, edit its description in [`server/schema/area_fields.py`](https://github.com/Killing-Fever-Online/KFO-Server/blob/master/server/schema/area_fields.py).

Then run `python scripts/generate_docs.py` to bring the pages back in line.

To look at the site on your own computer, do the same two steps the README
explains: run `python scripts/generate_docs.py`, then run
`venv\Scripts\python.exe -m mkdocs serve` (or `venv/bin/python -m mkdocs serve`
on Linux) and open the link it shows you in your browser.
