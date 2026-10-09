---
schema_version: base.resource.v1
id: employee-capacity
type: process
title: Mesurer la capacite enregistree des collaboratrices
description: Mesurer la capacite enregistree des collaboratrices avec les sources FlowPilot autorisees.
use_when: Mesurer la capacite enregistree des collaboratrices
scope: personal
status: active
sensitivity: internal
keywords: [employee, capacity]
routing:
  examples:
    - Mesurer la capacite enregistree des collaboratrices
    - Consulter la capacite enregistree du personnel
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Mesurer la capacite enregistree des collaboratrices

Appeler exclusivement `EMPLOYEE_CAPACITY` dans le contexte authentifie. Toute journee ou reference de service doit venir de la selection explicite de l interface. Reutiliser les moteurs FlowPilot; ne pas inventer les horaires, les capacites physiques ou la possibilite de reserver. Preserver les sources manquantes, diagnostics et limites. Aucune mutation.
