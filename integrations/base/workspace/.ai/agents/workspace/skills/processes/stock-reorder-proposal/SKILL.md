---
schema_version: base.resource.v1
id: stock-reorder-proposal
type: process
title: Preparer une proposition de reapprovisionnement
description: Preparer une proposition de reapprovisionnement avec les calculs de stock FlowPilot et les selections explicites.
use_when: Preparer une proposition de reapprovisionnement
scope: personal
status: active
sensitivity: internal
keywords: [proposition, reapprovisionnement, fournisseur]
routing:
  examples:
    - Preparer une proposition de reapprovisionnement
    - Preparer une proposition de commande de stock
  avoid_when:
    - Afficher les quantites disponibles.
user-invocable: true
---

# Preparer une proposition de reapprovisionnement

Utiliser STOCK_REORDER_PROPOSAL au niveau PREPARE. Fournisseur, articles, hypothese sur les commandes en attente et eventuel scenario de volumes/recettes viennent des selections explicites. Reutiliser les deficits calcules par les services de stock ; conserver la couverture partielle et les hypotheses. La responsable doit revoir l'empreinte exacte avant de conserver la proposition. Aucune commande, reception, modification de stock, contact fournisseur ou paiement implicite ; aucun prix, delai ni demande inventes.
