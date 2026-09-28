"""Storage driver seam.

One interface, one implementation for now. `StorageDriver` is a Protocol
rather than a base class so a later `S3StorageDriver` drops in without
subscribing to anything -- the callers only ever see the four methods below.

Rules this layer enforces, because they are easy to get wrong once:

  * The stored key is generated here, never taken from the upload. A filename
    is attacker-controlled input and the one value that must not decide where
    bytes land on disk.
  * Every key is resolved and checked against the driver root, so a key
    containing `../` cannot walk out of the storage directory even if one
    reaches this layer.
  * The driver raises `StorageError`; it never returns a partial success.
    A file that is not durably written must not produce a database row.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional, Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """A file could not be written, read or removed."""


class StorageDriver(Protocol):
    def new_key(self, suffix: str = ".pdf") -> str:
        """Generate an opaque storage key. No user input involved."""
        ...

    def save(self, content: bytes, key: str) -> str:
        """Write bytes and return the key. Raise StorageError on failure."""
        ...

    def open(self, key: str) -> bytes:
        """Read bytes back. Raise StorageError if missing or unreadable."""
        ...

    def delete(self, key: str) -> None:
        """Remove bytes. Raise StorageError on failure."""
        ...

    def exists(self, key: str) -> bool:
        ...


class LocalStorageDriver:
    """Writes under `<root>`, flat, with generated filenames."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).expanduser().resolve()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # Surfaced at construction rather than on the first upload: a
            # misconfigured path is a deployment problem, not a per-request one.
            raise StorageError(f"storage directory is not writable: {self._root}") from exc

    @property
    def root(self) -> Path:
        return self._root

    def new_key(self, suffix: str = ".pdf") -> str:
        # uuid4 is fine here: the key only has to be unguessable enough to
        # avoid directory listings being a useful attack, and it never
        # authorises anything on its own.
        return f"{uuid.uuid4().hex}{suffix}"

    def _resolve(self, key: str) -> Path:
        if not key or key != Path(key).name:
            # A key with a separator is a path-traversal attempt, or a bug.
            raise StorageError("invalid storage key")

        candidate = (self._root / key).resolve()
        if self._root != candidate.parent and self._root not in candidate.parents:
            raise StorageError("storage key resolves outside the storage root")
        return candidate

    def save(self, content: bytes, key: str) -> str:
        target = self._resolve(key)
        try:
            # Write to a temporary sibling then rename, so an interrupted
            # write can never leave a half-written PDF behind.
            staging = target.with_suffix(target.suffix + ".part")
            staging.write_bytes(content)
            staging.replace(target)
        except OSError as exc:
            logger.warning("storage write failed: %s", type(exc).__name__)
            raise StorageError("could not write the file to storage") from exc
        return key

    def open(self, key: str) -> bytes:
        target = self._resolve(key)
        try:
            return target.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("the stored file is missing") from exc
        except OSError as exc:
            logger.warning("storage read failed: %s", type(exc).__name__)
            raise StorageError("could not read the file from storage") from exc

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("storage delete failed: %s", type(exc).__name__)
            raise StorageError("could not remove the file from storage") from exc

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except StorageError:
            return False


# --- wiring ----------------------------------------------------------------
#
# Cached on the module rather than rebuilt per request, and overridable so a
# test can point the app at a temporary directory.


_driver: Optional[StorageDriver] = None


def build_driver() -> StorageDriver:
    """Construct the driver named by STORAGE_DRIVER.

    An unknown value raises rather than silently falling back to local disk:
    quietly downgrading an intended S3 deployment to local storage would be
    the kind of failure that only shows up when the box is rebuilt.
    """
    driver = settings.storage_driver.strip().lower()
    if driver == "local":
        return LocalStorageDriver(Path(settings.storage_local_path) / "documents")
    if driver == "s3":
        raise StorageError(
            "STORAGE_DRIVER=s3 is not implemented yet; set STORAGE_DRIVER=local"
        )
    raise StorageError(f"unknown STORAGE_DRIVER '{settings.storage_driver}'")


def get_storage_driver() -> StorageDriver:
    global _driver
    if _driver is None:
        _driver = build_driver()
    return _driver


def set_storage_driver(driver: StorageDriver) -> None:
    """Point the app at a different driver (tests, and the s3 swap later)."""
    global _driver
    _driver = driver


def reset_storage_driver() -> None:
    global _driver
    _driver = None
