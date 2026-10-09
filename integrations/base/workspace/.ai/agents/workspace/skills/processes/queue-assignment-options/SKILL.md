---
schema_version: base.resource.v1
id: queue-assignment-options
type: process
title: Options d affectation de la file
description: Options d affectation de la file avec les faits verifies du service FlowPilot.
use_when: Qui peut prendre cette cliente maintenant
scope: personal
status: active
sensitivity: internal
keywords: [queue, assignment, options]
routing:
  examples:
    - Qui peut prendre cette cliente maintenant
    - Examiner les options d affectation de cette cliente
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Options d affectation de la file

L adaptateur FlowPilot appelle exclusivement la capacite `QUEUE_ASSIGNMENT_OPTIONS` dans le contexte de session authentifie. Les references employee_id, service_id et ticket_id doivent etre des selections explicites, pas des identifiants inventes par le modele. Le domaine fournit les resultats; ne pas recalculer les regles de disponibilite, d affectation ou de planning. En cas de refus, selection manquante ou service indisponible, clarifier sans fabriquer de faits. Aucune ecriture metier, confirmation ou execution n est autorisee par ce process.
