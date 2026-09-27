# ADR-004 — Human Approval for Sensitive AI Actions

Status: Accepted
Date: 2026-09-28

## Context

Certaines actions déclenchées avec aide IA ont un impact financier, légal ou opérationnel et exigent un contrôle renforcé.

## Decision

Les actions IA sont classées :

- LEVEL 0 = READ
- LEVEL 1 = SUGGEST
- LEVEL 2 = PREPARE
- LEVEL 3 = EXECUTE

Les actions sensibles LEVEL 3 nécessitent selon leur nature :

- permission
- validation métier
- validation humaine
- audit
- idempotence

Aucune action externe sensible ne doit être exécutée directement par un LLM.

## Consequences

Les risques d'exécution non maîtrisée sont réduits. Les opérations sensibles sont contrôlées, auditées et compatibles avec les exigences de conformité.