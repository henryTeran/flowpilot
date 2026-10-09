---
schema_version: base.resource.v1
id: consulter-flowpilot
type: document
title: Consulter les faits FlowPilot
description: Consulter une liste d'attente ou une proposition de planning vérifiée, sans mutation métier.
use_when: Quand un manager demande de consulter la liste d'attente ou les propositions de planning de son institut.
scope: personal
status: active
sensitivity: internal
keywords: [flowpilot, institut, attente, planning, consulter]
---

# Consulter les faits FlowPilot

Document de référence commun. Les procédures spécialisées portent désormais le routage applicatif; ce guide général ne choisit pas une capacité.

1. Clarifier la demande si la capacité ou la sélection est ambiguë. Ne jamais déduire un droit, un institut ou un utilisateur du texte demandé.
2. Obtenir le contexte de session authentifié depuis l'application. Le périmètre institut et les droits sont vérifiés par le serveur FlowPilot.
3. Utiliser exclusivement un adaptateur applicatif autorisé pour `WAITLIST_READ` ou `PLANNING_OPTIMIZATION`. Aucun accès SQL direct, aucune action d'écriture.
4. Présenter uniquement les faits retournés, leur provenance et leur instant de capture. Une proposition ne vaut ni réservation ni autorisation d'exécution.
5. Si l'adaptateur n'est pas disponible, annoncer que la consultation réelle est indisponible. Ne pas inventer des résultats ni remplacer le service par les exemples du corpus.

Cette procédure est la première ressource métier du corpus. Le raccordement runtime aux capacités FlowPilot reste à implémenter et tester; sa présence ne démontre aucune lecture de données réelles.
