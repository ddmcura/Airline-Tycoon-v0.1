"""Durable, whole-world Stage 1 career saves.

File identities and integrity metadata are deliberately outside world authority.
All public operations either return a validated detached world or leave files and
the caller's live world alone on failure.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from .migration import (
    migrate_schema_1_to_2, migrate_schema_2_to_3, migrate_schema_3_to_4,
    migrate_schema_4_to_5, migrate_schema_5_to_6, migrate_schema_6_to_7,
)
from .schema import LATEST_SAVE_SCHEMA_VERSION
from .validation import validate_world


FILE_VERSION = 1
AUTOSAVE_COUNT = 3
DEFAULT_SAVE_ROOT = Path(__file__).resolve().parents[2] / "Saves" / "stage1"


class SaveError(ValueError):
    """A file or compatibility failure suitable for a terminal diagnostic."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(world):
    return hashlib.sha256(_canonical(world)).hexdigest()


def _career_id(value):
    if not isinstance(value, str) or len(value) != 32:
        raise SaveError("INVALID_CAREER", "Invalid career identifier")
    try:
        if uuid.UUID(hex=value).hex != value:
            raise ValueError("noncanonical UUID")
    except ValueError as exc:
        raise SaveError("INVALID_CAREER", "Invalid career identifier") from exc
    return value


def _airline_name(world):
    state = world["world_state"]
    airline_id = state["player"]["primary_airline_id"]
    return state["airlines"][airline_id]["display_name"]


def _validated(world):
    result = validate_world(world)
    if not result.is_valid:
        first = result.errors[0]
        raise SaveError("INVALID_WORLD", f"{first.path}: {first.message}")


def _migrated(source, *, foundation_snapshot=None):
    """Upgrade a detached source through every adjacent schema boundary."""
    world = deepcopy(source)
    metadata = world.get("metadata") if type(world) is dict else None
    version = metadata.get("save_schema_version") if type(metadata) is dict else None
    if type(version) is not int:
        raise SaveError("INVALID_SCHEMA", "Missing or invalid save schema version")
    if version > LATEST_SAVE_SCHEMA_VERSION:
        raise SaveError("NEWER_SCHEMA", f"Save schema {version} is newer than supported schema {LATEST_SAVE_SCHEMA_VERSION}")
    if version < 1:
        raise SaveError("INVALID_SCHEMA", "Unsupported save schema version")
    _validated(world)
    while version < LATEST_SAVE_SCHEMA_VERSION:
        if version == 1:
            if foundation_snapshot is None:
                raise SaveError("FOUNDATION_REQUIRED", "Schema 1 requires its approved historical country foundation snapshot")
            result = migrate_schema_1_to_2(world, foundation_snapshot=foundation_snapshot)
            if not result.succeeded:
                issue = result.issues[0] if result.issues else None
                raise SaveError("MIGRATION_FAILED", issue.message if issue else "Schema 1 migration failed")
        else:
            migrate = {
                2: migrate_schema_2_to_3,
                3: migrate_schema_3_to_4,
                4: migrate_schema_4_to_5,
                5: migrate_schema_5_to_6,
                6: migrate_schema_6_to_7,
            }[version]
            result = migrate(world)
            if not result.succeeded:
                issue = result.issues[0] if result.issues else None
                raise SaveError("MIGRATION_FAILED", issue.message if issue else f"Schema {version} migration failed")
            world = result.migrated_world
        version += 1
        _validated(world)
    world["simulation"]["clock_state"] = "PAUSED"
    world["simulation"]["fast_forward"]["target_time_utc"] = None
    _validated(world)
    # These indexes are disposable; constructing one now detects broken queue
    # ordering before the candidate is exposed to the active session.
    from game.simulation.kernel import build_event_queue_index
    build_event_queue_index(world)
    return world


