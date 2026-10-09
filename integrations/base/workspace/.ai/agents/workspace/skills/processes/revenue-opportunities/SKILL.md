---
schema_version: base.resource.v1
id: revenue-opportunities
type: process
title: Examiner les opportunites de revenus
description: Examiner les opportunites de revenus via les projections de capacite FlowPilot.
use_when: Examiner les opportunites de revenus
scope: personal
status: active
sensitivity: internal
keywords: [revenus, opportunites]
routing:
  examples:
    - Examiner les opportunites de revenus
    - Projeter une opportunite de capacite commerciale
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Examiner les opportunites de revenus

Appeler `REVENUE_OPPORTUNITIES` avec un service et un horizon explicites. La responsable authentifiee et les moteurs FlowPilot restent souverains. Respecter les incertitudes de file, qualifications et ressources. La valeur financiere reste inconnue; un creneau conditionnel ne prouve ni revenu ni reservation autorisee. Aucune mutation.
