"""Generate user-agent strings and client hints from upstream Chrome releases."""

from .build import build_document, latest_document
from .environments import ENVIRONMENTS

__all__ = ["build_document", "latest_document", "ENVIRONMENTS"]
