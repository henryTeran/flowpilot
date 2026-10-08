---
schema_version: base.resource.v1
id: workspace
type: agent
title: Workspace
description: FlowPilot Institut Manager: consultation des faits metier verifies sans execution automatique
use_when: Quand la demande porte sur: FlowPilot Institut Manager: consultation des faits metier verifies sans execution automatique
scope: personal
status: active
sensitivity: internal
---
# Workspace

Ce fichier est la carte d'identité de votre assistant: qui il est, quand le solliciter.
Précisez la description et le use_when dès que son rôle se dessine. C'est ce que lit le
routeur pour décider de l'activer.

Pour transformer vos documents existants en process et compétences, demandez à votre
assistant: «importer mes procédures existantes». Le routeur l'enverra sur le process
`importer-l-existant`, qui propose chaque conversion en diff (rien n'est écrit sans vous).
