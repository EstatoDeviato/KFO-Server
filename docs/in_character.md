# In-Character Commands

Some features are triggered **inside the in-character (IC) chat box** rather
than as OOC `/` commands. In AO, type the command at the start of an IC
message; the prefix is stripped and the rest is delivered as specified below.

## `/a` - announce to areas you own *(CM+)*

Broadcast an IC message to one or more areas you are a Case Maker of - a
cross-area "announce".

- `/a <msg>` - send `msg` to **every area you own** in the current hub.
- `/a <id(s)> <msg>` - send `msg` to the given comma-separated area IDs, e.g.
  `/a 1,2,3 msg`. You must own every listed area. Area IDs are shown by
  `/area` or in the A/M area list.

Only usable by Case Makers and above for the target areas.

## `/s` - announce to all areas you own *(CM+)*

`/s <msg>` is shorthand for `/a` with no IDs: the message is broadcast to
every area you own in the current hub.

## `/w` - whisper *(everyone, unless the area forbids it)*

Keep an IC message between yourself and specific clients in the same area.

- `/w <msg>` - whisper `msg` to everyone sharing your current position.
- `/w <id(s)> <msg>` - whisper only to the given comma-separated client IDs,
  e.g. `/w 1,2,3 msg`. IDs come from `/getarea` and the clients must be in
  the same area as you.

Anyone may whisper unless the area disables it - with `/area_pref can_whisper
false`, only CMs and above can. Whispered messages are prefixed with `[W]`
for the recipients.

## Testimony markers

Testimony is the witness-statement recording feature driven by the judge
buttons. A testimony is capped at 30 statements.

1. A statement spoken by anyone will be turned into a Witness Testimony Title
   as soon as the Judge presses the **Witness Testimony** button. (It's not
   necessary to put it in --title-- or ==title== or anything like that as the
   system handles this by itself and reposts your message with correct
   formatting.)
2. A Case Maker presses the **Witness Testimony** woosh button. From that
   point every IC message in the area is recorded as a testimony statement.
3. Say a single word, `end`, when everyone has testified. Recording stops.
   (anyone can say the word)
4. When the CM later presses **Cross-Examination**, the testimony is replayed
   and the defense navigates the statements with the markers below.

Navigation (typed in IC while a testimony exists):

- `>` - move to the next statement.
- `<` - move to the previous statement.
- `>N` - jump directly to statement number N, e.g. `>5`.
- `=` - re-show the current statement.

Editing while recording:

- `**msg` - amend the current statement, aka replace it with `msg` in full.
- `++msg` - insert a new statement after the current one.

The navigation and `**`/`++` edits only apply while a testimony is loaded in
the area.
