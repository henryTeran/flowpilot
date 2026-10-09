---
schema_version: base.resource.v1
id: client-read
type: process
title: Consulter la fiche cliente
description: Consulter la fiche cliente avec les sources autorisees FlowPilot.
use_when: Consulter la fiche cliente
scope: personal
status: active
sensitivity: internal
keywords: [client, read]
routing:
  examples:
    - Consulter la fiche cliente
    - Lire la fiche identite client
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Consulter la fiche cliente

L adaptateur appelle exclusivement `CLIENT_READ` dans le contexte authentifie. customer_id doit provenir de la selection explicite de l interface. Ne pas inventer un identifiant ni une politique CRM. Les permissions et services FlowPilot restent souverains. Aucune mutation ni transmission de faits clients au fournisseur de langage. Un segment indisponible et un historique incomplet doivent rester explicites.
