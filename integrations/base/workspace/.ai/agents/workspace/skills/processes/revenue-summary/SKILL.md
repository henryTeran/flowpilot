---
schema_version: base.resource.v1
id: revenue-summary
type: process
title: Consulter le resume des revenus enregistres
description: Consulter le resume des revenus enregistres avec la facturation FlowPilot.
use_when: Consulter le resume des revenus enregistres
scope: personal
status: active
sensitivity: internal
keywords: [revenus, facturation]
routing:
  examples:
    - Consulter le resume des revenus enregistres
    - Afficher le bilan de facturation
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Consulter le resume des revenus enregistres

Appeler uniquement `REVENUE_SUMMARY` avec la periode explicite selectionnee dans l interface et la responsable authentifiee. Utiliser les agregats existants; ne pas convertir les devises, inventer des causes ou assimiler la facturation a un encaissement. Preserver les montants inconnus et les limites d exhaustivite. Aucune mutation.
