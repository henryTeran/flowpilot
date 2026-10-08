# ADR-003 — BASE / JV Architecture

Status: Accepted
Date: 2026-09-28

## Context

FlowPilot vise une architecture IA fiable où le métier reste déterministe et auditable, tout en profitant des capacités linguistiques des LLM.

## Decision

Clarification acceptée le 2026-10-08: BASE est le framework officiel [ai-swiss/base](https://github.com/ai-swiss/base). Les agents, procédures et ressources suivent son standard; l'orchestration des services métier est portée par les adaptateurs FlowPilot. Voir [le plan d'intégration](../architecture/BASE_UPSTREAM_INTEGRATION.md).

JV porte l'intelligence métier structurée et déterministe.

Principe : JV produit les faits, LLM produit la langue.

Les adaptateurs FlowPilot autour du framework assurent :

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