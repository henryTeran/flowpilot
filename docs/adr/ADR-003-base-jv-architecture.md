# ADR-003 — BASE / JV Architecture

Status: Accepted
Date: 2026-09-28

## Context

FlowPilot vise une architecture IA fiable où le métier reste déterministe et auditable, tout en profitant des capacités linguistiques des LLM.

## Decision

BASE est l'orchestrateur intelligent de FlowPilot.

JV porte l'intelligence métier structurée et déterministe.

Principe : JV produit les faits, LLM produit la langue.

BASE orchestre :

- contexte
- intentions
- capabilities
- permissions
- business rules
- actions
- approvals
- evidence
- audit

Le LLM ne devient jamais la source de vérité métier.

## Consequences

Les décisions métier restent traçables et explicables. Les composants IA conversationnels améliorent l'expérience sans compromettre la gouvernance fonctionnelle.