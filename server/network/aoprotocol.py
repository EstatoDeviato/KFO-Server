# tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import re
import unicodedata

import logging

logger_debug = logging.getLogger('debug')
logger = logging.getLogger('events')

from enum import Enum

import arrow
from time import localtime, strftime

from server import database
from server.exceptions import ClientError, AreaError, ArgumentError, ServerError
from server.fantacrypt import fanta_decrypt
from .. import commands


class AOProtocol(asyncio.Protocol):
    """The main class that deals with the AO protocol."""

    class ArgType(Enum):
        """Represents the data type of an argument for a network command."""
        STR = 1,
        STR_OR_EMPTY = 2,
        INT = 3,
        INT_OR_STR = 3

    def __init__(self, server):
        super().__init__()
        self.server = server
        self.client = None
        self.buffer = ''
        self.ping_timeout = None

    def dezalgo(self, input):
        """
        Turns any string into a de-zalgo'd version, with a tolerance to allow for normal diacritic use.

        The following Unicode blocks are scrubbed:
        U+0300 - U+036F - COMBINING DIACRITICAL MARKS
        U+1AB0 - U+1AFF - COMBINING DIACRITICAL MARKS EXTENDED
        U+1DC0 - U+1DFF - COMBINING DIACRITICAL MARKS SUPPLEMENT
        U+20D0 - U+20FF - COMBINING DIACRITICAL MARKS FOR SYMBOLS
        U+FE20 - U+FE2F - COMBINING HALF MARKS
        """

        filtered = re.sub('([\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]' +
                          '{' + re.escape(str(self.server.zalgo_tolerance)) + ',})',
                          '', input)
        return filtered

    def data_received(self, data):
        """Handles any data received from the network.
        
        Receives data, parses them into a command and passes it
        to the command handler.

        :param data: bytes of data

        """
        buf = data
        ipid = self.client.ipid

        if buf is None:
            buf = b''

        if not isinstance(buf, str):
            # try to decode as utf-8, ignore any erroneous characters
            self.buffer += buf.decode('utf-8', 'ignore')
        else:
            self.buffer = buf

        self.buffer = self.buffer.translate({ord(c): None for c in '\0'})

        if len(self.buffer) > 8192:
            self.client.disconnect()
        for msg in self.get_messages():
            if len(msg) < 2:
                continue
            # general netcode structure is not great
            if msg[0] in ('#', '3', '4'):
                if msg[0] == '#':
                    msg = msg[1:]
                spl = msg.split('#', 1)
                msg = '#'.join([fanta_decrypt(spl[0])] + spl[1:])
            try:
                cmd, *args = msg.split('#')
                self.net_cmd_dispatcher[cmd](self, args)
            except KeyError:
                logger_debug.debug(f'Unknown incoming message from {ipid}: {msg}')

    def connection_made(self, transport):
        """Called upon a new client connecting

        :param transport: the transport object
        """
        try:
            self.client = self.server.new_client(transport)
        except ClientError:
            transport.close()
            return

        if not self.server.client_manager.new_client_preauth(self.client):
            self.client.send_command('BD', 'Maximum clients reached.\nDisconnect one of your clients to continue.')
            self.client.disconnect()
            return

        # Client needs to send CHECK#% within the timeout - otherwise,
        # it will be automatically dropped.
        self.ping_timeout = asyncio.get_event_loop().call_later(
            self.server.config['timeout'], self.client.disconnect)

        asyncio.get_event_loop().call_later(0.25, self.client.send_command,
                                            'decryptor',
                                            34)  # just fantacrypt things)

    def connection_lost(self, exc):
        """User disconnected

        :param exc: reason

        """
        if self.client is not None:
            logger.debug(f'{self.client.ipid} disconnected.')
            self.server.remove_client(self.client)
        if self.ping_timeout is not None:
            self.ping_timeout.cancel()

    def get_messages(self):
        """Parses out full messages from the buffer.

        :return: yields messages

        """
        while '#%' in self.buffer:
            spl = self.buffer.split('#%', 1)
            self.buffer = spl[1]
            yield spl[0]

    def validate_net_cmd(self, args, *types, needs_auth=True):
        """Makes sure the net command's arguments match expectations.

        :param args: actual arguments to the net command
        :param types: what kind of data types are expected
        :param needs_auth: whether you need to have chosen a character (Default value = True)
        :param *types: list of types corresponding to each argument in the command
        :returns: returns True if message was validated

        """
        if needs_auth and self.client.char_id == -1:
            return False
        if len(args) != len(types):
            return False
        for i, arg in enumerate(args):
            if len(str(arg)) == 0 and types[i] != self.ArgType.STR_OR_EMPTY:
                return False
            if types[i] == self.ArgType.INT:
                try:
                    args[i] = int(arg)
                except ValueError:
                    return False
        return True

    def net_cmd_hi(self, args):
        """Handshake.

        HI#<hdid:string>#%

        :param args: a list containing all the arguments

        """
        if not self.validate_net_cmd(args, self.ArgType.STR, needs_auth=False):
            return
        hdid = self.client.hdid = args[0]
        ipid = self.client.ipid

        database.add_hdid(ipid, hdid)
        ban = database.find_ban(ipid, hdid)
        if ban is not None:
            if ban.unban_date is not None:
                unban_date = arrow.get(ban.unban_date)
            else:
                unban_date = 'N/A'

            msg = f'{ban.reason}\r\n'
            msg += f'ID: {ban.ban_id}\r\n'
            msg += f'Until: {unban_date.humanize()}'

            database.log_connect(self.client, failed=True)
            self.client.send_command('BD', msg)
            self.client.disconnect()
            return
        else:
            self.client.is_checked = True

        database.log_connect(self.client, failed=False)
        self.client.send_command('ID', self.client.id, self.server.software,
                                 self.server.version)
        self.client.send_command('PN',
                                 self.server.player_count,
                                 self.server.config['playerlimit'])

    def net_cmd_id(self, args):
        """Client version and PV

        ID#<pv:int>#<software:string>#<version:string>#%
        """
        self.client.version = args[1]
        preflist = self.client.server.supported_features.copy()
        if not self.client.area.area_manager.arup_enabled and 'arup' in preflist:
            preflist.remove('arup')
        self.client.send_command('FL', preflist)

    def net_cmd_ch(self, _):
        """Reset the client drop timeout (keepalive).

        CHECK#%
        """
        self.client.send_command('CHECK')
        self.ping_timeout.cancel()
        self.ping_timeout = asyncio.get_event_loop().call_later(
            self.server.config['timeout'], self.client.disconnect)

    def net_cmd_askchaa(self, _):
        """Ask for the counts of characters/evidence/music

        askchaa#%
        """
        char_cnt = len(self.server.char_list)
        evi_cnt = 0
        music_cnt = sum([len(x) for x in self.server.music_pages_ao1])
        self.client.send_command('SI', char_cnt, evi_cnt, music_cnt)

    def net_cmd_askchar2(self, _):
        """Asks for the character list. (AO1)

        askchar2#%
        """
        self.client.send_command('CI', *self.server.char_pages_ao1[0])

    def net_cmd_an(self, args):
        """Asks for specific pages of the character list.
        (AO1 only; part of askchar2 sequence)

        AN#<page:int>#%
        """
        if not self.validate_net_cmd(args, self.ArgType.INT, needs_auth=False):
            return
        if len(self.server.char_pages_ao1) > args[0] >= 0:
            self.client.send_command('CI',
                                     *self.server.char_pages_ao1[args[0]])
        else:
            self.client.send_command('EM', *self.server.music_pages_ao1[0])

    def net_cmd_ae(self, _):
        """Asks for specific pages of the evidence list.
        (AO1 only; part of askchar2 sequence)

        AE#<page:int>#%

        """
        pass  # todo evidence maybe later

    def net_cmd_am(self, args):
        """Asks for specific pages of the music list.
        (AO1 only; part of askchar2 sequence)

        AM#<page:int>#%

        """
        if not self.validate_net_cmd(args, self.ArgType.INT, needs_auth=False):
            return
        if len(self.server.music_pages_ao1) > args[0] >= 0:
            self.client.send_command('EM',
                                     *self.server.music_pages_ao1[args[0]])
        else:
            self.client.send_done()
            self.client.send_area_list()
            self.client.send_motd()
            self.client.send_hub_info()

    def net_cmd_rc(self, _):
        """Asks for the whole character list (AO2)

        AC#%

        """

        self.client.send_command('SC', *self.server.char_list)

    def net_cmd_rm(self, _):
        """Asks for the whole music list (AO2)

        AM#%

        """

        song_list = []
        allowed = self.client.is_mod or self.client in self.client.area.owners
        area_list = self.client.get_area_list(allowed, allowed)
        self.client.local_area_list = area_list
        song_list += [a.name for a in area_list]
        self.client.local_music_list = self.server.music_list
        song_list += self.server.music_list_ao2

        self.client.send_command('SM', *song_list)

    def net_cmd_rd(self, _):
        """Asks for server metadata(charscheck, motd etc.) and a DONE#% signal(also best packet)

        RD#%

        """

        self.client.send_done()
        self.client.send_area_list()
        self.client.send_motd()
        self.client.send_hub_info()
        # TODO: move this code to the area itself so it can handle whatever it needs to later
        if self.client.area.music_autoplay:
            self.client.send_command('MC', self.client.area.current_music, -1, '', self.client.area.current_music_looping, 0, self.client.area.current_music_effects)

    def net_cmd_cc(self, args):
        """Character selection.

        CC#<client_id:int>#<char_id:int>#<hdid:string>#%

        """
        if not self.validate_net_cmd(args,
                                     self.ArgType.INT,
                                     self.ArgType.INT,
                                     self.ArgType.STR,
                                     needs_auth=False):
            return
        elif not self.client.is_checked:
            return

        cid = args[1]
        try:
            self.client.change_character(cid)
        except ClientError:
            return

    def net_cmd_ms(self, args):
        """IC message.

        Refer to the implementation for details.

        """
        if not self.client.is_checked:
            return
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You are muted by a moderator.')
            return

        showname = ""
        charid_pair = -1
        offset_pair = 0
        nonint_pre = 0
        sfx_looping = "0"
        screenshake = 0
        frames_shake = ""
        frames_realization = ""
        frames_sfx = ""
        additive = 0
        effect = ""
        pair_order = 0
        if self.validate_net_cmd(args, self.ArgType.STR, # msg_type
                                 self.ArgType.STR_OR_EMPTY, self.ArgType.STR,   # pre, folder
                                 self.ArgType.STR, self.ArgType.STR,            # anim, text
                                 self.ArgType.STR, self.ArgType.STR,            # pos, sfx
                                 self.ArgType.INT, self.ArgType.INT,            # anim_type, cid
                                 self.ArgType.INT, self.ArgType.INT_OR_STR,     # sfx_delay, button
                                 self.ArgType.INT, self.ArgType.INT,            # evidence, flip
                                 self.ArgType.INT, self.ArgType.INT,            # ding, color
            ):
            # Pre-2.6 validation monstrosity.
            msg_type, pre, folder, anim, text, pos, sfx, anim_type, cid, sfx_delay, button, evidence, flip, ding, color = args
        elif self.validate_net_cmd(
                args, self.ArgType.STR, self.ArgType.STR_OR_EMPTY,              # msg_type, pre
                self.ArgType.STR, self.ArgType.STR, self.ArgType.STR,           # folder, anim, text
                self.ArgType.STR, self.ArgType.STR, self.ArgType.INT,           # pos, sfx, anim_type
                self.ArgType.INT, self.ArgType.INT, self.ArgType.INT_OR_STR,    # cid, sfx_delay, button
                self.ArgType.INT, self.ArgType.INT, self.ArgType.INT,           # evidence, flip, ding
                self.ArgType.INT, self.ArgType.STR_OR_EMPTY, self.ArgType.INT,  # color, showname, charid_pair
                self.ArgType.INT, self.ArgType.INT,                             # offset_pair, nonint_pre
            ):
            # 2.6 validation monstrosity.
            msg_type, pre, folder, anim, text, pos, sfx, anim_type, cid, sfx_delay, button, evidence, flip, ding, color, showname, charid_pair, offset_pair, nonint_pre = args
        elif self.validate_net_cmd(
                args, self.ArgType.STR, self.ArgType.STR_OR_EMPTY,              # msg_type, pre
                self.ArgType.STR, self.ArgType.STR, self.ArgType.STR,           # folder, anim, text
                self.ArgType.STR, self.ArgType.STR, self.ArgType.INT,           # pos, sfx, anim_type
                self.ArgType.INT, self.ArgType.INT, self.ArgType.INT_OR_STR,    # cid, sfx_delay, button
                self.ArgType.INT, self.ArgType.INT, self.ArgType.INT,           # evidence, flip, ding
                self.ArgType.INT, self.ArgType.STR_OR_EMPTY, self.ArgType.STR,  # color, showname, charid_pair
                self.ArgType.INT, self.ArgType.INT, self.ArgType.STR,           # offset_pair, nonint_pre, sfx_looping
                self.ArgType.INT, self.ArgType.STR, self.ArgType.STR,           # screenshake, frames_shake, frames_realization
                self.ArgType.STR, self.ArgType.INT, self.ArgType.STR,           # frames_sfx, additive, effect
            ):
            # 2.8 validation monstrosity. (rip 2.7)
            msg_type, pre, folder, anim, text, pos, sfx, anim_type, cid, sfx_delay, button, evidence, flip, ding, color, showname, charid_pair, offset_pair, nonint_pre, sfx_looping, screenshake, frames_shake, frames_realization, frames_sfx, additive, effect = args
            pair_args = charid_pair.split("^")
            charid_pair = int(pair_args[0])
            if (len(pair_args) > 1):
                pair_order = pair_args[1]
        else:
            return

        # Targets for whispering
        whisper_clients = None

        target_area = []
        if self.client.is_mod or self.client in self.client.area.owners:
            target_area = self.client.broadcast_list.copy()

        if len(showname) > 0 and not self.client.area.showname_changes_allowed and not self.client.is_mod and not (self.client in self.client.area.owners):
            self.client.send_ooc(
                "Showname changes are forbidden in this area!")
            return
        if self.client.area.is_iniswap(self.client, pre, anim,
                folder, sfx):
            self.client.send_ooc("Iniswap/custom emotes are blocked in this area")
            return
        if len(self.client.charcurse) > 0 and \
            folder != self.client.char_name:
            self.client.send_ooc(
                "You may not iniswap while you are charcursed!")
            return
        if not self.client.area.blankposting_allowed:
            if text == ' ':
                self.client.send_ooc(
                    "Blankposting is forbidden in this area!")
                return
            if text.isspace():
                self.client.send_ooc(
                    "Blankposting is forbidden in this area, and putting more spaces in does not make it not blankposting."
                )
                return
            if len(re.sub(r'[{}\\`|(~~)]', '', text).replace(
                    ' ', '')) < 3 and text != '<' and text != '>':
                self.client.send_ooc(
                    "While that is not a blankpost, it is still pretty spammy. Try forming sentences."
                )
                return
        if text.lstrip().startswith('(('):
            self.client.send_ooc("Please, *please* use the OOC chat instead of polluting IC. Normal OOC is local to area. You can use /g to talk across the entire server.")
            return
        if text.lower().startswith('/a ') or text.lower().startswith('/s '):
            part = text.split(' ')
            try:
                areas = part[1].split(',')
                for a in areas:
                    try:
                        aid = int(a)
                    except ValueError:
                        break
                    area = self.client.area.area_manager.get_area_by_id(aid)
                    if self.client in area.owners:
                        target_area.append(area)
                    else:
                        self.client.send_ooc(f'You don\'t own {area.name}!')
                        return
                if len(target_area) <= 0:
                    for a in self.client.area.area_manager.areas:
                        if self.client in a.owners:
                            target_area.append(a)
                    part = part[1:]
                else:
                    part = part[2:]
                if len(target_area) <= 0:
                    self.client.send_ooc('No target areas found!')
                    return
                text = ' '.join(part)
            except (ValueError, AreaError):
                self.client.send_ooc(
                    "That does not look like a valid area ID!")
                return
        if len(self.client.area.testimony) > 0 and (text.lstrip().startswith('>') or text.lstrip().startswith('<')):
            if self.client.area.recording == True:
                self.client.send_ooc('It is not cross-examination yet!')
                return
            cmd = text.strip()
            idx = self.client.area.testimony_index
            if len(cmd) > 1:
                try:
                    idx = int(cmd[1:])-1
                    if idx <= -1:
                        raise ValueError
                except ValueError:
                    self.client.send_ooc('Invalid index!')
                    return
            else:
                if cmd == '>':
                    idx += 1
                if cmd == '<':
                    idx -= 1
                idx = idx % len(self.client.area.testimony)
                self.client.area.testimony_index = idx
            try:
                self.client.area.testimony_send(idx)
                self.client.area.broadcast_ooc(f'{self.client.char_name} has moved to Statement {idx+1}.')
            except:
                self.client.send_ooc('Invalid index!')
            return
        if msg_type not in ('chat', '0', '1'):
            return
        if anim_type not in (0, 1, 2, 4, 5, 6):
            return
        if cid != self.client.char_id:
            return
        if sfx_delay < 0:
            return
        if '4' in str(button) and "<and>" not in str(button):
            if not button.isdigit():
               return
        if evidence < 0:
            return
        if ding not in (0, 1):
            return
        if color >= 12:
            return
        if len(showname) > 15:
            self.client.send_ooc("Your IC showname is way too long!")
            return
        if nonint_pre == 1:
            if button in range(1, 4):
                if anim_type == 1 or anim_type == 2:
                    anim_type = 0
                elif anim_type == 6:
                    anim_type = 5
        if self.client.area.non_int_pres_only:
            if anim_type == 1 or anim_type == 2:
                anim_type = 0
            elif anim_type == 6:
                anim_type = 5
            nonint_pre = 1
        if not self.client.area.shouts_allowed:
            # Old clients communicate the objecting in anim_type.
            if anim_type == 2:
                anim_type = 1
            elif anim_type == 6:
                anim_type = 5
            # New clients do it in a specific objection message area.
            button = 0
            # Turn off the ding.
            ding = 0
        if int(button) <= 0 and not self.client.area.can_send_message(self.client):
            return
        max_char = 0
        try:
            max_char = int(self.server.config['max_chars'])
        except:
            max_char = 256

        if len(text) > max_char:
            return

        if pos != '' and self.client.pos != pos:
            try:
                self.client.change_position(pos)
            except ClientError:
                pos = ''
        if len(self.client.area.pos_lock) > 0 and pos not in self.client.area.pos_lock:
            pos = self.client.area.pos_lock[0]

        if text.lower().startswith('/w ') or text.lower().startswith('[w] '):
            if not self.client.area.can_whisper and not self.client.is_mod and not self.client in self.client.area.owners:
                self.client.send_ooc(
                    "You can't whisper in this area!")
                return
            part = text.split(' ')
            try:
                clients = part[1].split(',')
                try:
                    [int(c) for c in clients]
                except ValueError:
                    clients = []
                
                if len(clients) > 0:
                    part = part[2:]
                    whisper_clients = [c for c in self.client.area.clients if str(c.id) in clients]
                    clients = ','.join(clients)
                else:
                    part = part[1:]
                    whisper_clients = [c for c in self.client.area.clients if c.pos == self.client.pos]
                    clients = ''
                text = ' '.join(part)
                text = "}}}[W" + clients + "] {{{" + text
            except (ValueError, AreaError):
                self.client.send_ooc(
                    "Invalid targets!")
                return

        msg = self.dezalgo(text)[:256]
        if self.client.shaken:
            msg = self.client.shake_message(msg)
        if self.client.disemvowel:
            msg = self.client.disemvowel_message(msg)
        if evidence:
            evi = self.client.area.evi_list.evidences[
                    self.client.evi_list[evidence] - 1]

            if evi.hiding_client != None:
                c = evi.hiding_client
                c.hide(False)
                c.area.broadcast_area_list(c)
                self.client.send_ooc(f'You discover {c.char_name} in the {evi.name}!')

            if evi.pos != 'all':
                evi.pos = 'all'
                self.client.area.broadcast_evidence_list()

        # Here, we check the pair stuff, and save info about it to the client.
        # Notably, while we only get a charid_pair and an offset, we send back a chair_pair, an emote, a talker offset
        # and an other offset.

        self.client.charid_pair = charid_pair
        self.client.offset_pair = offset_pair
        if anim_type not in (5, 6):
            self.client.last_sprite = anim
        self.client.flip = flip
        self.client.claimed_folder = folder
        other_offset = 0
        other_emote = ''
        other_flip = 0
        other_folder = ''

        confirmed = False
        if charid_pair > -1:
            for target in self.client.area.clients:
                if not confirmed and target.char_id == self.client.charid_pair and target.charid_pair == self.client.char_id and target != self.client and target.pos == self.client.pos:
                    confirmed = True
                    other_offset = target.offset_pair
                    other_emote = target.last_sprite
                    other_flip = target.flip
                    other_folder = target.claimed_folder
                    if (pair_order != ""):
                        charid_pair = "{}^{}".format(charid_pair, pair_order)
                    break

        if not confirmed:
            charid_pair = -1

        if whisper_clients != None:
            whisper_clients.insert(0, self.client)
            for client in self.client.area.clients:
                if client in whisper_clients:
                    continue
                if client in self.client.area.owners:
                    whisper_clients.append(client)
                if client.is_mod:
                    whisper_clients.append(client)

        if len(target_area) > 0:
            try:
                for a in target_area:
                    add = additive
                    if a.last_ic_message == None or cid != a.last_ic_message[8]:
                        add = 0
                    a.send_command('MS', msg_type, pre, folder, anim, msg, pos, sfx,
                        anim_type, cid, sfx_delay, button, self.client.evi_list[evidence],
                        flip, ding, color, showname, charid_pair, other_folder,
                        other_emote, offset_pair, other_offset, other_flip, nonint_pre,
                        sfx_looping, screenshake, frames_shake, frames_realization,
                        frames_sfx, add, effect)
                a_list = ', '.join([str(a.id) for a in target_area])
                if not (self.client.area in target_area):
                    if msg == '':
                        msg = ' '
                    self.client.send_command('MS', msg_type, pre, folder, anim, '}}}[' + a_list + '] {{{' + msg, pos, sfx,
                        anim_type, cid, sfx_delay, button, self.client.evi_list[evidence],
                        flip, ding, color, showname, charid_pair, other_folder,
                        other_emote, offset_pair, other_offset, other_flip, nonint_pre,
                        sfx_looping, screenshake, frames_shake, frames_realization,
                        frames_sfx, add, effect)
                self.client.send_ooc(f'Broadcasting to areas {a_list}')
            except (AreaError, ValueError):
                self.client.send_ooc('Your broadcast list is invalid! Do /clear_broadcast to reset it and /broadcast <id(s)> to set a new one.')
            return

        # If we are not whispering...
        if whisper_clients == None:
            # Reveal ourselves from the evidence we were hiding in if it exists
            if self.client.hidden_in != None:
                self.client.hide(False)
                self.client.area.broadcast_area_list(client)

        # Additive only works on same-char messages
        if self.client.area.last_ic_message == None or cid != self.client.area.last_ic_message[8]:
            additive = 0
        self.client.area.send_ic(self.client, msg_type, pre, folder, anim, msg,
                                pos, sfx, anim_type, cid, sfx_delay,
                                button, self.client.evi_list[evidence],
                                flip, ding, color, showname, charid_pair,
                                other_folder, other_emote, offset_pair,
                                other_offset, other_flip, nonint_pre,
                                sfx_looping, screenshake, frames_shake,
                                frames_realization, frames_sfx,
                                additive, effect, targets=whisper_clients)

        self.client.area.send_owner_command(
            'MS', msg_type, pre, folder, anim,
            '}}}[' + str(self.client.area.id) + '] {{{' + msg, pos, sfx,
            anim_type, cid, sfx_delay, button, self.client.evi_list[evidence],
            flip, ding, color, showname, charid_pair, other_folder,
            other_emote, offset_pair, other_offset, other_flip, nonint_pre,
            sfx_looping, screenshake, frames_shake, frames_realization,
            frames_sfx, additive, effect)

    def net_cmd_ct(self, args):
        """OOC Message

        CT#<name:string>#<message:string>#%

        """

        if not self.client.is_checked:
            return
        if self.client.is_ooc_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You are muted by a moderator.')
            return
        if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.STR, needs_auth=False):
            return
        if self.client.name != args[0] and self.client.fake_name != args[0]:
            if self.client.is_valid_name(args[0]):
                self.client.name = args[0]
                self.client.fake_name = args[0]
            else:
                self.client.fake_name = args[0]
        if self.client.name == '':
            self.client.send_ooc(
                'You must insert a name with at least one letter')
            return
        if len(self.client.name) > 30:
            self.client.send_ooc(
                'Your OOC name is too long! Limit it to 30 characters.')
            return
        for c in self.client.name:
            if unicodedata.category(c) == 'Cf':
                self.client.send_ooc(
                    'You cannot use format characters in your name!')
                return
        if self.client.name.startswith(
                self.server.config['hostname']) or self.client.name.startswith(
                    '<dollar>G') or self.client.name.startswith('<dollar>M'):
            self.client.send_ooc('That name is reserved!')
            return
        if args[1].startswith(' /'):
            self.client.send_ooc(
                'Your message was not sent for safety reasons: you left a space before that slash.')
            return
        if args[1].startswith('/'):
            spl = args[1][1:].split(' ', 1)
            cmd = spl[0].lower()
            arg = ''
            if len(spl) == 2:
                arg = spl[1][:256]
            try:
                called_function = f'ooc_cmd_{cmd}'
                if not hasattr(commands, called_function):
                    self.client.send_ooc('Invalid command.')
                else:
                    getattr(commands, called_function)(self.client, arg)
            except (ClientError, AreaError, ArgumentError, ServerError) as ex:
                self.client.send_ooc(ex)
            except Exception as ex:
                self.client.send_ooc('An internal error occurred. Please check the server log.')
                logger.exception('Exception while running a command')
            return

        max_char = 0
        try:
            max_char = int(self.server.config['max_chars'])
        except:
            max_char = 256
        if len(args[1]) > max_char:
            self.client.send_ooc('Your message is too long!')
            return

        args[1] = self.dezalgo(args[1])
        if self.client.shaken:
            args[1] = self.client.shake_message(args[1])
        if self.client.disemvowel:
            args[1] = self.client.disemvowel_message(args[1])
        self.client.area.send_command('CT', self.client.name, args[1])
        self.client.area.send_owner_command(
            'CT',
            f'[{self.client.area.id}]{self.client.name}',
            args[1])
        database.log_room('ooc', self.client, self.client.area, message=args[1])

    def net_cmd_mc(self, args):
        """Play music.

        MC#<song_name:str>#<char_id:int>#<show_name:str_or_empty>#<effects:int>#%

        """
        if not self.client.is_checked:
            return
        try:
            called_function = 'ooc_cmd_area'
            # We can get cheeky and spoof ARUP info with normal song names
            getattr(commands, called_function)(self.client, args[0].split('\n')[0])
        except AreaError:
            if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.INT):
                if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.INT, self.ArgType.STR_OR_EMPTY):
                    if not self.validate_net_cmd(args, self.ArgType.STR, self.ArgType.INT, self.ArgType.STR_OR_EMPTY, self.ArgType.INT):
                        return
            self.client.change_music(args)
        except ClientError as ex:
            self.client.send_ooc(ex)

    def net_cmd_rt(self, args):
        """Plays the Testimony/CE animation.

        RT#<type:string>#%

        """
        if not self.client.is_checked:
            return
        if not self.client.area.shouts_allowed:
            self.client.send_ooc(
                "You cannot use the testimony buttons here!")
            return
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You are muted by a moderator.')
            return
        if not self.client.can_wtce:
            self.client.send_ooc(
                'You were blocked from using judge signs by a moderator.')
            return
        if not self.client.area.can_wtce and not self.client.is_mod and not self in self.client.area.owners:
            self.client.send_ooc(
                'Only CMs and mods may use judge buttons in this area!')
            return
        if self.client.area.cannot_ic_interact(self.client):
            self.client.send_ooc(
                "You are not on the area's invite list, and thus, you cannot use the WTCE buttons!"
            )
            return
        if not self.validate_net_cmd(
                args, self.ArgType.STR) and not self.validate_net_cmd(
                    args, self.ArgType.STR, self.ArgType.INT):
            return
        if args[0] == 'testimony1':
            sign = 'WT'
        elif args[0] == 'testimony2':
            sign = 'CE'
        elif args[0] == 'judgeruling':
            sign = 'JR'
        else:
            return
        if self.client.wtce_mute():
            self.client.send_ooc(
                f'You used witness testimony/cross examination signs too many times. Please try again after {int(self.client.wtce_mute())} seconds.')
            return

        if len(self.client.broadcast_list) > 0:
            try:
                a_list = ', '.join([str(a.id) for a in self.client.broadcast_list])
                self.client.send_ooc(f'Broadcasting to areas {a_list}')
                if len(args) == 1:
                    self.client.area.area_manager.send_remote_command(self.client.broadcast_list, 'RT', args[0])
                elif len(args) == 2:
                    self.client.area.area_manager.send_remote_command(self.client.broadcast_list, 'RT', args[0], args[1])
            except (AreaError, ValueError):
                self.client.send_ooc('Your broadcast list is invalid! Do /clear_broadcast to reset it and /broadcast <id(s)> to set a new one.')
                return

        if len(args) == 1:
            self.client.area.send_command('RT', args[0])
        elif len(args) == 2:
            self.client.area.send_command('RT', args[0], args[1])
        self.client.area.add_to_judgelog(self.client, f'used {sign}')
        database.log_room('wtce', self.client, self.client.area, message=sign)

        if self.client in self.client.area.owners:
            if self.client.area.last_ic_message != None and sign == 'WT':
                # remove centering chars and strip space chars
                msg = self.client.area.last_ic_message[4].replace('~', '').strip()
                if msg.startswith('--') and msg.endswith('--'):
                    msg = msg.replace('-', '')
                    msg = msg.strip()
                    # actual title possible lol!
                    if len(msg) > 0:
                        self.client.area.testimony.clear()
                        self.client.area.testimony_index = -1
                        self.client.area.testimony_title = msg
                        self.client.area.recording = True
                        self.client.area.broadcast_ooc(f'-- {self.client.area.testimony_title} --\nTestimony recording started! All new messages will be recorded as testimony lines. Say "End" to stop recording.')
                        return
            if sign == 'CE':
                if self.client.area.recording:
                    self.client.area.recording = False
                    self.client.area.broadcast_ooc('Testimony recording stopped!')
                # Display the testimony title
                if len(self.client.area.testimony) > 0:
                    statement = self.client.area.testimony[0]
                    lst = list(statement)
                    # See if the testimony is supposed to end here.

                    # Center it and make it speedy
                    lst[4] = "~~}}-- " + self.client.area.testimony_title + " --"

                    # Make it orange
                    lst[14] = 3
                    statement = tuple(lst)
                    targets = self.client.area.clients
                    for c in targets:
                        # Blinded clients don't receive IC messages
                        if c.blinded:
                            continue
                        # Ignore those losers with listenpos for testimony
                        c.send_command('MS', *statement)

    def net_cmd_setcase(self, args):
        """Sets the casing preferences of the given client.

        SETCASE#<cases:string>#<will_cm:int>#<will_def:int>#<will_pro:int>#<will_judge:int>#<will_jury:int>#<will_steno:int>#%

        Note: Though all but the first arguments are ints, they technically behave as bools of 0 and 1 value.

        """
        self.client.casing_cases = args[0]
        self.client.casing_cm = args[1] == "1"
        self.client.casing_def = args[2] == "1"
        self.client.casing_pro = args[3] == "1"
        self.client.casing_jud = args[4] == "1"
        self.client.casing_jur = args[5] == "1"
        self.client.casing_steno = args[6] == "1"

    def net_cmd_casea(self, args):
        """Announces a case with a title, and specific set of people to look for.

        CASEA#<casetitle:string>#<need_cm:int>#<need_def:int>#<need_pro:int>#<need_judge:int>#<need_jury:int>#<need_steno:int>#%

        Note: Though all but the first arguments are ints, they technically behave as bools of 0 and 1 value.

        """
        if not self.client.is_checked:
            return
        if self.client in self.client.area.owners:
            if not self.client.can_call_case():
                self.client.send_ooc(
                    'Please wait 60 seconds between case announcements!')
                return

            if not args[1] == "1" and not args[2] == "1" and not args[
                    3] == "1" and not args[4] == "1" and not args[5] == "1":
                self.client.send_ooc(
                    'You should probably announce the case to at least one person.'
                )
                return
            msg = '=== Case Announcement ===\r\n{} [{}] is hosting {}, looking for '.format(
                self.client.char_name, self.client.id, args[0])

            lookingfor = [p for p, q in
                zip(['defense', 'prosecutor', 'judge', 'juror', 'stenographer'], args[1:])
                if q == '1']

            msg += ', '.join(lookingfor) + '.\r\n=================='

            self.client.server.send_all_cmd_pred('CASEA', msg, args[1],
                                                 args[2], args[3], args[4],
                                                 args[5], '1')

            self.client.set_case_call_delay()

            log_data = {k: v for k, v in
                zip(('message', 'def', 'pro', 'jud', 'jur', 'steno'), args)}
            database.log_room('case', self.client, self.client.area, message=log_data)
        else:
            self.client.send_ooc('You cannot announce a case in an area where you are not a CM!')

    def net_cmd_hp(self, args):
        """Sets the penalty bar.

        HP#<type:int>#<new_value:int>#%

        """
        if not self.client.is_checked:
            return
        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You are muted by a moderator.')
            return
        if self.client.area.cannot_ic_interact(self.client):
            self.client.send_ooc(
                "You are not on the area's invite list, and thus, you cannot change the Confidence bars!"
            )
            return
        if not self.validate_net_cmd(args, self.ArgType.INT, self.ArgType.INT):
            return
        try:
            self.client.area.change_hp(args[0], args[1])
            self.client.area.add_to_judgelog(self.client,
                                             'changed the penalties')
            database.log_room('hp', self.client, self.client.area)
        except AreaError:
            return

    def net_cmd_pe(self, args):
        """Adds a piece of evidence.

        PE#<name: string>#<description: string>#<image: string>#%

        :param args:

        """
        if not self.client.is_checked:
            return
        if not self.validate_net_cmd(args, self.ArgType.STR_OR_EMPTY, self.ArgType.STR_OR_EMPTY, self.ArgType.STR_OR_EMPTY):
            return
        if len(args) < 3:
            return
        # evi = Evidence(args[0], args[1], args[2], self.client.pos)
        self.client.area.evi_list.add_evidence(self.client, args[0], args[1],
                                               args[2], 'all')
        database.log_room('evidence.add', self.client, self.client.area)
        self.client.area.broadcast_evidence_list()

    def net_cmd_de(self, args):
        """Deletes a piece of evidence.

        DE#<id: int>#%

        """
        if not self.client.is_checked:
            return
        if not self.validate_net_cmd(args, self.ArgType.INT):
            return
        self.client.area.evi_list.del_evidence(
            self.client, self.client.evi_list[int(args[0])])
        database.log_room('evidence.del', self.client, self.client.area)
        self.client.area.broadcast_evidence_list()

    def net_cmd_ee(self, args):
        """Edits a piece of evidence.

        EE#<id: int>#<name: string>#<description: string>#<image: string>#%

        """
        if not self.client.is_checked:
            return
        if not self.validate_net_cmd(args, self.ArgType.INT, self.ArgType.STR_OR_EMPTY, self.ArgType.STR_OR_EMPTY, self.ArgType.STR_OR_EMPTY):
            return
        elif len(args) < 4:
            return

        evi = (args[1], args[2], args[3], 'all')

        self.client.area.evi_list.edit_evidence(
            self.client, self.client.evi_list[int(args[0])], evi)
        database.log_room('evidence.edit', self.client, self.client.area)
        self.client.area.broadcast_evidence_list()

    def net_cmd_zz(self, args):
        """Sent on mod call.

        """
        if not self.client.is_checked:
            return

        if self.client.is_muted:  # Checks to see if the client has been muted by a mod
            self.client.send_ooc('You are muted by a moderator.')
            return

        if self.client.char_id == -1:
            self.client.send_ooc(
                "You cannot call a moderator while spectating.")
            return

        if not self.client.can_call_mod():
            self.client.send_ooc(
                "You must wait 30 seconds between mod calls.")
            return

        current_time = strftime("%H:%M", localtime())

        if len(args) < 1:
            self.server.send_all_cmd_pred(
                'ZZ',
                '[{}] {} ({}) in {} without reason (not using 2.6?)'.format(
                    current_time, self.client.char_name,
                    self.client.ip, self.client.area.name),
                pred=lambda c: c.is_mod)
            self.client.set_mod_call_delay()
            database.log_room('modcall', self.client, self.client.area)
        else:
            args[0] = self.dezalgo(args[0])
            self.server.send_all_cmd_pred(
                'ZZ',
                '[{}] {} ({}) in {} with reason: {}'.format(
                    current_time, self.client.char_name,
                    self.client.ip, self.client.area.name,
                    args[0][:100]),
                pred=lambda c: c.is_mod)
            self.client.set_mod_call_delay()
            database.log_room('modcall', self.client, self.client.area, message=args[0])

    def net_cmd_opKICK(self, args):
        """
        Unused; kick a user from the client UI.

        """
        self.net_cmd_ct(['opkick', '/kick {}'.format(args[0])])

    def net_cmd_opBAN(self, args):
        """
        Unused; ban a user from the client UI.

        """
        self.net_cmd_ct(['opban', '/ban {}'.format(args[0])])

    net_cmd_dispatcher = {
        'HI': net_cmd_hi,  # handshake
        'ID': net_cmd_id,  # client version
        'CH': net_cmd_ch,  # keepalive
        'askchaa': net_cmd_askchaa,  # ask for list lengths
        'askchar2': net_cmd_askchar2,  # ask for list of characters
        'AN': net_cmd_an,  # character list
        'AE': net_cmd_ae,  # evidence list
        'AM': net_cmd_am,  # music list
        'RC': net_cmd_rc,  # AO2 character list
        'RM': net_cmd_rm,  # AO2 music list
        'RD': net_cmd_rd,  # AO2 done request, charscheck etc.
        'CC': net_cmd_cc,  # select character
        'MS': net_cmd_ms,  # IC message
        'CT': net_cmd_ct,  # OOC message
        'MC': net_cmd_mc,  # play song
        'RT': net_cmd_rt,  # WT/CE buttons
        'SETCASE':
        net_cmd_setcase,  # set case-announcement preferences for user
        'CASEA': net_cmd_casea,  # announce a case
        'HP': net_cmd_hp,  # penalties
        'PE': net_cmd_pe,  # add evidence
        'DE': net_cmd_de,  # delete evidence
        'EE': net_cmd_ee,  # edit evidence
        'ZZ': net_cmd_zz,  # call mod button
        'opKICK': net_cmd_opKICK,  # /kick with guard on
        'opBAN': net_cmd_opBAN,  # /ban with guard on
    }
