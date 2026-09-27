# ADR-002 — Provider Independent AI

Status: Accepted
Date: 2026-09-28

## Context

FlowPilot doit éviter tout verrouillage fournisseur et garder une continuité de service même si un provider IA est indisponible.

## Decision

FlowPilot ne dépend pas directement d'OpenAI, Voxtral ou d'un autre provider.

Utiliser des abstractions telles que :

- LLMProvider
- SpeechToTextProvider
- EmbeddingProvider

Les SDK spécifiques provider doivent être isolés dans la couche provider.

La logique métier doit continuer à fonctionner même sans provider IA.

## Consequences

Les intégrations IA sont interchangeables et testables par contrat. Les parcours métier critiques restent disponibles sans dépendance forte à un fournisseur externe.