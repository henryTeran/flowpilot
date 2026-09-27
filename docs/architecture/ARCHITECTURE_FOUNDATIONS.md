# FlowPilot - Architecture Foundations

Date: 2026-09-28
Statut: Référence d'implémentation

## Objectif

Construire une application modulable, scalable, robuste et sécurisée, prête à évoluer vers une plateforme multi-instituts.

## Principes non négociables

1. Modularité forte
- chaque domaine métier isolé par module
- dépendances unidirectionnelles
- interfaces explicites entre modules

2. Sécurité by design
- moindre privilège partout
- secrets hors code source
- validation stricte des entrées
- traçabilité des actions sensibles

3. Scalabilité pragmatique
- services stateless côté API
- jobs asynchrones pour tâches lourdes
- cache ciblé sur lectures critiques
- architecture compatible montée en charge horizontale

4. Résilience opérationnelle
- gestion d'erreurs standardisée
- idempotence sur opérations critiques
- stratégie de reprise sur pannes partielles

5. Observabilité native
- logs structurés
- métriques techniques et métier
- corrélation requête -> action -> impact métier

## Cible backend

Architecture en couches:

- API layer: routes, validation HTTP, authn/authz
- Application layer: orchestration des cas d'usage
- Domain layer: règles métier pures
- Infrastructure layer: DB, cache, providers externes

Règles:

- la couche API ne contient pas de logique métier complexe
- la logique métier ne dépend pas de FastAPI ni SQLAlchemy directement
- l'accès aux données passe par des ports/repositories

## Cible frontend

Architecture UI:

- app shell
- modules de fonctionnalités
- composants UI partagés
- état global minimal et découplé

Règles:

- séparation stricte entre composants de présentation et logique métier UI
- design tokens centralisés
- accessibilité et responsive comme critères de done

## Sécurité applicative

1. Authentification et sessions
- JWT signés avec rotation de secret/clé planifiée
- durée de vie courte + refresh token sécurisé
- invalidation explicite à la déconnexion sensible

2. Autorisation
- RBAC par rôle + contexte institut
- contrôle d'accès systématique côté backend
- audit des refus d'accès

3. Protection API
- rate limiting sur endpoints sensibles
- CORS strict par environnement
- protection brute-force login
- validation des payloads et limites de taille

4. Données
- chiffrement en transit (TLS)
- chiffrement au repos (DB/backup)
- politique de rétention et anonymisation
- journalisation des actions critiques (encaissement, annulation, droits)

## Scalabilité

1. Base de données
- migrations gérées (Alembic)
- index ciblés sur requêtes critiques
- pagination systématique
- stratégie partitionnement si volumétrie forte

2. Temps réel
- WebSocket avec gestion de reconnexion et heartbeat
- backpressure et limitation de débit par client

3. Traitements asynchrones
- file de jobs pour notifications, exports, calculs lourds
- retries avec backoff et dead-letter queue

4. Mise à l'échelle
- API stateless derrière load balancer
- séparation des services CPU intensifs si besoin

## Qualité et robustesse

1. Tests
- unitaires: règles métier
- intégration: repositories et API
- end-to-end: parcours critiques institut

2. Standards
- convention de code stricte
- revues de code orientées sécurité + perf
- couverture minimum sur modules critiques

3. Performance
- objectifs SLO dès le départ
- budget de latence par endpoint critique
- monitoring p50, p95, p99

## Plan d'implémentation progressif

Phase A - Durcissement immédiat
- retirer la création auto des tables au startup en prod
- ajouter migration Alembic
- standardiser gestion d'erreurs et réponses

Phase B - Modularité
- introduire couche application/domain
- déplacer règles métier hors routes
- formaliser interfaces repositories

Phase C - Observabilité et sécurité
- logs JSON corrélés
- métriques Prometheus
- rate limiting et audit trail

Phase D - Scalabilité
- cache Redis ciblé
- queue de jobs asynchrones
- tuning DB et tests de charge

## Definition of done technique

Une fonctionnalité n'est terminée que si:

- règles métier testées
- contrôles d'accès validés
- observabilité ajoutée
- performance acceptable mesurée
- UX cohérente avec design system