class SaveStore:
    def __init__(self, root=DEFAULT_SAVE_ROOT):
        self.root = Path(root)

    def new_career_id(self):
        return uuid.uuid4().hex

    def _directory(self, career_id):
        return self.root / _career_id(career_id)

    def _path(self, career_id, kind, bookmark_id=None, autosave_index=None):
        directory = self._directory(career_id)
        if kind == "manual":
            return directory / "manual.json"
        if kind == "autosave":
            if type(autosave_index) is not int or not 0 <= autosave_index < AUTOSAVE_COUNT:
                raise SaveError("INVALID_AUTOSAVE", "Invalid autosave position")
            return directory / f"autosave-{autosave_index}.json"
        if kind == "bookmark":
            return directory / f"bookmark-{_career_id(bookmark_id)}.json"
        raise SaveError("INVALID_KIND", "Unknown save kind")

    def _read(self, path, *, expected_career=None):
        try:
            with path.open("rb") as stream:
                data = json.load(stream)
        except (OSError, ValueError, UnicodeError) as exc:
            raise SaveError("CORRUPT_FILE", f"Cannot read {path.name}: {exc}") from exc
        if type(data) is not dict or set(data) != {"file_version", "career_id", "kind", "bookmark_id", "bookmark_name", "saved_at_real_utc", "save_serial", "progression_revision", "world", "integrity_sha256"}:
            raise SaveError("CORRUPT_FILE", f"Invalid save container in {path.name}")
        if data["file_version"] != FILE_VERSION or type(data["file_version"]) is not int:
            raise SaveError("UNSUPPORTED_FILE", "Unsupported save file version")
        _career_id(data["career_id"])
        if expected_career is not None and data["career_id"] != expected_career:
            raise SaveError("CAREER_MISMATCH", "Save belongs to another career")
        if data["kind"] not in {"manual", "autosave", "bookmark"}:
            raise SaveError("CORRUPT_FILE", "Invalid save kind")
        if type(data["progression_revision"]) is not int or data["progression_revision"] < 0:
            raise SaveError("CORRUPT_FILE", "Invalid progression revision")
        if type(data["save_serial"]) is not int or data["save_serial"] < 1:
            raise SaveError("CORRUPT_FILE", "Invalid save serial")
        try:
            expected = _digest({key: value for key, value in data.items()
                                if key != "integrity_sha256"})
        except (TypeError, ValueError) as exc:
            raise SaveError("CORRUPT_FILE", "Invalid world encoding") from exc
        if data["integrity_sha256"] != expected:
            raise SaveError("CORRUPT_FILE", "Save integrity check failed")
        return data

    def _read_best(self, path, *, expected_career=None):
        try:
            return self._read(path, expected_career=expected_career)
        except SaveError as original:
            try:
                recovered = self._read(path.with_suffix(".previous"),
                                       expected_career=expected_career)
                recovered['_recovered_from_previous'] = True
                return recovered
            except SaveError:
                raise original

    def _write(self, path, data):
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        previous_tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".prevtmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve semantic insertion order inside versioned domain records.
            # Some approved fingerprints and validators depend on ordered maps.
            payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False,
                                 allow_nan=False).encode("utf-8")
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_data = self._read(temporary, expected_career=data["career_id"])
            _validated(temporary_data['world'])
            if path.exists():
                try:
                    previous_current = self._read(path, expected_career=data["career_id"])
                    current_world = previous_current['world']
                    current_metadata = current_world.get('metadata') if type(current_world) is dict else None
                    current_schema = current_metadata.get('save_schema_version') if type(current_metadata) is dict else None
                    if type(current_schema) is int and current_schema > LATEST_SAVE_SCHEMA_VERSION:
                        raise SaveError('NEWER_SCHEMA', 'Refusing to replace a newer save schema')
                    _validated(previous_current['world'])
                except SaveError as exc:
                    if exc.code == 'NEWER_SCHEMA':
                        raise
                    pass  # Never replace a known-good recovery copy with corrupt data.
                else:
                    shutil.copyfile(path, previous_tmp)
                    with previous_tmp.open("r+b") as stream:
                        os.fsync(stream.fileno())
                    previous_data = self._read(previous_tmp, expected_career=data["career_id"])
                    _validated(previous_data['world'])
                    os.replace(previous_tmp, path.with_suffix(".previous"))
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as exc:
            if isinstance(exc, SaveError):
                raise
            raise SaveError("WRITE_FAILED", f"Save was not committed: {exc}") from exc
        finally:
            for leftover in (temporary, previous_tmp):
                try:
                    leftover.unlink(missing_ok=True)
                except OSError:
                    pass

    def save(self, career_id, kind, world, *, bookmark_name=None,
             bookmark_id=None, progression_revision=0):
        _career_id(career_id)
        prior = self._entries(career_id)
        lineage = world.get('metadata', {}).get('lineage_id') if type(world) is dict else None
        if any(e['world']['metadata']['lineage_id'] != lineage for e in prior):
            raise SaveError('CAREER_MISMATCH', 'World lineage does not match this career')
        save_serial = max((e["save_serial"] for e in prior), default=0) + 1
        if kind == "bookmark":
            if not isinstance(bookmark_name, str) or not bookmark_name.strip() or len(bookmark_name.strip()) > 80:
                raise SaveError("INVALID_NAME", "Bookmark name must contain 1–80 characters")
            bookmark_name = bookmark_name.strip()
            if any(e['kind'] == 'bookmark' and e['bookmark_name'].casefold() == bookmark_name.casefold()
                   for e in prior):
                raise SaveError("BOOKMARK_EXISTS", "A bookmark with this name already exists")
            bookmark_id = bookmark_id or uuid.uuid4().hex
            path = self._path(career_id, kind, bookmark_id)
            if path.exists() and bookmark_id is not None:
                raise SaveError("BOOKMARK_EXISTS", "Bookmark already exists; delete it explicitly before reusing its name")
        else:
            bookmark_name = None
            bookmark_id = None
            if kind == "autosave":
                present = []
                for index in range(AUTOSAVE_COUNT):
                    candidate = self._path(career_id, kind, autosave_index=index)
                    if not candidate.exists():
                        path = candidate
                        break
                    try:
                        item = self._read(candidate, expected_career=career_id)
                        present.append((item["save_serial"], index))
                    except SaveError:
                        present.append((0, index))
                else:
                    path = self._path(career_id, kind,
                                      autosave_index=min(present)[1])
            else:
                path = self._path(career_id, kind)
        snapshot = deepcopy(world)
        _validated(snapshot)
        data = {
            "file_version": FILE_VERSION,
            "career_id": career_id,
            "kind": kind,
            "bookmark_id": bookmark_id,
            "bookmark_name": bookmark_name,
            "saved_at_real_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "save_serial": save_serial,
            "progression_revision": progression_revision,
            "world": snapshot,
        }
        data["integrity_sha256"] = _digest(data)
        self._write(path, data)
        return bookmark_id

    def load(self, career_id, kind="manual", *, bookmark_id=None,
             autosave_index=None,
             foundation_snapshot=None):
        if kind == "autosave" and autosave_index is None:
            autosave_index = self._latest_autosave_index(career_id)
        path = self._path(career_id, kind, bookmark_id, autosave_index)
        data = self._read_best(path, expected_career=career_id)
        if data["kind"] != kind or data["bookmark_id"] != bookmark_id:
            raise SaveError("SAVE_MISMATCH", "Selected save type does not match its file")
        try:
            candidate = _migrated(data["world"], foundation_snapshot=foundation_snapshot)
        except SaveError as exc:
            if exc.code != 'INVALID_WORLD' or data.get('_recovered_from_previous'):
                raise
            recovered = self._read(path.with_suffix('.previous'), expected_career=career_id)
            candidate = _migrated(recovered['world'], foundation_snapshot=foundation_snapshot)
            recovered['_recovered_from_previous'] = True
            data = recovered
        return candidate, data

    def _entries(self, career_id):
        directory = self._directory(career_id)
        if not directory.is_dir():
            return []
        paths = [directory / "manual.json"]
        paths.extend(self._path(career_id, "autosave", autosave_index=i)
                     for i in range(AUTOSAVE_COUNT))
        paths.extend(sorted(directory.glob("bookmark-*.json")))
        found = []
        for path in paths:
            if not path.exists() and not path.with_suffix(".previous").exists():
                continue
            data = None
            try:
                data = self._read_best(path, expected_career=career_id)
                _validated(data['world'])
            except SaveError:
                if type(data) is dict and (
                    type(data.get('world')) is dict and
                    type(data['world'].get('metadata')) is dict and
                    type(data['world']['metadata'].get('save_schema_version')) is int and
                    data['world']['metadata']['save_schema_version'] > LATEST_SAVE_SCHEMA_VERSION
                ):
                    continue
                try:
                    data = self._read(path.with_suffix('.previous'),
                                      expected_career=career_id)
                    _validated(data['world'])
                    data['_recovered_from_previous'] = True
                except SaveError:
                    continue
            found.append(data)
        return found

    def list_careers(self):
        if not self.root.is_dir():
            return ()
        careers = []
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir():
                continue
            try:
                career_id = _career_id(directory.name)
                entries = self._entries(career_id)
                chosen = next((item for item in entries if item["kind"] == "manual"),
                              entries[0] if entries else None)
                if chosen is not None:
                    careers.append({"career_id": career_id,
                                    "airline_name": _airline_name(chosen["world"]),
                                    "simulation_time_utc": chosen["world"]["simulation"]["time_utc"],
                                    "has_manual": any(e["kind"] == "manual" for e in entries),
                                    "has_autosave": any(e["kind"] == "autosave" for e in entries),
                                    "unreadable": False})
                elif any(directory.glob('*.json')) or any(directory.glob('*.previous')):
                    diagnostic = 'CORRUPT_FILE'
                    display = f"[Unreadable career {career_id[:8]}]"
                    for path in (directory / 'manual.json',
                                 *(directory / f'autosave-{i}.json'
                                   for i in range(AUTOSAVE_COUNT))):
                        try:
                            raw = self._read(path, expected_career=career_id)
                            version = raw['world']['metadata']['save_schema_version']
                            if type(version) is int and version > LATEST_SAVE_SCHEMA_VERSION:
                                diagnostic = 'NEWER_SCHEMA'
                            display = _airline_name(raw['world'])
                            break
                        except (KeyError, SaveError, TypeError):
                            continue
                    careers.append({"career_id": career_id,
                                    "airline_name": display,
                                    "simulation_time_utc": "unavailable",
                                    "has_manual": False, "has_autosave": False,
                                    "unreadable": True, "diagnostic": diagnostic})
            except (KeyError, SaveError, TypeError):
                continue
        return tuple(careers)

    def list_bookmarks(self, career_id):
        return tuple({"bookmark_id": e["bookmark_id"], "name": e["bookmark_name"],
                      "simulation_time_utc": e["world"]["simulation"]["time_utc"]}
                     for e in self._entries(career_id) if e["kind"] == "bookmark")

    def newer_autosave(self, career_id):
        entries = self._entries(career_id)
        manual = next((e for e in entries if e["kind"] == "manual"), None)
        autos = []
        for entry in entries:
            if entry['kind'] != 'autosave':
                continue
            try:
                _migrated(entry['world'])
            except SaveError:
                continue
            autos.append(entry)
        auto = max(autos, key=lambda e: e["save_serial"]) if autos else None
        if auto is None:
            return False
        if manual is None:
            return True
        manual_time = manual["world"]["simulation"]["time_utc"]
        auto_time = auto["world"]["simulation"]["time_utc"]
        return auto_time > manual_time or (auto_time == manual_time and
            auto["progression_revision"] > manual["progression_revision"])

    def _latest_autosave_index(self, career_id):
        candidates = []
        for index in range(AUTOSAVE_COUNT):
            path = self._path(career_id, "autosave", autosave_index=index)
            try:
                data = self._read_best(path, expected_career=career_id)
                try:
                    _migrated(data['world'])
                except SaveError as exc:
                    if exc.code != 'INVALID_WORLD' or data.get('_recovered_from_previous'):
                        raise
                    data = self._read(path.with_suffix('.previous'),
                                      expected_career=career_id)
                    _migrated(data['world'])
                candidates.append((data["save_serial"], index))
            except SaveError:
                continue
        if not candidates:
            raise SaveError("MISSING_AUTOSAVE", "No valid autosave exists")
        return max(candidates)[1]

    def delete_bookmark(self, career_id, bookmark_id):
        path = self._path(career_id, "bookmark", bookmark_id)
        self._read(path, expected_career=career_id)
        path.unlink()
        path.with_suffix(".previous").unlink(missing_ok=True)
