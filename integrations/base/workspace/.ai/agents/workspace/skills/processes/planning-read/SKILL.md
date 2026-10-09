---
schema_version: base.resource.v1
id: planning-read
type: process
title: Consulter le planning du jour
description: Consulter le planning du jour avec les faits verifies du service FlowPilot.
use_when: Consulter le planning du jour
scope: personal
status: active
sensitivity: internal
keywords: [planning, read]
routing:
  examples:
    - Consulter le planning du jour
    - Afficher les sessions du jour
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Consulter le planning du jour

L adaptateur FlowPilot appelle exclusivement la capacite `PLANNING_READ` dans le contexte de session authentifie. Les references employee_id, service_id et ticket_id doivent etre des selections explicites, pas des identifiants inventes par le modele. Le domaine fournit les resultats; ne pas recalculer les regles de disponibilite, d affectation ou de planning. En cas de refus, selection manquante ou service indisponible, clarifier sans fabriquer de faits. Aucune ecriture metier, confirmation ou execution n est autorisee par ce process.
