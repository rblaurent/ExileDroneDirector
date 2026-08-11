"""Engine-independent server repository and recoverable-storage oracle.

The shipped mod remains Blueprint-only. This module fixes the behavioral
contract for the Blueprint repository/service/storage split before those graphs
are built in the DevKit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from flypath_document import (
    DocumentValidationError,
    FlypathRecord,
    RevisionConflictError,
    RevisionDocument,
    clone_published,
    create_private_flypath,
    deserialize_record,
    publish,
    save_draft,
    serialize_record,
    utc_text,
    validate_record,
)


class ResultCode(str, Enum):
    SUCCESS = "Success"
    NOT_FOUND = "NotFound"
    FORBIDDEN = "Forbidden"
    REVISION_CONFLICT = "RevisionConflict"
    VALIDATION_FAILED = "ValidationFailed"
    LIMIT_EXCEEDED = "LimitExceeded"
    REGION_FORBIDDEN = "RegionForbidden"
    PERSISTENCE_UNAVAILABLE = "PersistenceUnavailable"
    ALREADY_EXISTS = "AlreadyExists"


T = TypeVar("T")


@dataclass(frozen=True)
class RepositoryResult(Generic[T]):
    code: ResultCode
    value: T | None = None
    current_revision: int | None = None
    detail: str = ""

    @property
    def succeeded(self) -> bool:
        return self.code is ResultCode.SUCCESS


@dataclass(frozen=True)
class RepositoryLimits:
    max_paths_per_owner: int = 64
    max_waypoints_per_path: int = 512
    max_serialized_bytes: int = 2_000_000
    max_title_chars: int = 96
    allowed_regions: tuple[str, ...] = ("ExiledLands", "Siptah")


@dataclass(frozen=True)
class FlypathMetadata:
    flypath_id: str
    owner_display_name: str
    title: str
    visibility: str
    region_id: str
    updated_utc: str
    draft_revision_number: int
    published_revision_number: int | None


@dataclass(frozen=True)
class MetadataPage:
    items: tuple[FlypathMetadata, ...]
    offset: int
    total: int
    has_more: bool


@dataclass
class StoredGeneration:
    generation: int
    payload: str | None
    committed: bool = False


class RecoverableMemoryStorage:
    """Copy-on-write storage model used to prove restart/recovery semantics.

    A Blueprint adapter must expose equivalent Stage/Commit/Activate behavior.
    `payload=None` is a committed tombstone. Recovery scans committed generations
    newest-first, ignores incomplete candidates, and falls back past corrupt data.
    """

    def __init__(self) -> None:
        self.generations: dict[str, list[StoredGeneration]] = {}
        self.active_generation: dict[str, int] = {}
        self.available = True

    def stage(self, flypath_id: str, payload: str | None) -> int:
        if not self.available:
            raise OSError("storage unavailable")
        records = self.generations.setdefault(flypath_id, [])
        generation = records[-1].generation + 1 if records else 1
        records.append(StoredGeneration(generation, payload, committed=False))
        return generation

    def commit(self, flypath_id: str, generation: int) -> None:
        if not self.available:
            raise OSError("storage unavailable")
        self._generation(flypath_id, generation).committed = True

    def activate(self, flypath_id: str, generation: int) -> None:
        if not self.available:
            raise OSError("storage unavailable")
        candidate = self._generation(flypath_id, generation)
        if not candidate.committed:
            raise ValueError("cannot activate an uncommitted generation")
        self.active_generation[flypath_id] = generation

    def atomic_write(self, record: FlypathRecord) -> None:
        payload = serialize_record(record)
        generation = self.stage(record.flypath_id, payload)
        self.commit(record.flypath_id, generation)
        self.activate(record.flypath_id, generation)

    def atomic_delete(self, flypath_id: str) -> None:
        generation = self.stage(flypath_id, None)
        self.commit(flypath_id, generation)
        self.activate(flypath_id, generation)

    def recover(self) -> dict[str, FlypathRecord]:
        if not self.available:
            raise OSError("storage unavailable")
        recovered: dict[str, FlypathRecord] = {}
        for flypath_id, generations in self.generations.items():
            committed = sorted(
                (item for item in generations if item.committed),
                key=lambda item: item.generation,
                reverse=True,
            )
            for item in committed:
                if item.payload is None:
                    break
                try:
                    record = deserialize_record(item.payload)
                except DocumentValidationError:
                    continue
                if record.flypath_id != flypath_id:
                    continue
                recovered[flypath_id] = record
                break
        return recovered

    def _generation(self, flypath_id: str, generation: int) -> StoredGeneration:
        for candidate in self.generations.get(flypath_id, []):
            if candidate.generation == generation:
                return candidate
        raise KeyError((flypath_id, generation))


class FlypathRepository:
    """Server-authoritative repository contract with typed results."""

    def __init__(
        self,
        storage: RecoverableMemoryStorage,
        *,
        limits: RepositoryLimits = RepositoryLimits(),
    ) -> None:
        self.storage = storage
        self.limits = limits
        self.records: dict[str, FlypathRecord] = {}

    def load(self) -> RepositoryResult[int]:
        try:
            recovered = self.storage.recover()
        except OSError as error:
            return RepositoryResult(ResultCode.PERSISTENCE_UNAVAILABLE, detail=str(error))
        self.records = recovered
        return RepositoryResult(ResultCode.SUCCESS, len(recovered))

    def create(
        self,
        *,
        requester_account_id: str,
        requester_display_name: str,
        flypath_id: str,
        title: str,
        region_id: str,
        now: datetime,
    ) -> RepositoryResult[FlypathRecord]:
        if flypath_id in self.records:
            return RepositoryResult(ResultCode.ALREADY_EXISTS)
        owned = sum(
            record.owner_account_id == requester_account_id
            for record in self.records.values()
        )
        if owned >= self.limits.max_paths_per_owner:
            return RepositoryResult(ResultCode.LIMIT_EXCEEDED, detail="owner path limit")
        if region_id not in self.limits.allowed_regions:
            return RepositoryResult(ResultCode.REGION_FORBIDDEN)
        if len(title) > self.limits.max_title_chars:
            return RepositoryResult(ResultCode.LIMIT_EXCEEDED, detail="title length")
        try:
            record = create_private_flypath(
                flypath_id=flypath_id,
                owner_account_id=requester_account_id,
                owner_display_name=requester_display_name,
                title=title,
                region_id=region_id,
                now=now,
            )
            return self._persist(record)
        except DocumentValidationError as error:
            return RepositoryResult(ResultCode.VALIDATION_FAILED, detail=str(error))

    def save(
        self,
        *,
        requester_account_id: str,
        flypath_id: str,
        expected_revision: int,
        candidate: RevisionDocument,
        now: datetime,
    ) -> RepositoryResult[FlypathRecord]:
        record = self.records.get(flypath_id)
        access = self._owner_record(record, requester_account_id)
        if access is not None:
            return access
        assert record is not None
        if len(candidate.waypoints) > self.limits.max_waypoints_per_path:
            return RepositoryResult(ResultCode.LIMIT_EXCEEDED, detail="waypoint limit")
        try:
            updated = save_draft(
                record,
                candidate,
                expected_revision=expected_revision,
                now=now,
            )
            return self._persist(updated)
        except RevisionConflictError as error:
            return RepositoryResult(
                ResultCode.REVISION_CONFLICT,
                current_revision=record.draft_revision_number,
                detail=str(error),
            )
        except DocumentValidationError as error:
            return RepositoryResult(ResultCode.VALIDATION_FAILED, detail=str(error))

    def get_draft(
        self, *, requester_account_id: str, flypath_id: str
    ) -> RepositoryResult[RevisionDocument]:
        record = self.records.get(flypath_id)
        access = self._owner_record(record, requester_account_id)
        if access is not None:
            return RepositoryResult(access.code, current_revision=access.current_revision)
        assert record is not None
        return RepositoryResult(ResultCode.SUCCESS, record.draft)

    def publish(
        self,
        *,
        requester_account_id: str,
        flypath_id: str,
        expected_revision: int,
        now: datetime,
    ) -> RepositoryResult[FlypathRecord]:
        record = self.records.get(flypath_id)
        access = self._owner_record(record, requester_account_id)
        if access is not None:
            return access
        assert record is not None
        if expected_revision != record.draft_revision_number:
            return RepositoryResult(
                ResultCode.REVISION_CONFLICT,
                current_revision=record.draft_revision_number,
            )
        return self._persist(publish(record, now=now))

    def unpublish(
        self,
        *,
        requester_account_id: str,
        flypath_id: str,
        expected_revision: int,
        now: datetime,
    ) -> RepositoryResult[FlypathRecord]:
        record = self.records.get(flypath_id)
        access = self._owner_record(record, requester_account_id)
        if access is not None:
            return access
        assert record is not None
        if expected_revision != record.draft_revision_number:
            return RepositoryResult(
                ResultCode.REVISION_CONFLICT,
                current_revision=record.draft_revision_number,
            )
        updated = replace(record, visibility="private", updated_utc=utc_text(now))
        return self._persist(updated)

    def get_published(self, *, flypath_id: str) -> RepositoryResult[RevisionDocument]:
        record = self.records.get(flypath_id)
        if record is None or record.visibility != "public" or record.published is None:
            return RepositoryResult(ResultCode.NOT_FOUND)
        return RepositoryResult(ResultCode.SUCCESS, record.published)

    def clone(
        self,
        *,
        requester_account_id: str,
        requester_display_name: str,
        source_flypath_id: str,
        source_revision: int,
        clone_flypath_id: str,
        now: datetime,
    ) -> RepositoryResult[FlypathRecord]:
        source = self.records.get(source_flypath_id)
        if source is None or source.visibility != "public" or source.published is None:
            return RepositoryResult(ResultCode.NOT_FOUND)
        if source.published_revision_number != source_revision:
            return RepositoryResult(
                ResultCode.REVISION_CONFLICT,
                current_revision=source.published_revision_number,
            )
        if clone_flypath_id in self.records:
            return RepositoryResult(ResultCode.ALREADY_EXISTS)
        owned = sum(
            record.owner_account_id == requester_account_id
            for record in self.records.values()
        )
        if owned >= self.limits.max_paths_per_owner:
            return RepositoryResult(ResultCode.LIMIT_EXCEEDED, detail="owner path limit")
        try:
            clone = clone_published(
                source,
                flypath_id=clone_flypath_id,
                owner_account_id=requester_account_id,
                owner_display_name=requester_display_name,
                now=now,
            )
            return self._persist(clone)
        except DocumentValidationError as error:
            return RepositoryResult(ResultCode.VALIDATION_FAILED, detail=str(error))

    def delete(
        self,
        *,
        requester_account_id: str,
        flypath_id: str,
        expected_revision: int,
    ) -> RepositoryResult[None]:
        record = self.records.get(flypath_id)
        access = self._owner_record(record, requester_account_id)
        if access is not None:
            return RepositoryResult(access.code, current_revision=access.current_revision)
        assert record is not None
        if expected_revision != record.draft_revision_number:
            return RepositoryResult(
                ResultCode.REVISION_CONFLICT,
                current_revision=record.draft_revision_number,
            )
        try:
            self.storage.atomic_delete(flypath_id)
        except OSError as error:
            return RepositoryResult(ResultCode.PERSISTENCE_UNAVAILABLE, detail=str(error))
        del self.records[flypath_id]
        return RepositoryResult(ResultCode.SUCCESS)

    def list_mine(
        self, *, requester_account_id: str, offset: int = 0, limit: int = 20
    ) -> RepositoryResult[MetadataPage]:
        if not requester_account_id.strip():
            return RepositoryResult(
                ResultCode.VALIDATION_FAILED, detail="invalid requester account id"
            )
        records = [
            record
            for record in self.records.values()
            if record.owner_account_id == requester_account_id
        ]
        return RepositoryResult(ResultCode.SUCCESS, self._page(records, offset, limit))

    def list_public(
        self, *, offset: int = 0, limit: int = 20
    ) -> RepositoryResult[MetadataPage]:
        records = [record for record in self.records.values() if record.visibility == "public"]
        return RepositoryResult(ResultCode.SUCCESS, self._page(records, offset, limit))

    def _persist(self, record: FlypathRecord) -> RepositoryResult[FlypathRecord]:
        try:
            validate_record(record)
            encoded = serialize_record(record)
            if len(encoded.encode("utf-8")) > self.limits.max_serialized_bytes:
                return RepositoryResult(ResultCode.LIMIT_EXCEEDED, detail="serialized bytes")
            self.storage.atomic_write(record)
        except OSError as error:
            return RepositoryResult(ResultCode.PERSISTENCE_UNAVAILABLE, detail=str(error))
        except DocumentValidationError as error:
            return RepositoryResult(ResultCode.VALIDATION_FAILED, detail=str(error))
        self.records[record.flypath_id] = record
        return RepositoryResult(ResultCode.SUCCESS, record)

    @staticmethod
    def _owner_record(
        record: FlypathRecord | None, requester_account_id: str
    ) -> RepositoryResult[FlypathRecord] | None:
        if record is None:
            return RepositoryResult(ResultCode.NOT_FOUND)
        if record.owner_account_id != requester_account_id:
            return RepositoryResult(ResultCode.FORBIDDEN)
        return None

    @staticmethod
    def _metadata(record: FlypathRecord) -> FlypathMetadata:
        return FlypathMetadata(
            flypath_id=record.flypath_id,
            owner_display_name=record.owner_display_name,
            title=record.title,
            visibility=record.visibility,
            region_id=record.region_id,
            updated_utc=record.updated_utc,
            draft_revision_number=record.draft_revision_number,
            published_revision_number=record.published_revision_number,
        )

    @classmethod
    def _page(
        cls, records: list[FlypathRecord], offset: int, limit: int
    ) -> MetadataPage:
        safe_offset = max(0, offset)
        safe_limit = max(1, min(100, limit))
        ordered = sorted(records, key=lambda record: (record.updated_utc, record.flypath_id), reverse=True)
        selected = ordered[safe_offset : safe_offset + safe_limit]
        return MetadataPage(
            items=tuple(cls._metadata(record) for record in selected),
            offset=safe_offset,
            total=len(ordered),
            has_more=safe_offset + len(selected) < len(ordered),
        )
