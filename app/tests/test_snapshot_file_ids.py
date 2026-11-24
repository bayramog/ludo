"""The library snapshot keeps each ROM file's RomM id.

Save channels are keyed to one ROM file (save_channels.rom_file_for_save), so
a snapshot without file ids sent every save back to negotiate after a cold
start, until the next full fetch rewrote the library."""
from ludo_app.backend import LudoBackend


def test_snapshot_keeps_file_ids_and_drops_the_rest():
    games = [{'rom_id': 1, 'romm_data': {'files': [{
        'id': 12686, 'file_name': 'Game (USA).gba', 'file_size_bytes': 4,
        'category': 'game', 'md5_hash': 'x', 'archive_members': ['a']}]}}]
    slim = LudoBackend._slim_for_snapshot(LudoBackend.__new__(LudoBackend), games)
    assert slim[0]['romm_data']['files'] == [{
        'id': 12686, 'file_name': 'Game (USA).gba', 'file_size_bytes': 4,
        'category': 'game'}]
    # the live library is not trimmed in place
    assert 'md5_hash' in games[0]['romm_data']['files'][0]
