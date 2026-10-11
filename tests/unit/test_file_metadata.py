"""Network/monitor metadata can omit optional hidden/backup attributes."""
import pytest
from gi.repository import Gio
from aurora.files.window import is_backup, is_hidden


@pytest.mark.parametrize('name,hidden,backup', [('notes.txt',False,False),
    ('.notes',True,False), ('notes~',False,True), ('.notes~',True,True)])
def test_missing_optional_metadata_uses_the_filename(name, hidden, backup):
    info = Gio.FileInfo()
    info.set_name(name)
    assert not info.has_attribute('standard::is-hidden')
    assert is_hidden(info) == hidden and is_backup(info) == backup


def test_backend_metadata_takes_precedence_over_filename():
    info = Gio.FileInfo()
    info.set_name('.notes~')
    info.set_attribute_boolean('standard::is-hidden',False)
    info.set_attribute_boolean('standard::is-backup',False)
    assert not is_hidden(info) and not is_backup(info)
