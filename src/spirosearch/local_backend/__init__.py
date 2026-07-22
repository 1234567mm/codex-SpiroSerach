"""V33C local backend database and object store.

Provides SQLite-backed repositories for provider snapshots, sync jobs,
HTL device records, paper sources/assets/groups, knowledge chunks,
manual acquisition tasks, review items, and citation links.
"""
from spirosearch.local_backend.object_store import ObjectStore
from spirosearch.local_backend.repository import (
    CitationLinkRepository,
    HtlDeviceRepository,
    KnowledgeChunkRepository,
    LocalBackendDatabase,
    ManualAcquisitionRepository,
    MaterialEntityRepository,
    PaperAssetRepository,
    PaperGroupRepository,
    PaperSourceRepository,
    ProviderSnapshotRepository,
    ReviewItemRepository,
    SyncJobRepository,
)
from spirosearch.local_backend.schema import SCHEMA_VERSION
from spirosearch.local_backend.vector_index import NoopVectorIndex, VectorIndex

__all__ = [
    "CitationLinkRepository",
    "HtlDeviceRepository",
    "KnowledgeChunkRepository",
    "LocalBackendDatabase",
    "ManualAcquisitionRepository",
    "MaterialEntityRepository",
    "ObjectStore",
    "NoopVectorIndex",
    "PaperAssetRepository",
    "PaperGroupRepository",
    "PaperSourceRepository",
    "ProviderSnapshotRepository",
    "ReviewItemRepository",
    "SCHEMA_VERSION",
    "SyncJobRepository",
    "VectorIndex",
]
