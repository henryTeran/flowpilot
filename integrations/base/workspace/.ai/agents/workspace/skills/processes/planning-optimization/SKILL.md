---
schema_version: base.resource.v1
id: planning-optimization
type: process
title: Comparer les scores du planning
description: Comparer les scores du planning avec les sources deterministes FlowPilot.
use_when: Optimiser le planning
scope: personal
status: active
sensitivity: internal
keywords: [planning, optimization]
routing:
  examples:
    - Optimiser le planning
    - Comparer les scores du planning
    - Calculer les scores du planning
    - Optimize the schedule
    - Score the schedule
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Comparer les scores du planning

La resolution de methode autorise seulement une proposition de `PLANNING_OPTIMIZATION`. Une selection explicite et schema-validee reste indispensable. L adaptateur verifie les permissions et le perimetre signe avant d appeler le service existant. Cette resolution ne lit pas les donnees metier et ne confirme aucune execution. Une preparation capture ensuite les preuves par les services officiels FlowPilot. Un original deja retenu se recupere sans rejouer le routage.
