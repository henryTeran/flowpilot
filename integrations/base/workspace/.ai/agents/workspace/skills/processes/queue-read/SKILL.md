---
schema_version: base.resource.v1
id: queue-read
type: process
title: Consulter la file operationnelle
description: Consulter la file operationnelle avec les faits verifies du service FlowPilot.
use_when: Consulter la file operationnelle
scope: personal
status: active
sensitivity: internal
keywords: [queue, read]
routing:
  examples:
    - Consulter la file operationnelle
    - Afficher la file des clientes
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Consulter la file operationnelle

L adaptateur FlowPilot appelle exclusivement la capacite `QUEUE_READ` dans le contexte de session authentifie. Les references employee_id, service_id et ticket_id doivent etre des selections explicites, pas des identifiants inventes par le modele. Le domaine fournit les resultats; ne pas recalculer les regles de disponibilite, d affectation ou de planning. En cas de refus, selection manquante ou service indisponible, clarifier sans fabriquer de faits. Aucune ecriture metier, confirmation ou execution n est autorisee par ce process.
