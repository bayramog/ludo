"""An install whose device isn't the one its token is bound to takes the
token's device once the server stops serving the other (RomM 5.5, #5460).

Before 5.5 a mismatch only cost web-UI installs; from 5.5 every sync route
answers the token 404 for any other device, so save sync stopped."""
from ludo_app.backend import LudoBackend


class _Settings:
    def __init__(self, **device):
        self.d = {('Device', k): v for k, v in device.items()}

    def get(self, sec, key, default=''):
        return self.d.get((sec, key), default)

    def set(self, sec, key, value):
        self.d[(sec, key)] = value


class _Client:
    """`serves`: device ids GET /api/devices/{id} answers for this token."""
    authenticated = True
    client_token = 'rmm_x'

    def __init__(self, bound, serves):
        self.bound, self.serves, self.registered = bound, set(serves), []

    def get_current_user(self):
        return {'id': 1, 'current_device_id': self.bound}

    def get_device(self, device_id):
        return {'id': device_id, 'name': 'n'} if device_id in self.serves else None

    def register_device(self, **kw):
        self.registered.append(kw)
        return 'fresh'


def _backend(client, **device):
    b = LudoBackend.__new__(LudoBackend)
    b._romm_client, b._settings = client, _Settings(**device)
    b._install_not_bound = True
    b._push_device_name = lambda *a, **k: None
    return b


def test_5_5_mismatch_adopts_the_tokens_device():
    c = _Client(bound='tok-dev', serves={'tok-dev'})  # old device now 404s
    b = _backend(c, device_id='old-dev')
    assert b._ensure_device_registered() == 'tok-dev'
    assert b._settings.get('Device', 'device_id') == 'tok-dev'
    assert b._install_not_bound is False and c.registered == []


def test_older_server_keeps_the_device_it_syncs_as():
    c = _Client(bound='tok-dev', serves={'tok-dev', 'old-dev'})
    b = _backend(c, device_id='old-dev')
    assert b._ensure_device_registered() == 'old-dev'
    assert b._settings.get('Device', 'device_id') == 'old-dev'


def test_no_device_yet_takes_the_tokens_instead_of_registering():
    c = _Client(bound='tok-dev', serves={'tok-dev'})
    b = _backend(c)
    assert b._ensure_device_registered() == 'tok-dev' and c.registered == []


def test_unbound_token_registers_as_before():
    c = _Client(bound=None, serves=set())
    b = _backend(c, device_id='gone')
    assert b._ensure_device_registered() == 'fresh'
    assert b._settings.get('Device', 'device_id') == 'fresh'


def test_password_session_never_asks():
    c = _Client(bound='tok-dev', serves=set())
    c.client_token = None
    b = _backend(c)
    assert b._ensure_device_registered() == 'fresh'
