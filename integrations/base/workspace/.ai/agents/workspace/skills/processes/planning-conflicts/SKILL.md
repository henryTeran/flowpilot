---
schema_version: base.resource.v1
id: planning-conflicts
type: process
title: Examiner les conflits de planning
description: Examiner les conflits de planning des engagements enregistres pour une collaboratrice.
use_when: Examiner les conflits de planning
scope: personal
status: active
sensitivity: internal
keywords: [conflits, chevauchements]
routing:
  examples:
    - Examiner les conflits de planning
    - Detecter les chevauchements des engagements
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Examiner les conflits de planning

Appeler `PLANNING_CONFLICTS` avec une collaboratrice et une journee explicitement selectionnees. Les sources et permissions FlowPilot restent souveraines. Preserver les incertitudes des engagements depasses ou invalides et la limite de couverture des ressources. Ne pas confondre un chevauchement de creneaux enregistres avec une preuve d activite physique. Aucune mutation.
