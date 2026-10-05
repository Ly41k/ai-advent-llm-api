"""Single-host POSIX session leases; the kernel releases them on process exit."""
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import tempfile


def acquire(database, session):
    # Inode identity also covers symlink/hardlink aliases. Never unlink a lock:
    # replacing its inode would allow two simultaneous owners.
    info = Path(database).stat()
    root = Path(tempfile.gettempdir()) / f"bublik-day25-locks-{os.getuid()}"
    root.mkdir(mode=0o700, exist_ok=True)
    directory = root.lstat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid() or directory.st_mode & 0o077:
        raise ValueError("Session lock directory must be private and owned by the current user")
    key = hashlib.sha256(f"{info.st_dev}:{info.st_ino}:{session}".encode()).hexdigest()
    fd = os.open(root / key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(fd)
        raise ValueError("Session has an active pending turn; wait for its process, do not /recover") from error
    except BaseException:
        os.close(fd)
        raise
    return fd


def release(fd):
    os.close(fd)
