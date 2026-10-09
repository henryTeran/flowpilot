---
schema_version: base.resource.v1
id: client-summary
type: process
title: Resumer le profil CRM cliente
description: Resumer le profil CRM cliente avec les sources autorisees FlowPilot.
use_when: Resumer le profil CRM cliente
scope: personal
status: active
sensitivity: internal
keywords: [client, summary]
routing:
  examples:
    - Resumer le profil CRM cliente
    - Resumer le segment CRM
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Resumer le profil CRM cliente

L adaptateur appelle exclusivement `CLIENT_SUMMARY` dans le contexte authentifie. customer_id doit provenir de la selection explicite de l interface. Ne pas inventer un identifiant ni une politique CRM. Les permissions et services FlowPilot restent souverains. Aucune mutation ni transmission de faits clients au fournisseur de langage. Un segment indisponible et un historique incomplet doivent rester explicites.
