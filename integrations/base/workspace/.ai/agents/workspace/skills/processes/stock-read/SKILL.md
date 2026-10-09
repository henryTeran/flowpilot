---
schema_version: base.resource.v1
id: stock-read
type: process
title: Consulter les stocks enregistres
description: Consulter les stocks enregistres avec les sources inventaire FlowPilot.
use_when: Consulter les stocks enregistres
scope: personal
status: active
sensitivity: internal
keywords: [stock, read]
routing:
  examples:
    - Consulter les stocks enregistres
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Consulter les stocks enregistres

Appeler uniquement `STOCK_READ` dans l institut authentifie. Un scenario doit provenir d une selection explicite, avec volumes et recettes originales choisis. Ne pas inventer de demande, de recette ou de reception de commande. Preserver les quantites exactes et les couvertures partielles. Aucune commande ou mutation.
