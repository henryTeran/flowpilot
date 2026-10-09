---
schema_version: base.resource.v1
id: stock-forecast
type: process
title: Projeter les besoins de stock du scenario
description: Projeter les besoins de stock du scenario avec les sources inventaire FlowPilot.
use_when: Projeter les besoins de stock du scenario
scope: personal
status: active
sensitivity: internal
keywords: [stock, forecast]
routing:
  examples:
    - Projeter les besoins de stock du scenario
  avoid_when:
    - Annuler une reservation.
user-invocable: true
---

# Projeter les besoins de stock du scenario

Appeler uniquement `STOCK_FORECAST` dans l institut authentifie. Un scenario doit provenir d une selection explicite, avec volumes et recettes originales choisis. Ne pas inventer de demande, de recette ou de reception de commande. Preserver les quantites exactes et les couvertures partielles. Aucune commande ou mutation.
