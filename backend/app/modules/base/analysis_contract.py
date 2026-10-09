"""Future JV port: deterministic claims must cite captured application evidence.

No JV engine or concrete language provider is implemented in this phase.
"""
from typing import Protocol
from app.modules.crm.metrics import Fact
from app.modules.base.query import Evidence
from app.modules.base.read_capabilities import Digest


class Analysis(Fact):
    evidence_fingerprint: Digest
    observed_facts: tuple[str, ...]
    missing_facts: tuple[str, ...]


class DeterministicAnalyzer(Protocol):
    def analyze(self, evidence: Evidence) -> Analysis:
        """Return source-bound facts; no language generation or business mutation."""
        ...


class LanguageProvider(Protocol):
    def explain(self, analysis: Analysis) -> str:
        """Optional wording only; its text never authorizes an application action."""
        ...
