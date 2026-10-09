---
schema_version: base.resource.v1
id: waitlist-match
type: process
title: Trouver des creneaux de liste d attente
description: Trouver des creneaux de liste d attente avec les sources deterministes FlowPilot.
use_when: Chercher des creneaux pour la liste d'attente
scope: personal
status: active
sensitivity: internal
keywords: [waitlist, match]
routing:
  examples:
    - Chercher des creneaux pour la liste d'attente
    - Trouver des creneaux pour la liste d'attente
    - Examiner les creneaux de la liste d'attente
    - Find slots for the waitlist
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Trouver des creneaux de liste d attente

La resolution de methode autorise seulement une proposition de `WAITLIST_MATCH`. Une selection explicite et schema-validee reste indispensable. L adaptateur verifie les permissions et le perimetre signe avant d appeler le service existant. Cette resolution ne lit pas les donnees metier et ne confirme aucune execution. Une preparation capture ensuite les preuves par les services officiels FlowPilot. Un original deja retenu se recupere sans rejouer le routage.
