---
schema_version: base.resource.v1
id: revenue-loss-analysis
type: process
title: Examiner les pertes de revenus enregistrees
description: Examiner les pertes de revenus enregistrees via les preuves de cloture FlowPilot.
use_when: Examiner les pertes de revenus enregistrees
scope: personal
status: active
sensitivity: internal
keywords: [pertes, annulations]
routing:
  examples:
    - Examiner les pertes de revenus enregistrees
    - Analyser les annulations et absences commerciales
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Examiner les pertes de revenus enregistrees

Appeler `REVENUE_LOSS_ANALYSIS` avec une periode explicite et la responsable authentifiee. Les lecteurs FlowPilot valident les preuves originales. Une annulation ou une absence ne prouve pas une perte financiere causale. Conserver les valeurs commerciales enregistrees, devises, inconnues et limites d historique. Aucune mutation ni cause inventee.
