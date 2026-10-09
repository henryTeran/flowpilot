---
schema_version: base.resource.v1
id: waitlist-read
type: process
title: Lire, afficher ou consulter la liste d attente
description: Lire, afficher ou consulter une demande de liste d attente avec les sources deterministes FlowPilot.
use_when: Lire la liste d'attente
scope: personal
status: active
sensitivity: internal
keywords: [waitlist, read]
routing:
  examples:
    - Lire la liste d'attente
    - Afficher la liste d'attente
    - Consulter la liste d'attente
    - Read the waitlist
    - Show the waitlist
  avoid_when:
    - Modifier ou annuler une reservation.
user-invocable: true
---

# Lire une demande de liste d attente

La resolution de methode autorise seulement une proposition de `WAITLIST_READ`. Une selection explicite et schema-validee reste indispensable. L adaptateur verifie les permissions et le perimetre signe avant d appeler le service existant. Cette resolution ne lit pas les donnees metier et ne confirme aucune execution. Une preparation capture ensuite les preuves par les services officiels FlowPilot. Un original deja retenu se recupere sans rejouer le routage.
