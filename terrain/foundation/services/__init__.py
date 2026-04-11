"""Terrain - Services."""

# Re-export protocols from the types layer (L0) for backward compatibility.
# The canonical definitions live in terrain.foundation.types.types.
from terrain.foundation.types.types import IngestorProtocol, QueryProtocol


# Import implementation
from .graph_service import MemgraphIngestor
from .git_service import GitChangeDetector

__all__ = ["IngestorProtocol", "QueryProtocol", "MemgraphIngestor", "GitChangeDetector"]
