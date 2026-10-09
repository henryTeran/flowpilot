---
schema_version: base.resource.v1
id: client-rebooking-opportunities
type: process
title: Examiner les opportunites de reprise rendez-vous
description: Examiner les opportunites de reprise rendez-vous cliente avec la politique CRM et les soins observes.
use_when: Examiner les opportunites de reprise rendez-vous
scope: personal
status: active
sensitivity: internal
keywords: [reprise, rebooking, opportunites]
routing:
  examples:
    - Examiner les opportunites de reprise rendez-vous
    - Quand proposer une reprise de rendez-vous
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Examiner les opportunites de reprise rendez-vous

Appeler uniquement `CLIENT_REBOOKING_OPPORTUNITIES` pour la cliente explicitement selectionnee. La responsable authentifiee et les services CRM deterministes restent souverains. Respecter les sources manquantes, la politique originale et les rendez-vous actifs. La suggestion n autorise aucune reservation, communication externe ou mutation. Ne pas inventer de periodicite ou de soin.
