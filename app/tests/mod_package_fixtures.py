"""Synthetic mod archive/client shared by portable and transaction tests."""
import io
import zipfile
from types import SimpleNamespace

import pytest

from ludo_app import mod_packages as M
from romm_sync_engine import switch_mods

TITLE = '0100F2C0115B6000'
MOD = f'load/{TITLE}/Example/exefs/subsdk3'


class Reply:
    headers = {}

    def __init__(self, data=None, blob=b''):
        self.data, self.blob = data, blob

    def json(self):
        return self.data

    def raise_for_status(self):
        pass

    def iter_content(self, _):
        yield self.blob

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    target = switch_mods.Installer(tmp_path / 'state', tmp_path / 'load',
                                   tmp_path / 'sdmc', lambda: False)
    monkeypatch.setattr(M, 'installer', lambda: target)
    monkeypatch.setattr(M.emulator_saves, 'eden_is_running', lambda: False)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        z.writestr(MOD, b'example-code')
    c = SimpleNamespace(authenticated=True, base_url='http://romm.test', calls=[])
    detail = {'fs_name': 'Example Game', 'files': [
        {'id': 1, 'file_name': 'Game.nsp', 'category': 'game'},
        {'id': 2, 'file_name': 'mods/backups/Example.zip', 'category': 'mod'},
        {'id': 3, 'file_name': 'gone.zip', 'category': 'mod', 'missing_from_fs': True},
        {'id': 4, 'file_name': 'patch.pchtxt', 'category': 'mod'},
        {'id': 5, 'file_name': 'Other.zip', 'category': 'game'},
    ]}

    def get(url, **kwargs):
        c.calls.append((url, kwargs))
        return Reply(blob=stream.getvalue()) if '/content/' in url else Reply(detail)
    c.session = SimpleNamespace(get=get)
    return c


