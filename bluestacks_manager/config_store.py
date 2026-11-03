"""Safe reader/writer for BlueStacks ``bluestacks.conf`` files.

The file is a UTF-8 ``key="value"`` format. Unknown lines and comments are
preserved wherever possible. Writes are atomic through a temporary file in the
same directory, and the original file is replaced with ``os.replace``.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .constants import BACKUP_DIR_NAME, CONFIG_FILENAME

_CONF_RE = re.compile(r'^(?P<key>[^=]+?)="(?P<value>.*)"$')
_INSTANCE_RE = re.compile(r"^bst\.instance\.(?P<instance_id>[^.]+)\.")


@dataclass
class ConfigKey:
    """A parsed configuration line."""

    key: str
    value: str
    line_number: int


def parse_line(line: str) -> ConfigKey | None:
    """Parse one ``key="value"`` line, returning ``None`` for comments/blanks."""

    match = _CONF_RE.match(line.strip())
    if not match:
        return None
    return ConfigKey(match.group("key"), match.group("value"), 0)


def instance_id_from_key(key: str) -> str | None:
    """Return the instance id if ``key`` belongs to an instance block."""

    match = _INSTANCE_RE.match(key)
    return match.group("instance_id") if match else None


def normalize_instance_id(instance_id: str) -> str:
    """Normalize an instance id without changing its display value."""

    return instance_id.strip()


def instance_prefix(instance_id: str) -> str:
    return f"bst.instance.{normalize_instance_id(instance_id)}."


class ConfigStore:
    """In-memory representation of a BlueStacks configuration file."""

    def __init__(self, path: str | Path, lines: Iterable[str] | None = None) -> None:
        self.path = Path(path)
        raw_lines = list(lines) if lines is not None else self.path.read_text(encoding="utf-8").splitlines()
        self.lines = raw_lines
        self.keys: dict[str, ConfigKey] = {}
        self.duplicate_keys: set[str] = set()
        for line_number, line in enumerate(self.lines, start=1):
            parsed = parse_line(line)
            if parsed is None:
                continue
            parsed.line_number = line_number
            if parsed.key in self.keys:
                self.duplicate_keys.add(parsed.key)
            # Last value wins for reads; first line wins for replacement.
            self.keys.setdefault(parsed.key, parsed)

    @classmethod
    def load(cls, path: str | Path) -> "ConfigStore":
        return cls(path)

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def get(self, key: str, default: str = "") -> str:
        key_obj = self.keys.get(key)
        return key_obj.value if key_obj else default

    def has_key(self, key: str) -> bool:
        return key in self.keys

    def instance_ids(self) -> list[str]:
        ids = set()
        for key in self.keys:
            instance_id = instance_id_from_key(key)
            if instance_id:
                ids.add(instance_id)
        return sorted(ids)

    def instance_key(self, instance_id: str, suffix: str) -> str:
        return f"{instance_prefix(instance_id)}{suffix}"

    def instance_value(self, instance_id: str, suffix: str, default: str = "") -> str:
        return self.get(self.instance_key(instance_id, suffix), default)

    def set_instance_values(
        self,
        instance_id: str,
        values: dict[str, str],
        *,
        preserve_unknown: bool = True,
    ) -> dict[str, str]:
        """Set instance values in memory and return old -> new changes."""

        normalized = normalize_instance_id(instance_id)
        if not normalized:
            raise ValueError("实例 ID 不能为空")
        changes: dict[str, str] = {}
        for suffix, value in values.items():
            if value is None:
                continue
            value = str(value)
            key = self.instance_key(normalized, suffix)
            old_value = self.get(key)
            if old_value == value:
                continue
            self._assign(key, value)
            changes[key] = {"old": old_value, "new": value}
        return changes

    def delete_instance_values(self, instance_id: str, suffixes: Iterable[str]) -> list[str]:
        """Remove instance keys from memory and return the deleted keys."""

        normalized = normalize_instance_id(instance_id)
        deleted: list[str] = []
        for suffix in suffixes:
            key = self.instance_key(normalized, suffix)
            if key in self.keys:
                self._delete_key(key)
                deleted.append(key)
        return deleted

    def add_instance_id(self, instance_id: str) -> bool:
        """Create a minimal instance block if it does not already exist."""

        normalized = normalize_instance_id(instance_id)
        if normalized in self.instance_ids():
            return False
        self.set_instance_values(normalized, {"display_name": normalized})
        return True

    def save(self, *, create_backup: bool = False, backup_dir: str | Path | None = None) -> Path | None:
        """Write the in-memory configuration atomically.

        Returns the backup path when ``create_backup`` is true and a backup was
        created; otherwise returns ``None``.
        """

        if not self.exists:
            raise FileNotFoundError(f"配置文件不存在: {self.path}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if create_backup:
            backup_path = backup_config_file(self.path, backup_dir=backup_dir)
        text = "\n".join(self.lines).rstrip("\n") + "\n"
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=".bluestacks.conf.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
        # Refresh the in-memory key map after the on-disk write.
        self.__init__(self.path)
        return backup_path

    def _assign(self, key: str, value: str) -> None:
        serialized = f'{key}="{value}"'
        existing = self.keys.get(key)
        if existing is not None:
            self.lines[existing.line_number - 1] = serialized
            existing.value = value
            return
        # Place new instance keys near the end of the instance section. If no
        # instance section exists, simply append.
        instance_line = None
        for line_number, line in enumerate(self.lines):
            parsed = parse_line(line)
            if parsed and parse_line(line) and instance_id_from_key(parsed.key):
                instance_line = line_number
                break
        if instance_line is None:
            self.lines.append(serialized)
        else:
            # Insert after the last instance-related line when available.
            last_instance_line = instance_line
            for line_number in range(instance_line, len(self.lines)):
                parsed = parse_line(self.lines[line_number])
                if parsed and instance_id_from_key(parsed.key):
                    last_instance_line = line_number
            self.lines.insert(last_instance_line + 1, serialized)
        self.keys[key] = ConfigKey(key, value, len(self.lines))

    def _delete_key(self, key: str) -> None:
        existing = self.keys.pop(key, None)
        if existing is not None and 1 <= existing.line_number <= len(self.lines):
            del self.lines[existing.line_number - 1]


def backup_config_file(path: str | Path, backup_dir: str | Path | None = None) -> Path:
    """Create a timestamped backup of a configuration file."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"配置文件不存在: {source}")
    target_dir = Path(backup_dir) if backup_dir else source.parent / BACKUP_DIR_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = target_dir / f"{source.name}.{timestamp}.bak"
    shutil.copy2(source, backup_path)
    return backup_path
