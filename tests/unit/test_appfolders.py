"""Launchpad's folders and pages: what the grid shows, and what survives."""

from aurora.shell import appfolders


class FakeApp:
    def __init__(self, app_id):
        self.app_id = app_id

    def get_id(self):
        return self.app_id

    def __repr__(self):
        return f"<{self.app_id}>"


def apps(*ids):
    return [FakeApp(i) for i in ids]


# --- what is kept ---------------------------------------------------------

def test_a_damaged_value_never_stops_launchpad_from_opening():
    assert appfolders.load("") == []
    assert appfolders.load("not json") == []
    assert appfolders.load('{"name": "x"}') == []
    assert appfolders.load('[1, "two", {"name": 3, "apps": []}, {"apps": ["a"]}]') == []
    # A folder with nothing in it is not a folder.
    assert appfolders.load('[{"name": "Work", "apps": []}]') == []
    # A name that is only spaces still gets one.
    assert appfolders.load('[{"name": "  ", "apps": ["a"]}]')[0]["name"] == "Folder"


def test_what_is_written_comes_back(tmp_path):
    folders = [{"name": "Lavoro", "apps": ["a.desktop", "b.desktop"]}]
    assert appfolders.load(appfolders.dump(folders)) == folders
    # Duplicates inside one folder are dropped, order kept.
    assert appfolders.load('[{"name": "x", "apps": ["a", "b", "a"]}]')[0]["apps"] == ["a", "b"]


# --- what the grid shows --------------------------------------------------

def test_a_folder_stands_where_its_first_app_stood():
    folders = [{"name": "Work", "apps": ["b", "d"]}]
    items = appfolders.arrange(apps("a", "b", "c", "d", "e"), folders)
    kinds = [(i[0], i[1]["name"] if i[0] == "folder" else i[1].get_id()) for i in items]
    assert kinds == [("app", "a"), ("folder", "Work"), ("app", "c"), ("app", "e")]
    members = [m.get_id() for m in items[1][2]]
    assert members == ["b", "d"]


def test_an_app_that_is_no_longer_installed_is_remembered_but_not_shown():
    folders = [{"name": "Work", "apps": ["b", "gone", "d"]}]
    items = appfolders.arrange(apps("a", "b", "d"), folders)
    folder = [i for i in items if i[0] == "folder"][0]
    assert [m.get_id() for m in folder[2]] == ["b", "d"]
    # The folder itself still holds the id, so reinstalling puts it back.
    assert folders[0]["apps"] == ["b", "gone", "d"]


def test_a_folder_whose_apps_are_all_gone_is_not_drawn():
    items = appfolders.arrange(apps("a"), [{"name": "Work", "apps": ["x", "y"]}])
    assert [i[0] for i in items] == ["app"]


# --- making and unmaking --------------------------------------------------

def test_dropping_one_app_on_another_makes_a_folder_with_both():
    folders = appfolders.put_together([], "a", "b", "Work")
    assert folders == [{"name": "Work", "apps": ["a", "b"]}]
    # Dropping a third on the same tile puts it in the same folder.
    folders = appfolders.put_together(folders, "a", "c", "Ignored")
    assert folders[0]["apps"] == ["a", "b", "c"]
    # An app only ever lives in one folder.
    folders = appfolders.put_together(folders, "d", "b", "Other")
    assert appfolders.folder_of(folders, "b")["name"] == "Other"
    assert "b" not in [f for f in folders if f["name"] == "Work"][0]["apps"]


def test_an_app_cannot_be_dropped_on_itself_or_moved_inside_its_own_folder():
    folders = [{"name": "Work", "apps": ["a", "b"]}]
    assert appfolders.put_together(folders, "a", "a", "x") == folders
    assert appfolders.put_together(folders, "a", "b", "x") == folders


def test_taking_apps_out_empties_the_folder_away():
    folders = [{"name": "Work", "apps": ["a", "b"]}]
    folders = appfolders.take_out(folders, "a")
    assert folders == [{"name": "Work", "apps": ["b"]}]
    assert appfolders.take_out(folders, "b") == []


def test_renaming_keeps_the_apps():
    folders = [{"name": "Work", "apps": ["a"]}, {"name": "Play", "apps": ["b"]}]
    renamed = appfolders.rename(folders, "Work", "  Lavoro ")
    assert renamed[0] == {"name": "Lavoro", "apps": ["a"]}
    assert renamed[1]["name"] == "Play"
    assert appfolders.rename(folders, "Work", "   ") == folders


# --- pages ----------------------------------------------------------------

def test_pages_hold_what_the_screen_holds():
    items = list(range(30))
    assert appfolders.paginate(items, 12) == [items[0:12], items[12:24], items[24:30]]
    assert appfolders.paginate(items, 30) == [items]
    assert appfolders.paginate([], 12) == [[]]
    # Nonsense sizes still give usable pages.
    assert len(appfolders.paginate(items, 0)[0]) == appfolders.MIN_PER_PAGE
    assert len(appfolders.paginate(items, None)[0]) == appfolders.MIN_PER_PAGE


def test_a_page_is_measured_from_the_screen():
    count, columns = appfolders.fits(760, 520, 118, 128)
    assert columns == 6 and count == 6 * 4
    # A very small screen still gets three columns and two rows.
    count, columns = appfolders.fits(100, 100, 118, 128)
    assert columns == 3 and count == 6
