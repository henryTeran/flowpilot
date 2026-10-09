---
schema_version: base.resource.v1
id: marketing-campaign-draft
type: process
title: Preparer un brouillon de campagne marketing
description: Preparer un brouillon marketing avec audience et modele originaux explicitement selectionnes.
use_when: Preparer un brouillon de campagne marketing
scope: personal
status: active
sensitivity: internal
keywords: [brouillon, campagne, marketing]
routing:
  examples:
    - Preparer un brouillon de campagne marketing
    - Preparer un brouillon marketing avec un modele
  avoid_when:
    - Envoyer une campagne ou contacter des clientes.
user-invocable: true
---

# Preparer un brouillon de campagne marketing

Utiliser MARKETING_CAMPAIGN_DRAFT au niveau PREPARE. Audience et modele originaux viennent des selections explicites de l'interface. Le service marketing conserve uniquement un DRAFT avec le contenu litteral du modele et les destinataires de l'audience verifiee. Aucun identifiant, destinataire ou contenu invente ; aucune approbation de campagne, aucun contact ni envoi implicite. Les destinataires et le texte du modele ne sont pas fournis au routeur ou au fournisseur. La validation puis l'approbation restent dans le circuit marketing existant.
