"""Tests for the per-area room motd (/roommotd) and its BB popup delivery."""

from unittest import mock

from server.area import Area
from server.commands.areas import ooc_cmd_roommotd


class FakeServer:
    def __init__(self, censors=None):
        self.censors = censors
        self.config = {"hostname": "test", "motd": ""}


class FakeAreaManager:
    def __init__(self):
        self.areas = []
        self.owners = set()
        self.single_cm = False

    @property
    def server(self):
        return FakeServer()

    def send_arup_players(self):
        pass

    def send_arup_cms(self):
        pass


def make_area():
    manager = FakeAreaManager()
    area = Area(manager, "Test Area")
    manager.areas.append(area)
    return area


class FakeClient:
    def __init__(self, area, server, is_mod=True, showname="CM"):
        self.area = area
        self.server = server
        self.is_mod = is_mod
        self.is_gm = False
        self.showname = showname
        self.id = 1
        self.char_id = 0
        self.hidden = False
        self.sneaking = False
        self.hidden_in = None
        self.broadcast_list = []
        self.ooc = []

    def send_ooc(self, msg):
        self.ooc.append(msg)


# --- Area.set_motd -----------------------------------------------------------


def test_set_motd_records_whether_a_cm_was_present():
    area = make_area()
    area.set_motd("welcome to the room")
    assert area.motd == "welcome to the room"
    assert area.motd_held_by_cm is False  # no CM present at set time

    area._owners.add(FakeClient(area, area.area_manager.server))
    area.set_motd("read the rules")
    assert area.motd == "read the rules"
    assert area.motd_held_by_cm is True


# --- clearing ----------------------------------------------------------------


def test_remove_owner_clears_motd_when_last_cm_leaves():
    area = make_area()
    cm = FakeClient(area, area.area_manager.server)
    area._owners.add(cm)
    area.set_motd("rules")

    with mock.patch.object(area, "broadcast_ooc"):
        area.remove_owner(cm, dc=True)

    assert area.motd == ""
    assert area.motd_held_by_cm is False


def test_remove_owner_keeps_motd_when_other_cms_remain():
    area = make_area()
    cm1 = FakeClient(area, area.area_manager.server, showname="cm1")
    cm2 = FakeClient(area, area.area_manager.server, showname="cm2")
    area._owners.update([cm1, cm2])
    area.set_motd("rules")

    with mock.patch.object(area, "broadcast_ooc"):
        area.remove_owner(cm1, dc=True)

    assert area.motd == "rules"


def test_remove_client_clears_motd_when_room_empties():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.clients.add(client)
    area.set_motd("welcome")

    with mock.patch.object(area, "trigger"), \
            mock.patch.object(area, "change_status"), \
            mock.patch.object(area, "broadcast_player_list"), \
            mock.patch.object(area, "broadcast_player_list_to_target"), \
            mock.patch("server.database.log_area"):
        area.remove_client(client)

    assert area.motd == ""
    assert area.motd_held_by_cm is False


# --- command -----------------------------------------------------------------


def test_roommotd_bare_shows_help_and_current_motd():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.set_motd("hi")

    ooc_cmd_roommotd(client, "")

    assert any("Usage: /roommotd" in line for line in client.ooc)
    assert any("Current room motd:" in line for line in client.ooc)


def test_roommotd_clear_flag():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.set_motd("hi")
    area.motd_held_by_cm = True

    with mock.patch.object(area, "broadcast_ooc") as broadcast:
        ooc_cmd_roommotd(client, "-c")

    assert area.motd == ""
    assert area.motd_held_by_cm is False
    broadcast.assert_called_once()


def test_roommotd_set_converts_backslash_n_to_newline():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)

    with mock.patch.object(area, "broadcast_ooc"):
        ooc_cmd_roommotd(client, "Line one\\nLine two")

    assert area.motd == "Line one\nLine two"


def test_roommotd_set_censors_text():
    server = FakeServer(censors={"whole": ["badword"], "partial": [], "replace": "*"})
    area = make_area()
    client = FakeClient(area, server)

    with mock.patch.object(area, "broadcast_ooc"):
        ooc_cmd_roommotd(client, "this has a badword")

    assert area.motd == "this has a *******"
