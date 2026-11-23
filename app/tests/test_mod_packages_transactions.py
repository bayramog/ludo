"""Real mod installation/removal requires the native POSIX flock transaction."""
from mod_package_fixtures import client, M, MOD, TITLE


def test_download_is_one_revalidated_file_then_install_and_remove(client, tmp_path):
    assert M.install(client, 1200, TITLE, 2, {})['status'] == 'ok'
    url, args = client.calls[-1]
    assert url.endswith('/api/roms/1200/content/Example%20Game')
    assert args['params'] == {'file_ids': '2'}
    assert (tmp_path / MOD).read_bytes() == b'example-code'
    assert M.state(client, 1200, TITLE)['installed'][0]['package_id'] == '1200:2'
    assert M.remove(TITLE, '1200:2')['status'] == 'ok'
    assert not (tmp_path / MOD).exists()
