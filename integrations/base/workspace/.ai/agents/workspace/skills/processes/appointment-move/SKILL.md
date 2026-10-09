---
schema_version: base.resource.v1
id: appointment-move
type: process
title: Preparer le deplacement d'un rendez-vous
description: Preparer un deplacement de rendez-vous selon une selection explicite et les services FlowPilot.
use_when: Preparer le deplacement d'un rendez-vous
scope: personal
status: active
sensitivity: internal
keywords: [deplacement, rendez-vous, preparation]
routing:
  examples:
    - Preparer le deplacement d'un rendez-vous
    - Preparer un changement de creneau de reservation
  avoid_when:
    - Creer une nouvelle reservation.
user-invocable: true
---

# Preparer le deplacement d'un rendez-vous

Utiliser APPOINTMENT_MOVE au niveau PREPARE avec le rendez-vous et le nouvel instant explicitement selectionnes. Les changements de collaboratrice ou de prestation restent explicites et optionnels. Aucun changement de cliente, coordonnees ou notes. Les services FlowPilot verifient le rendez-vous appartenant a l'institut, son historique, le creneau et les ressources, puis conservent un original en attente d'approbation explicite. Ne pas deduire les identifiants ou dates depuis le message. Aucun deplacement, contact, accord ou execution implicite.
