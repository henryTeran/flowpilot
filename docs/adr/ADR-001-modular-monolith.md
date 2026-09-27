# ADR-001 — Modular Monolith

Status: Accepted
Date: 2026-09-28

## Context

FlowPilot doit évoluer rapidement tout en gardant une base technique lisible et maîtrisable par une équipe réduite.

## Decision

FlowPilot reste un modular monolith.

Pas de microservices tant qu'un besoin concret de séparation ou de scaling indépendant n'est pas démontré.

Les modules doivent rester isolés avec dépendances contrôlées.

## Consequences

Le coût opérationnel reste faible et la cohérence métier est plus simple à garantir. Toute proposition de microservice devra être justifiée par des métriques de charge, de couplage ou de cadence de livraison.