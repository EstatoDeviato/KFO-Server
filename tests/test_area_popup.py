"""Tests for the per-area popup (/area_popup) and its BB popup delivery."""

from unittest import mock

from server.area import Area
from server.commands.areas import ooc_cmd_area_popup


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


# --- Area.set_popup -----------------------------------------------------------


def test_set_popup_records_whether_a_cm_was_present():
    area = make_area()
    area.set_popup("welcome to the room")
    assert area.popup == "welcome to the room"
    assert area.popup_held_by_cm is False  # no CM present at set time

    area._owners.add(FakeClient(area, area.area_manager.server))
    area.set_popup("read the rules")
    assert area.popup == "read the rules"
    assert area.popup_held_by_cm is True


# --- clearing ----------------------------------------------------------------


def test_remove_owner_clears_popup_when_last_cm_leaves():
    area = make_area()
    cm = FakeClient(area, area.area_manager.server)
    area._owners.add(cm)
    area.set_popup("rules")

    with mock.patch.object(area, "broadcast_ooc"):
        area.remove_owner(cm, dc=True)

    assert area.popup == ""
    assert area.popup_held_by_cm is False


def test_remove_owner_keeps_popup_when_other_cms_remain():
    area = make_area()
    cm1 = FakeClient(area, area.area_manager.server, showname="cm1")
    cm2 = FakeClient(area, area.area_manager.server, showname="cm2")
    area._owners.update([cm1, cm2])
    area.set_popup("rules")

    with mock.patch.object(area, "broadcast_ooc"):
        area.remove_owner(cm1, dc=True)

    assert area.popup == "rules"


def test_remove_client_clears_popup_when_room_empties():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.clients.add(client)
    area.set_popup("welcome")

    with mock.patch.object(area, "trigger"), \
            mock.patch.object(area, "change_status"), \
            mock.patch.object(area, "broadcast_player_list"), \
            mock.patch.object(area, "broadcast_player_list_to_target"), \
            mock.patch("server.database.log_area"):
        area.remove_client(client)

    assert area.popup == ""
    assert area.popup_held_by_cm is False


# --- command -----------------------------------------------------------------


def test_area_popup_bare_shows_current_popup():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.set_popup("hi")

    ooc_cmd_area_popup(client, "")

    assert any("Current area popup:" in line for line in client.ooc)
    assert not any("Usage: /area_popup" in line for line in client.ooc)


def test_area_popup_bare_with_no_popup_points_to_help():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)

    ooc_cmd_area_popup(client, "")

    assert any("/help area_popup" in line for line in client.ooc)


def test_area_popup_docstring_documents_usage_and_formatting():
    import inspect

    doc = inspect.getdoc(ooc_cmd_area_popup) or ""
    assert "Usage: /area_popup [-c] [message]" in doc
    assert "new line" in doc


def test_area_popup_clear_flag():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)
    area.set_popup("hi")
    area.popup_held_by_cm = True

    with mock.patch.object(area, "broadcast_ooc") as broadcast:
        ooc_cmd_area_popup(client, "-c")

    assert area.popup == ""
    assert area.popup_held_by_cm is False
    broadcast.assert_called_once()


def test_area_popup_set_converts_backslash_n_to_newline():
    area = make_area()
    client = FakeClient(area, area.area_manager.server)

    with mock.patch.object(area, "broadcast_ooc"):
        ooc_cmd_area_popup(client, "Line one\\nLine two")

    assert area.popup == "Line one\nLine two"


def test_area_popup_set_censors_text():
    server = FakeServer(censors={"whole": ["badword"], "partial": [], "replace": "*"})
    area = make_area()
    client = FakeClient(area, server)

    with mock.patch.object(area, "broadcast_ooc"):
        ooc_cmd_area_popup(client, "this has a badword")

    assert area.popup == "this has a *******"
