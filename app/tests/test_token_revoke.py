"""Log out and re-pair revoke the Client API Token they retire.

Both pairing routes return the issued token's id; Ludo records it as
RomM/client_token_id and revokes it with DELETE /api/client-tokens/{id}
(a client token may always revoke itself). Without an id nothing is sent.
"""
import asyncio

from ludo_app.backend import LudoBackend
from romm_sync_engine.sync_core import RomMClient


class _Resp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body or {}
        self.text = ''

    def json(self):
        return self._body


def test_exchange_records_token_id():
    c = RomMClient('http://romm.test')
    c.session.post = lambda *a, **k: _Resp(200, {'id': 57, 'raw_token': 'rmm_x'})
    assert c.exchange_pair_code('12345678') == 'rmm_x'
    assert c.paired_token_id == 57


def test_device_flow_records_token_id():
    c = RomMClient('http://romm.test')
    c.session.post = lambda *a, **k: _Resp(200, {'id': 58, 'access_token': 'rmm_y',
                                                 'device_id': 'dev'})
    assert c.device_auth_poll('code') == ('approved', 'rmm_y')
    assert (c.paired_token_id, c.paired_device_id) == (58, 'dev')


def test_revoke_hits_own_token():
    c = RomMClient('http://romm.test')
    calls = []
    c.session.delete = lambda url, **k: calls.append(url) or _Resp(200)
    assert c.revoke_client_token(57)
    assert calls == ['http://romm.test/api/client-tokens/57']
    c.session.delete = lambda url, **k: _Resp(404)
    assert c.revoke_client_token(57)  # already gone
    c.session.delete = lambda url, **k: _Resp(403)
    assert not c.revoke_client_token(57)
    assert not c.revoke_client_token('')


class _Settings(dict):
    def get(self, section, key, default=''):
        return dict.get(self, (section, key), default)


class _Client:
    client_token = 'rmm_old'

    def __init__(self):
        self.revoked = []

    def revoke_client_token(self, token_id):
        self.revoked.append(token_id)
        return True


def _backend(client):
    b = LudoBackend.__new__(LudoBackend)
    b._romm_client = client
    return b


def test_backend_revokes_recorded_id():
    client = _Client()
    s = _Settings({('RomM', 'client_token'): 'rmm_old', ('RomM', 'client_token_id'): '57'})
    assert asyncio.run(_backend(client)._revoke_paired_token(s))
    assert client.revoked == ['57']


def test_backend_skips_without_id_or_client():
    client = _Client()
    s = _Settings({('RomM', 'client_token'): 'rmm_old'})
    assert not asyncio.run(_backend(client)._revoke_paired_token(s))
    assert client.revoked == []
    s = _Settings({('RomM', 'client_token'): 'rmm_old', ('RomM', 'client_token_id'): '57'})
    assert not asyncio.run(_backend(None)._revoke_paired_token(s))
