"""Runtime evidence producer for SHAKTI convergence handoff."""

from .canonical import CONTRACT_VERSION, SCHEMA_VERSION
from .producer import produce_evidence_run, validate_evidence_root

__all__ = [
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "produce_evidence_run",
    "validate_evidence_root",
]
