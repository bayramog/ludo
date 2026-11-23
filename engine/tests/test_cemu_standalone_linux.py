"""Linux Cemu discovery, executable permissions and XDG audio repair."""
import os
import sys
import tempfile
from pathlib import Path
from test_cemu_standalone import (sync_core, RetroArchInterface, STANDALONE_EMULATORS,
    find_standalone_builds, find_standalone_executable, touch, check, FAILED)


def main():
    spec = STANDALONE_EMULATORS['cemu']
    ra = RetroArchInterface.__new__(RetroArchInterface)
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / 'home'
        home.mkdir()
        os.environ.update(HOME=str(home), USERPROFILE=str(home),
                          APPDATA=str(home / 'roaming'), LOCALAPPDATA=str(home / 'local'),
                          XDG_CONFIG_HOME=str(home / '.config'))
        installed = set()
        sync_core.flatpak_app_installed = lambda app: app in installed
        sync_core.shutil.which = lambda n: None
        # --- nothing installed ----------------------------------------------
        check('nothing installed', find_standalone_executable('cemu', spec), '')

        # --- AppImage only, upstream's real file name -----------------------
        app = touch(home / 'AppImages' / 'Cemu-2.6-x86_64.AppImage', exec_=True)
        check('appimage found', find_standalone_executable('cemu', spec), str(app))
        builds = find_standalone_builds('cemu', spec)
        check('appimage listed', [(b['kind'], b['label']) for b in builds],
              [('appimage', 'Cemu')])
        touch(home / 'AppImages' / 'ludo.appimage', exec_=True)
        touch(home / 'AppImages' / 'Eden-1.0.AppImage', exec_=True)
        check('other appimages ignored',
              find_standalone_executable('cemu', spec), str(app))
        # Downloaded without +x -> adopted, and the bit is set for the user.
        app.chmod(0o644)
        check('non-executable appimage made executable',
              find_standalone_executable('cemu', spec), str(app))
        check('exec bit added', bool(app.stat().st_mode & 0o100), True)
        app.chmod(0o755)

        # --- flatpak wins over AppImage; both are listed ---------------------
        installed.add('info.cemu.Cemu')
        check('flatpak preferred', find_standalone_executable('cemu', spec),
              'flatpak:info.cemu.Cemu')
        builds = find_standalone_builds('cemu', spec)
        check('both listed', [b['kind'] for b in builds], ['flatpak', 'appimage'])
        check('flatpak is current', [b['current'] for b in builds], [True, False])

        # --- user override picks the AppImage over the flatpak --------------
        class S:
            def get(self, sec, key, default=''):
                return str(app) if (sec, key) == ('Emulators', 'cemu_path') else default
        check('override to appimage',
              find_standalone_executable('cemu', spec, S()), str(app))

        # --- launch preparation must not rewrite Cemu's audio settings -------
        def audio(cfg_dir, exe, device, label):
            cfg_dir.mkdir(parents=True, exist_ok=True)
            f = cfg_dir / 'settings.xml'
            original = (f'<Audio>\r\n<TVDevice>{device}</TVDevice>\r\n</Audio>\r\n'
                        ).encode('utf-8')
            f.write_bytes(original)
            ra.build_standalone_launch_command(str(home / 'g.wua'), 'cemu', spec, exe)
            check(f'{label}: {device} settings unchanged', f.read_bytes(), original)
            backup = cfg_dir / 'settings.xml.bak-ludo-audio'
            check(f'{label}: {device} no audio backup', backup.exists(), False)
            # Keep cases independent even when running against the old rewrite.
            if backup.exists():
                backup.unlink()
        for label, exe, cfg_dir, xdg in (
                ('flatpak', 'flatpak:info.cemu.Cemu',
                 home / '.var/app/info.cemu.Cemu/config/Cemu', home / '.config'),
                ('appimage', str(app), home / '.config/Cemu', None),
                ('native XDG', '/usr/bin/cemu', home / 'xdg/Cemu', home / 'xdg')):
            if xdg is None:
                os.environ.pop('XDG_CONFIG_HOME', None)
            else:
                os.environ['XDG_CONFIG_HOME'] = str(xdg)
            for device in ('default', 'alsa_x'):
                audio(cfg_dir, exe, device, label)

        # --- beta.23 blanked the device; its backup puts 'default' back once --
        def repair(cfg_dir, exe, device, label):
            cfg_dir.mkdir(parents=True, exist_ok=True)
            f = cfg_dir / 'settings.xml'
            backup = cfg_dir / 'settings.xml.bak-ludo-audio'
            f.write_bytes(f'<Audio>\r\n<TVDevice>{device}</TVDevice>\r\n</Audio>\r\n'.encode())
            backup.write_bytes(b'<Audio>\r\n<TVDevice>default</TVDevice>\r\n</Audio>\r\n')
            ra.build_standalone_launch_command(str(home / 'g.wua'), 'cemu', spec, exe)
            check(f'{label}: backup removed after repair', backup.exists(), False)
            return f.read_bytes()
        os.environ['XDG_CONFIG_HOME'] = str(home / '.config')
        fp = home / '.var/app/info.cemu.Cemu/config/Cemu'
        check('flatpak: blanked device restored, CRLF kept',
              repair(fp, 'flatpak:info.cemu.Cemu', '', 'flatpak'),
              b'<Audio>\r\n<TVDevice>default</TVDevice>\r\n</Audio>\r\n')
        check('flatpak: device chosen since is left alone',
              repair(fp, 'flatpak:info.cemu.Cemu', 'alsa_x', 'flatpak'),
              b'<Audio>\r\n<TVDevice>alsa_x</TVDevice>\r\n</Audio>\r\n')
        os.environ.pop('XDG_CONFIG_HOME', None)
        check('appimage: blanked device restored',
              repair(home / '.config/Cemu', str(app), '', 'appimage'),
              b'<Audio>\r\n<TVDevice>default</TVDevice>\r\n</Audio>\r\n')
        # Once the backup is gone, a deliberately empty device stays empty.
        f = home / '.config/Cemu/settings.xml'
        f.write_bytes(b'<Audio>\r\n<TVDevice></TVDevice>\r\n</Audio>\r\n')
        ra.build_standalone_launch_command(str(home / 'g.wua'), 'cemu', spec, str(app))
        check('no backup: an empty device is left empty', f.read_bytes(),
              b'<Audio>\r\n<TVDevice></TVDevice>\r\n</Audio>\r\n')


    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
