---
schema_version: base.resource.v1
id: employee-availability
type: process
title: Disponibilite des collaboratrices
description: Disponibilite des collaboratrices avec les faits verifies du service FlowPilot.
use_when: Consulter la disponibilite des collaboratrices
scope: personal
status: active
sensitivity: internal
keywords: [employee, availability]
routing:
  examples:
    - Consulter la disponibilite des collaboratrices
    - Qui est disponible maintenant
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Disponibilite des collaboratrices

L adaptateur FlowPilot appelle exclusivement la capacite `EMPLOYEE_AVAILABILITY` dans le contexte de session authentifie. Les references employee_id, service_id et ticket_id doivent etre des selections explicites, pas des identifiants inventes par le modele. Le domaine fournit les resultats; ne pas recalculer les regles de disponibilite, d affectation ou de planning. En cas de refus, selection manquante ou service indisponible, clarifier sans fabriquer de faits. Aucune ecriture metier, confirmation ou execution n est autorisee par ce process.
