"""The encoding and atomic-write contract for every settings.ini consumer."""
import locale
import os
import tempfile


def read_settings(parser, path):
    """Prefer UTF-8; accept the active locale used by older installations."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # ConfigParser.read previously used the active locale on every OS.
        # Keep that compatibility; a UTF-8 locale still rejects invalid bytes.
        text = data.decode(locale.getencoding())
    parser.read_string(text, source=str(path))


def write_settings(parser, path):
    """Replace only after a complete UTF-8 write; keep the old file on failure."""
    # mkstemp creates owner-only files on POSIX without Windows-unavailable
    # fchmod. Windows inherits the per-user directory ACL. Each writer gets
    # its own temporary file; callers still own their in-memory parser lock.
    fd, tmp = tempfile.mkstemp(prefix='settings-', suffix='.tmp', dir=path.parent)
    try:
        try:
            stream = os.fdopen(fd, 'w', encoding='utf-8')
        except BaseException:
            os.close(fd)
            raise
        with stream:
            parser.write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
