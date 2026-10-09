---
schema_version: base.resource.v1
id: planning-gaps
type: process
title: Consulter les creneaux libres du planning
description: Consulter les creneaux libres du planning avec les sources FlowPilot autorisees.
use_when: Consulter les creneaux libres du planning
scope: personal
status: active
sensitivity: internal
keywords: [planning, gaps]
routing:
  examples:
    - Consulter les creneaux libres du planning
    - Consulter les creneaux libres
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Consulter les creneaux libres du planning

Appeler exclusivement `PLANNING_GAPS` dans le contexte authentifie. Toute journee ou reference de service doit venir de la selection explicite de l interface. Reutiliser les moteurs FlowPilot; ne pas inventer les horaires, les capacites physiques ou la possibilite de reserver. Preserver les sources manquantes, diagnostics et limites. Aucune mutation.
