---
schema_version: base.resource.v1
id: revenue-opportunities
type: process
title: Examiner les opportunites de revenus
description: Examiner les opportunites de revenus via les projections de capacite ou les reprises observees FlowPilot.
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

Appeler `REVENUE_OPPORTUNITIES` selon la source explicitement selectionnee dans l'interface. La source `capacity` (par defaut) exige un service et un horizon explicites. La source `rebooking` consulte les reprises dues de l'institut selon les soins observes et la politique CRM originale; elle refuse les selections de capacite et retourne la premiere page avec les comptes du groupe complet. Ne pas deduire la source, les identifiants ou les dates depuis le message. La responsable authentifiee et les moteurs FlowPilot restent souverains. Respecter les incertitudes de file, qualifications et ressources, ainsi que les diagnostics CRM. La valeur financiere reste inconnue; ni un creneau conditionnel ni une reprise due ne prouvent un revenu, une permission de contact ou une reservation autorisee. Aucune mutation.
