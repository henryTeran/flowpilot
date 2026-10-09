---
schema_version: base.resource.v1
id: appointment-create
type: process
title: Preparer la creation d'un rendez-vous
description: Preparer une creation de rendez-vous avec les termes explicites selectionnes et les services FlowPilot.
use_when: Preparer la creation d'un rendez-vous
scope: personal
status: active
sensitivity: internal
keywords: [creation, rendez-vous, preparation]
routing:
  examples:
    - Preparer la creation d'un rendez-vous
    - Preparer une nouvelle reservation cliente
  avoid_when:
    - Annuler un rendez-vous existant.
user-invocable: true
---

# Preparer la creation d'un rendez-vous

Utiliser APPOINTMENT_CREATE au niveau PREPARE. Les termes, identifiants et dates viennent exclusivement des selections explicites de l'interface. Le service FlowPilot verifie le creneau et les ressources avant de conserver un original en attente. Aucune reservation, approbation ou execution implicite. La responsable authentifiee doit revoir l'original exact puis donner une decision explicite par le circuit d'approbation. Ne pas transformer le message en consentement ni inventer des identifiants, dates, coordonnees ou disponibilites.
