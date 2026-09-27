# FlowPilot Institut Manager — Master Plan

Date de référence : 2026-09-28  
Statut : PLAN DIRECTEUR VALIDÉ  
Branche de référence initiale : `pivot/bodyminute-workflow`

---

# 1. Rôle de ce document

Ce document constitue le plan directeur de FlowPilot Institut Manager.

Il définit :

- la vision produit ;
- les principes d'architecture ;
- la stratégie IA ;
- les modules cibles ;
- les phases d'implémentation ;
- les gates de validation ;
- les règles de développement ;
- la gouvernance documentaire ;
- la méthode de travail avec Codex.

Ce document répond principalement à la question :

> Où allons-nous et selon quelles règles ?

Il ne doit pas servir de journal quotidien du projet.

L'état opérationnel courant doit rester dans :

```text
PROJECT_STATUS.md
```

---

# 2. Vision produit

FlowPilot Institut Manager est une plateforme de pilotage pour instituts de beauté orientée :

- performance opérationnelle ;
- expérience collaboratrice ;
- expérience cliente premium ;
- automatisation métier ;
- intelligence décisionnelle ;
- optimisation des revenus ;
- pilotage data ;
- architecture IA indépendante des fournisseurs.

FlowPilot ne doit pas devenir un clone d'une solution legacy.

L'objectif est de construire un véritable :

# Operating System intelligent pour instituts

---

# 3. Les trois niveaux du produit

## RUN

Faire fonctionner l'institut.

```text
Planning
Clients
Réservations
Prestations
Tickets
Encaissement
Équipe
Ressources
Stock
```

---

## GROW

Développer l'activité.

```text
CRM
Rebooking
Fidélité
Packages
Abonnements
Cartes cadeaux
Marketing
Automatisations
Revenue opportunities
Customer lifecycle
```

---

## OPTIMIZE

Optimiser les opérations et les décisions.

```text
Revenue Guardian
Smart Waitlist
Scheduling Optimizer
No-Show Risk
Retention Engine
Demand Forecasting
Inventory Forecasting
JV
BASE
FlowPilot Copilot
```

---

# 4. Principe architectural fondamental

# Le domaine est souverain

Les modèles IA ne constituent pas l'intelligence métier principale de FlowPilot.

La responsabilité reste ainsi :

```text
Règles métier          -> FlowPilot
Permissions            -> FlowPilot
Calculs                -> FlowPilot
Scores                 -> FlowPilot
Workflows              -> FlowPilot
Optimisation           -> FlowPilot
Données                -> FlowPilot
Validation             -> FlowPilot
Décisions critiques    -> FlowPilot + humain

Compréhension langage  -> LLM
Génération texte       -> LLM
Synthèse               -> LLM
Conversation           -> LLM
Speech-to-text         -> provider vocal
```

Principe :

```text
LLM != intelligence métier
```

---

# 5. Indépendance vis-à-vis des providers IA

FlowPilot ne doit pas dépendre directement d'OpenAI, Voxtral ou d'un autre fournisseur.

Les providers doivent être remplaçables.

Architecture cible :

```text
LLMProvider
├── OpenAIProvider
├── MistralProvider
├── AnthropicProvider
└── LocalProvider
```

et :

```text
SpeechToTextProvider
├── VoxtralProvider
├── WhisperProvider
└── FutureProvider
```

Éventuellement :

```text
EmbeddingProvider
```

Le reste de l'application dépend des interfaces internes de FlowPilot et non des SDK fournisseurs.

---

# 6. Test architectural fondamental

FlowPilot doit continuer à fonctionner correctement lorsque :

```text
OPENAI = OFF
VOXTRAL = OFF
```

Dans ce mode :

- planning fonctionne ;
- booking fonctionne ;
- tickets fonctionnent ;
- caisse fonctionne ;
- CRM fonctionne ;
- stock fonctionne ;
- règles métier fonctionnent ;
- Revenue Guardian fonctionne ;
- Scheduling Optimizer fonctionne ;
- scores déterministes fonctionnent ;
- JV fonctionne.

Les fonctions conversationnelles ou vocales peuvent être indisponibles.

Lorsque :

```text
OPENAI = ON
```

FlowPilot gagne notamment :

- langage naturel ;
- conversation ;
- synthèse ;
- génération ;
- explication.

Lorsque :

```text
VOXTRAL = ON
```

FlowPilot gagne :

- transcription vocale ;
- interaction vocale.

Principe :

# FlowPilot utilise l'IA sans dépendre de l'IA.

---

# 7. Architecture IA cible

```text
FLOWPILOT
│
├── DOMAIN
│   ├── Business Rules
│   ├── Policies
│   ├── Validators
│   ├── Calculations
│   ├── Scoring
│   ├── Optimizers
│   └── Permissions
│
├── AI PLATFORM
│   │
│   ├── BASE
│   │   ├── Context Resolver
│   │   ├── Intent Resolver
│   │   ├── Capability Registry
│   │   ├── Permission Guard
│   │   ├── Business Rule Guard
│   │   ├── Action Planner
│   │   ├── Approval Manager
│   │   ├── Evidence Builder
│   │   └── Audit Trail
│   │
│   ├── JV
│   │   ├── Business Knowledge
│   │   ├── Deterministic Analysis
│   │   ├── Decision Support Rules
│   │   ├── Scoring
│   │   └── Explainability
│   │
│   ├── Capabilities
│   ├── Orchestration
│   ├── Guards
│   ├── Prompts
│   ├── Schemas
│   ├── Evaluation
│   └── Providers
│
└── EXTERNAL PROVIDERS
    ├── OpenAI
    ├── Voxtral
    └── Future Providers
```

---

# 8. Rôle de BASE

BASE est l'orchestrateur intelligent de FlowPilot.

BASE n'est pas un simple chatbot.

BASE doit orchestrer :

```text
User request
↓
Context
↓
Intent
↓
Capability
↓
Permissions
↓
Business Rules
↓
Application Service
↓
Domain
↓
Evidence
↓
Result
↓
Optional LLM explanation
```

BASE ne doit jamais court-circuiter le domaine.

---

# 9. Rôle de JV

JV contient l'intelligence métier structurée et réutilisable indépendamment d'un provider IA.

Responsabilités possibles :

- calculs métier ;
- diagnostics ;
- scoring ;
- comparaison ;
- règles d'aide à la décision ;
- interprétation structurée ;
- evidence ;
- explications déterministes ;
- recommandations basées sur des faits.

Principe central :

```text
JV produit les faits
LLM produit la langue
```

Exemple :

JV calcule :

```text
CA = -12.4%

Contribution:
- capacité inutilisée: -CHF 340
- annulations: -CHF 190
+ ticket moyen: +CHF 75
+ retail: +CHF 48
```

Le LLM peut ensuite transformer ces faits en langage naturel.

Le LLM ne doit pas recalculer ou inventer les causes.

---

# 10. Evidence First

Les fonctionnalités intelligentes doivent privilégier :

```text
ANSWER
+
EVIDENCE
+
ACTION
```

Exemple :

```text
ANSWER
Le CA est inférieur de 11.8%.

EVIDENCE
- 2 annulations: CHF 180
- 2h15 de capacité inutilisée
- ticket moyen: +3.2%

CONFIDENCE
HIGH

ACTION
5 clientes sont compatibles avec les créneaux disponibles.
```

Le système doit permettre de comprendre sur quelles données repose une recommandation.

---

# 11. Règles IA non négociables

Le LLM ne doit jamais :

- écrire directement dans PostgreSQL ;
- exécuter du SQL généré dynamiquement ;
- contourner les services applicatifs ;
- contourner les permissions ;
- inventer des données métier ;
- définir lui-même les règles métier ;
- effectuer une opération sensible sans contrôles ;
- envoyer librement des communications externes ;
- modifier stock, paiements ou planning sans workflow sécurisé.

Toute action passe par :

```text
Intent
↓
Capability
↓
Permission
↓
Business Rules
↓
Application Service
↓
Domain
↓
Repository
↓
Audit
```

---

# 12. Niveaux de confiance IA

## LEVEL 0 — READ

Lecture uniquement.

Exemples :

- afficher CA ;
- expliquer planning ;
- résumer cliente ;
- analyser stock.

Aucune modification.

---

## LEVEL 1 — SUGGEST

BASE/JV proposent une action.

Exemple :

> Quatre clientes pourraient remplir ce créneau.

Aucune modification.

---

## LEVEL 2 — PREPARE

Le système prépare une opération.

Exemple :

> Quatre messages sont prêts à être envoyés.

Toujours aucune exécution externe.

---

## LEVEL 3 — EXECUTE

Action réelle.

Exemples :

- envoyer SMS ;
- déplacer rendez-vous ;
- annuler rendez-vous ;
- modifier stock ;
- effectuer remboursement ;
- lancer campagne.

Selon la nature de l'action :

```text
permission
+
business validation
+
human approval
+
audit
+
idempotence
```

doivent être appliqués.

---

# 13. Capabilities IA

BASE ne doit utiliser que des capacités explicitement enregistrées.

Exemples :

```text
CLIENT_READ
CLIENT_SUMMARY
CLIENT_REBOOKING_OPPORTUNITIES

PLANNING_READ
PLANNING_GAPS
PLANNING_CONFLICTS
PLANNING_OPTIMIZATION

APPOINTMENT_CREATE
APPOINTMENT_MOVE
APPOINTMENT_CANCEL

WAITLIST_READ
WAITLIST_MATCH

REVENUE_SUMMARY
REVENUE_LOSS_ANALYSIS
REVENUE_OPPORTUNITIES

STOCK_READ
STOCK_FORECAST
STOCK_REORDER_PROPOSAL

EMPLOYEE_CAPACITY
EMPLOYEE_PERFORMANCE

MARKETING_SEGMENT
MARKETING_CAMPAIGN_DRAFT
```

Chaque capability doit connaître :

- son niveau READ / SUGGEST / PREPARE / EXECUTE ;
- les permissions nécessaires ;
- les entrées autorisées ;
- les sorties structurées ;
- les règles métier concernées ;
- les contraintes d'audit.

---

# 14. Architecture backend cible

Conserver :

# Modular Monolith

Pas de microservices actuellement.

Structure cible :

```text
backend/app/

core/
database/
shared/

modules/

  auth/
  organizations/
  institutes/

  clients/
  crm/

  employees/
  workforce/

  services/
  resources/

  booking/
  scheduling/
  waitlist/

  tickets/
  checkout/
  payments/

  packages/
  memberships/
  giftcards/
  loyalty/

  inventory/
  procurement/

  marketing/
  automations/
  notifications/

  analytics/
  revenue_intelligence/

  ai/
    base/
    jv/
    capabilities/
    orchestration/
    providers/
    prompts/
    schemas/
    guards/
    evaluation/
    audit/

  realtime/
  audit/
  integrations/
```

---

# 15. Architecture interne des modules

Chaque domaine doit tendre vers :

```text
module/
├── api/
├── application/
├── domain/
├── infrastructure/
├── schemas/
└── tests/
```

Flux :

```text
API
↓
Application
↓
Domain
↓
Ports / Repositories
↓
Infrastructure
```

Le domaine ne doit pas dépendre directement :

- de FastAPI ;
- de SQLAlchemy ;
- d'OpenAI ;
- de Voxtral ;
- d'un SDK externe.

---

# 16. Domain Events

Utiliser progressivement des événements métier internes.

Exemple :

```text
AppointmentCompleted
```

peut déclencher :

```text
Inventory
→ consommation produits

CRM
→ update last_visit

Loyalty
→ attribution points

Marketing
→ workflow satisfaction

Analytics
→ update KPI

Revenue Intelligence
→ recalcul opportunités
```

Pas besoin de microservices pour cela.

Un Event Bus interne suffit initialement.

---

# 17. Architecture frontend cible

Stack recommandée :

- React ;
- TypeScript ;
- Vite ;
- TailwindCSS ;
- TanStack Query ;
- Zustand pour état global minimal ;
- React Hook Form ;
- Zod ;
- WebSocket ;
- PWA.

Structure :

```text
frontend/src/

app/
features/
components/
design-system/
hooks/
services/
stores/
schemas/
utils/
```

Features possibles :

```text
features/
├── today/
├── planning/
├── booking/
├── clients/
├── tickets/
├── checkout/
├── team/
├── inventory/
├── marketing/
├── insights/
└── base/
```

---

# 18. Design System

Avant une extension importante de l'interface, stabiliser :

## Tokens

- couleurs ;
- typographie ;
- spacing ;
- radius ;
- shadows ;
- z-index ;
- breakpoints ;
- motion ;
- focus states.

## Composants

- Button ;
- IconButton ;
- Input ;
- Select ;
- DatePicker ;
- Modal ;
- Drawer ;
- Card ;
- Table ;
- Badge ;
- Tabs ;
- Toast ;
- EmptyState ;
- Skeleton ;
- Alert ;
- CommandPalette.

Responsive prioritaire :

```text
Desktop
Tablet
Tablet tactile institut
```

---

# 19. Navigation produit cible

```text
Aujourd'hui
Planning
Clients
Ventes
Équipe
Stock
Marketing
Insights
BASE
Paramètres
```

---

# 20. Today / Command Center

L'écran principal doit devenir la console opérationnelle.

Afficher notamment :

- CA prévu ;
- CA réalisé ;
- taux d'occupation ;
- rendez-vous ;
- clientes en attente ;
- prestations en cours ;
- retards ;
- no-shows ;
- paiements en attente ;
- alertes stock ;
- opportunités rebooking ;
- Revenue Guardian ;
- recommandations utiles.

Actions rapides :

- nouveau RDV ;
- nouveau ticket ;
- arrivée cliente ;
- démarrer prestation ;
- encaisser ;
- trouver créneau ;
- préparer contact cliente.

---

# 21. Phase 0 — Stabilisation du workflow existant

## Objectif

Ne pas étendre massivement FlowPilot avant de stabiliser le flux déjà présent.

Flux critique :

```text
identification collaboratrice
↓
création ticket
↓
ajout prestation
↓
assignation
↓
démarrage
↓
fin prestation
↓
encaissement
↓
mise à jour chiffres
```

Cas limites :

- ticket vide ;
- prestation supprimée ;
- collaboratrice non disponible ;
- double démarrage ;
- double encaissement ;
- ticket annulé ;
- paiement partiel ;
- paiement échoué ;
- remboursement ;
- resoumission réseau ;
- idempotence.

## Gate

```text
CORE_WORKFLOW = PASS
TICKETS = PASS
PLANNING = PASS
CHECKOUT = PASS
ANALYTICS = PASS
BACKEND_TESTS = PASS
FRONTEND_TESTS = PASS
```

---

# 22. Phase 1 — Fondations techniques

## Backend

- Alembic ;
- suppression auto-create schema en production ;
- gestion d'erreurs standardisée ;
- pagination ;
- correlation ID ;
- logs structurés ;
- audit trail ;
- CORS par environnement ;
- rate limiting ;
- secrets ;
- health endpoints.

## Tests

- unitaires ;
- intégration ;
- API ;
- E2E critiques.

## Gate

```text
MIGRATIONS = PASS
ERROR_HANDLING = PASS
AUDIT = PASS
SECURITY_BASELINE = PASS
OBSERVABILITY_BASELINE = PASS
```

---

# 23. Phase 2 — Multi-Tenant Foundations

Créer la fondation :

```text
Organization
Institute
Location
```

Les données métier pertinentes doivent porter le contexte nécessaire.

Exemples :

```text
organization_id
institute_id
location_id
```

Objectif :

éviter une migration difficile lors du passage futur au multi-institut.

## Gate

```text
TENANT_ISOLATION = PASS
INSTITUTE_CONTEXT = PASS
RBAC_CONTEXT = PASS
```

---

# 24. Phase 3 — Client 360

Créer le CRM métier central.

## Client

- identité ;
- coordonnées ;
- préférences ;
- notes ;
- tags ;
- consentements ;
- historique ;
- dépenses ;
- fréquence ;
- no-show ;
- rebooking ;
- produits ;
- prestations ;
- photos ;
- documents.

## Beauty Record

- allergies ;
- contre-indications ;
- grossesse ;
- traitements pertinents ;
- sensibilité ;
- phototype ;
- réactions ;
- paramètres machines ;
- observations ;
- photos avant/après ;
- consentements.

## Gate

```text
CLIENT_360 = PASS
CLIENT_HISTORY = PASS
CONSENTS = PASS
BEAUTY_RECORD = PASS
RBAC_CLIENT_DATA = PASS
```

---

# 25. Phase 4 — Booking Engine

Disponibilité :

```text
employee availability
+
employee skills
+
service duration
+
room availability
+
equipment availability
+
buffers
+
opening hours
+
existing appointments
+
business rules
```

Fonctions :

- création ;
- modification ;
- annulation ;
- confirmation ;
- réservation cliente ;
- contraintes.

## Gate

```text
BOOKING_CREATE = PASS
BOOKING_MOVE = PASS
BOOKING_CANCEL = PASS
AVAILABILITY_ENGINE = PASS
CONFLICT_PREVENTION = PASS
```

---

# 26. Phase 5 — Resources & Skills

Créer :

```text
Resource
├── Room
├── Equipment
├── Bed
├── Chair
└── Device
```

et :

```text
EmployeeSkill
ServiceRequirement
ResourceRequirement
```

## Gate

```text
RESOURCE_SCHEDULING = PASS
SKILL_MATCHING = PASS
RESOURCE_CONFLICT = PASS
```

---

# 27. Phase 6 — Live Operations

États possibles :

```text
EXPECTED
ARRIVED
WAITING
IN_SERVICE
FINISHED
PAYMENT_PENDING
COMPLETED
NO_SHOW
```

Actions opérationnelles :

```text
ARRIVED
START
FINISH
PAY
```

Synchronisation via WebSocket.

## Gate

```text
LIVE_BOARD = PASS
REALTIME_SYNC = PASS
RECONNECT = PASS
TABLET_UX = PASS
```

---

# 28. Phase 7 — Commerce

Ajouter :

## Packages

- cures ;
- séances ;
- consommation ;
- expiration.

## Memberships

- abonnements ;
- avantages ;
- renouvellement.

## Gift Cards

- émission ;
- utilisation ;
- expiration ;
- solde.

## Loyalty

- points ;
- niveaux ;
- avantages ;
- historique.

## Gate

```text
PACKAGES = PASS
MEMBERSHIPS = PASS
GIFTCARDS = PASS
LOYALTY = PASS
```

---

# 29. Phase 8 — Payments

Abstraction :

```text
PaymentProvider
```

Providers possibles :

```text
Stripe
TWINT
Worldline
Adyen
Cash
CardTerminal
```

Fonctions :

```text
authorize
capture
refund
cancel
webhook
```

Idempotence obligatoire.

## Gate

```text
PAYMENT_PROVIDER_ABSTRACTION = PASS
PAYMENT_CAPTURE = PASS
REFUND = PASS
WEBHOOK_IDEMPOTENCE = PASS
```

---

# 30. Phase 9 — Inventory

Distinguer :

```text
retail stock
cabine stock
consumables
```

Créer :

- mouvements ;
- ajustements ;
- consommation par prestation ;
- seuils ;
- fournisseurs ;
- commandes ;
- prévisions.

Exemple :

```text
HydraFacial
→ 8 ml cleanser
→ 4 ml serum
→ 1 cartridge
```

## Gate

```text
INVENTORY = PASS
SERVICE_CONSUMPTION = PASS
STOCK_MOVEMENTS = PASS
REORDER = PASS
```

---

# 31. Phase 10 — Workforce

Employee 360 :

- disponibilité ;
- planning ;
- compétences ;
- certifications ;
- objectifs ;
- CA ;
- occupation ;
- rebooking ;
- commissions ;
- absences ;
- congés ;
- heures.

Créer Skill Matrix.

## Gate

```text
EMPLOYEE_360 = PASS
SKILLS = PASS
ABSENCES = PASS
COMMISSIONS = PASS
```

---

# 32. Phase 11 — CRM & Customer Lifecycle

États :

```text
NEW
ACTIVE
LOYAL
VIP
AT_RISK
DORMANT
```

Calculer notamment :

- fréquence ;
- recency ;
- panier moyen ;
- CLV ;
- cycle de rebooking.

Automatisations :

- anniversaire ;
- post-prestation ;
- rebooking ;
- inactivité ;
- expiration package ;
- renouvellement abonnement.

## Gate

```text
CRM_SEGMENTS = PASS
REBOOKING = PASS
CUSTOMER_LIFECYCLE = PASS
AUTOMATION_EVENTS = PASS
```

---

# 33. Phase 12 — Marketing

Créer :

- segmentation ;
- audiences ;
- campagnes ;
- templates ;
- SMS ;
- email ;
- push ;
- suivi conversion.

Une campagne IA suit :

```text
DRAFT
↓
REVIEW
↓
APPROVE
↓
SEND
```

## Gate

```text
SEGMENTATION = PASS
CAMPAIGN_DRAFT = PASS
CAMPAIGN_APPROVAL = PASS
CAMPAIGN_AUDIT = PASS
```

---

# 34. Phase 13 — Revenue Intelligence

Créer Revenue Guardian.

Calculs possibles :

- capacity utilization ;
- unused capacity ;
- cancelled revenue ;
- no-show revenue ;
- average ticket ;
- rebooking opportunities ;
- service mix ;
- retail attach rate ;
- employee capacity ;
- projected revenue.

Chaque opportunité contient :

```text
type
evidence
estimated_value
confidence
recommended_action
```

## Gate

```text
REVENUE_GUARDIAN = PASS
REVENUE_EVIDENCE = PASS
OPPORTUNITY_ENGINE = PASS
```

---

# 35. Phase 14 — Smart Waitlist

Matching selon :

- prestation ;
- durée ;
- disponibilité cliente ;
- collaboratrice ;
- compétences ;
- ressources ;
- contraintes ;
- historique ;
- consentements.

## Gate

```text
WAITLIST = PASS
WAITLIST_MATCHING = PASS
AUTO_SLOT_DETECTION = PASS
```

---

# 36. Phase 15 — Scheduling Optimizer

Créer un moteur déterministe.

Exemple :

```text
score =
revenue_score
+ utilization_score
+ continuity_score
+ client_preference_score
+ employee_preference_score
- idle_gap_penalty
- overtime_penalty
- resource_conflict_penalty
```

Résultat :

```text
option
score
reasons
constraints
```

Le LLM explique éventuellement le résultat.

Il ne calcule pas le score officiel.

## Gate

```text
SCHEDULING_OPTIMIZER = PASS
SCORING_DETERMINISTIC = PASS
EXPLANATION_EVIDENCE = PASS
```

---

# 37. Phase 16 — BASE Foundation

Créer :

## Context Resolver

Construit uniquement le contexte nécessaire et autorisé.

## Intent Resolver

Transforme langage naturel en intention structurée.

## Capability Registry

Liste les actions autorisées.

## Permission Guard

Valide RBAC et contexte institut.

## Business Rule Guard

Valide règles métier.

## Action Planner

Prépare les opérations.

## Approval Manager

Gère confirmation humaine.

## Evidence Builder

Construit les preuves.

## Audit Trail

Trace l'interaction.

## Gate

```text
BASE_CONTEXT = PASS
BASE_INTENT = PASS
BASE_CAPABILITIES = PASS
BASE_PERMISSIONS = PASS
BASE_GUARDS = PASS
BASE_AUDIT = PASS
```

---

# 38. Phase 17 — JV

Responsabilités :

- règles métier analytiques ;
- calculs structurés ;
- diagnostics ;
- comparaison ;
- scoring ;
- decision support ;
- evidence ;
- explainability.

## Gate

```text
JV_RULES = PASS
JV_EVIDENCE = PASS
JV_PROVIDER_INDEPENDENCE = PASS
```

---

# 39. Phase 18 — AI Provider Layer

Interfaces :

```text
LLMProvider
SpeechToTextProvider
EmbeddingProvider
```

Implémentations initiales possibles :

```text
OpenAIProvider
VoxtralProvider
```

Règle :

aucun SDK fournisseur ne doit se propager dans les modules métier.

Un fake provider doit permettre les tests.

## Gate

```text
LLM_ABSTRACTION = PASS
STT_ABSTRACTION = PASS
OPENAI_ISOLATED = PASS
VOXTRAL_ISOLATED = PASS
FAKE_PROVIDER_TESTS = PASS
```

---

# 40. Phase 19 — FlowPilot Copilot

Capacités initiales :

```text
CLIENT_READ
CLIENT_SUMMARY
CLIENT_REBOOKING_OPPORTUNITIES

PLANNING_READ
PLANNING_GAPS
PLANNING_CONFLICTS

REVENUE_SUMMARY
REVENUE_LOSS_ANALYSIS
REVENUE_OPPORTUNITIES

STOCK_READ
STOCK_FORECAST

EMPLOYEE_CAPACITY
```

Puis progressivement :

```text
APPOINTMENT_CREATE
APPOINTMENT_MOVE
MARKETING_CAMPAIGN_DRAFT
STOCK_REORDER_PROPOSAL
```

## Gate

```text
COPILOT_READ = PASS
COPILOT_SUGGEST = PASS
COPILOT_PREPARE = PASS
COPILOT_EXECUTE_GUARDED = PASS
```

---

# 41. Phase 20 — Voice

Pipeline :

```text
audio
↓
SpeechToTextProvider
↓
text
↓
BASE
↓
Intent
↓
Capability
↓
Domain
```

Voxtral ne contient aucune décision métier.

## Gate

```text
VOICE_TRANSCRIPTION = PASS
VOICE_INTENT = PASS
VOICE_BASE_INTEGRATION = PASS
```

---

# 42. Phase 21 — No-Show Risk

Commencer avec des règles déterministes.

Variables possibles :

- no-shows précédents ;
- annulations tardives ;
- lead time ;
- valeur ;
- confirmation ;
- acompte ;
- historique.

Sortie :

```text
risk_score
risk_level
evidence
```

## Gate

```text
NOSHOW_SCORE = PASS
NOSHOW_EVIDENCE = PASS
NOSHOW_POLICY = PASS
```

---

# 43. Phase 22 — Retention Engine

Identifier :

- clientes arrivant au rebooking ;
- clientes à risque ;
- VIP inactives ;
- packages proches expiration ;
- changement de comportement.

Le système produit des opportunités.

Pas d'action externe sans contrôle.

## Gate

```text
RETENTION_ENGINE = PASS
REBOOKING_DETECTION = PASS
AT_RISK_DETECTION = PASS
```

---

# 44. Phase 23 — Forecasting

Ajouter progressivement :

- demand forecasting ;
- revenue forecasting ;
- inventory forecasting ;
- workforce capacity forecasting.

Toujours séparer :

```text
forecast engine
```

de :

```text
LLM explanation
```

## Gate

```text
DEMAND_FORECAST = PASS
REVENUE_FORECAST = PASS
INVENTORY_FORECAST = PASS
```

---

# 45. Phase 24 — Multi-Institut

Lorsque le socle est stable :

- management groupe ;
- consolidation ;
- comparaison sites ;
- droits groupe/local ;
- mobilité collaborateurs ;
- catalogue partagé ;
- stock inter-sites ;
- KPIs consolidés.

## Gate

```text
MULTI_INSTITUTE = PASS
GROUP_ANALYTICS = PASS
TENANT_SECURITY = PASS
```

---

# 46. Phase 25 — Production Readiness

Avant production :

- TLS ;
- backup ;
- restore test ;
- migrations ;
- rate limiting ;
- audit ;
- observabilité ;
- erreurs ;
- secrets ;
- privacy ;
- rétention ;
- monitoring ;
- performance ;
- disaster recovery.

## Gate final

```text
SECURITY = PASS
BACKUP_RESTORE = PASS
PERFORMANCE = PASS
OBSERVABILITY = PASS
PRIVACY = PASS
E2E = PASS
PRODUCTION_READY = PASS
```

---

# 47. Stratégie de tests

Chaque module doit posséder selon pertinence :

## Unit Tests

Règles métier.

## Integration Tests

DB, repositories, Redis, providers.

## API Tests

Auth, validation, permissions, erreurs.

## Frontend Tests

Interactions critiques.

## E2E

Parcours métier réels.

---

# 48. Tests permanents de non-régression

Conserver des tests spécifiques pour :

```text
booking conflict
double payment
double execution
cross-tenant access
unauthorized access
AI permission bypass
AI direct DB attempt
stale data
idempotence
resource conflict
negative stock
package over-consumption
```

---

# 49. Sécurité

Principes :

- moindre privilège ;
- validation stricte ;
- secrets hors code ;
- contrôle backend systématique ;
- tenant isolation ;
- audit actions sensibles ;
- rate limiting ;
- protections brute-force ;
- TLS ;
- chiffrement infrastructure ;
- politique de rétention ;
- anonymisation lorsque nécessaire.

---

# 50. Observabilité

Prévoir progressivement :

- logs JSON ;
- correlation IDs ;
- métriques techniques ;
- métriques métier ;
- p50 ;
- p95 ;
- p99 ;
- traces ;
- monitoring ;
- alerting.

Outils possibles :

```text
OpenTelemetry
Prometheus
Grafana
Sentry
```

---

# 51. Prompts IA

Les prompts ne doivent pas être dispersés dans les routes.

Structure :

```text
ai/prompts/
```

Exemples :

```text
intent_classifier.v1
manager_explanation.v1
customer_message.v1
```

Les prompts doivent être versionnés lorsqu'ils deviennent critiques.

Ils ne constituent jamais une règle métier officielle.

---

# 52. Git Strategy

Éviter l'accumulation massive de fichiers modifiés.

Principe :

```text
1 commit = 1 changement cohérent et testable
```

Exemples :

```text
feat(clients): add client 360 domain model

feat(booking): add availability engine

feat(ai): add provider abstraction

feat(base): add capability registry

fix(planning): prevent overlapping appointments

test(booking): cover resource conflicts

refactor(ai): isolate OpenAI provider

docs(flowpilot): update master plan
```

Ne pas faire :

- un commit par fichier ;
- un unique commit de plusieurs semaines de travail.

---

# 53. Règles Git pour Codex

Avant toute tâche :

1. inspecter le working tree ;
2. identifier les modifications préexistantes ;
3. préserver les modifications hors scope ;
4. travailler sur un checkpoint limité ;
5. exécuter les tests pertinents ;
6. vérifier le diff ;
7. commit à la fin d'une unité cohérente ;
8. rapporter le hash ;
9. maintenir le working tree aussi propre que raisonnablement possible.

Ne jamais écraser silencieusement le travail préexistant.

---

# 54. Format de checkpoint obligatoire

Après une étape importante :

```text
CHECKPOINT — <nom>

STATUS = PASS / PARTIAL / BLOCKED

IMPLEMENTED
- ...

TESTS
- ...
- X/X PASS

SECURITY
- ...

AI
- ...

FILES_CHANGED
- ...

COMMITS
- <hash> <message>

KNOWN_LIMITATIONS
- ...

BLOCKERS
- ...

NEXT_STEP
- ...
```

---

# 55. Anti-Scope-Creep

Pendant une phase, ne pas implémenter arbitrairement une phase future.

Exceptions :

- fondation indispensable ;
- correction sécurité ;
- correction régression ;
- changement nécessaire pour ne pas créer une dette immédiate importante.

Les autres idées vont dans le backlog.

---

# 56. Organisation documentaire officielle

Structure minimale :

```text
docs/
├── product/
│   ├── FLOWPILOT_MASTER_PLAN.md
│   └── PRODUCT_VISION.md
│
├── architecture/
│   └── ARCHITECTURE_FOUNDATIONS.md
│
└── adr/
    ├── ADR-001-modular-monolith.md
    ├── ADR-002-provider-independent-ai.md
    ├── ADR-003-base-jv-architecture.md
    └── ADR-004-human-approval-ai-actions.md
```

À la racine :

```text
PROJECT_STATUS.md
README.md
```

---

# 57. Source de vérité

Ordre d'autorité officiel :

```text
1. docs/product/FLOWPILOT_MASTER_PLAN.md
2. PROJECT_STATUS.md
3. docs/architecture/ARCHITECTURE_FOUNDATIONS.md
4. docs/product/PRODUCT_VISION.md
5. docs/adr/*
6. Code
7. README.md
```

En cas de conflit :

le document supérieur prévaut jusqu'à correction explicite de l'incohérence.

---

# 58. Rôle de chaque document

## FLOWPILOT_MASTER_PLAN.md

Répond :

> Où allons-nous ?

Contient :

- vision ;
- architecture ;
- phases ;
- règles ;
- gates ;
- roadmap.

---

## PROJECT_STATUS.md

Répond :

> Où sommes-nous maintenant ?

Doit rester court.

Structure recommandée :

```text
CURRENT_PHASE
CURRENT_CHECKPOINT
STATUS
TESTS
BLOCKERS
LAST_COMMITS
NEXT_STEP
WORKING_TREE
```

Ne pas y recopier toute la roadmap.

---

## ARCHITECTURE_FOUNDATIONS.md

Répond :

> Comment devons-nous construire le système ?

Principes techniques structurants.

---

## PRODUCT_VISION.md

Répond :

> Pourquoi construisons-nous ce produit et quelle expérience voulons-nous ?

---

## ADR

Répond :

> Pourquoi cette décision architecturale a-t-elle été prise ?

---

## README.md

Répond :

> Qu'est-ce que ce repository et comment le lancer ?

---

# 59. ADR

Dossier :

```text
docs/adr/
```

Premiers ADR :

```text
ADR-001-modular-monolith.md
ADR-002-provider-independent-ai.md
ADR-003-base-jv-architecture.md
ADR-004-human-approval-ai-actions.md
```

ADR futurs possibles :

```text
ADR-005-multi-tenant-foundation.md
ADR-006-payment-provider-abstraction.md
ADR-007-domain-events.md
```

Ne créer un ADR que pour une décision réellement structurante.

---

# 60. Archives documentaires

Si d'anciens documents deviennent obsolètes mais doivent être conservés :

```text
docs/archive/
```

Ce dossier ne fait pas partie des sources de vérité actives.

Les documents archivés ne doivent pas être utilisés automatiquement par Codex pour prendre des décisions courantes.

---

# 61. Règle de lecture pour Codex

Codex ne doit pas systématiquement lire toute la documentation.

Pour une tâche standard, lire :

```text
docs/product/FLOWPILOT_MASTER_PLAN.md
PROJECT_STATUS.md
fichiers du module concerné
```

Ajouter :

```text
docs/architecture/ARCHITECTURE_FOUNDATIONS.md
```

uniquement si le changement touche significativement l'architecture.

Lire les ADR concernés uniquement lorsque pertinents.

Objectif :

- conserver le contexte ;
- éviter les contradictions ;
- limiter la consommation inutile de tokens.

---

# 62. Format recommandé des prompts Codex

```text
FLOWPILOT CHECKPOINT

Read first:
- docs/product/FLOWPILOT_MASTER_PLAN.md
- PROJECT_STATUS.md
- <relevant files>

Read architecture docs only if required.

Current phase:
<phase>

Objective:
<objective>

Scope:
<exact scope>

Out of scope:
<explicit exclusions>

Architecture constraints:
<rules>

AI constraints:
<BASE/JV/provider rules>

Security constraints:
<rules>

Tests required:
<tests>

Git requirements:
- inspect existing working tree
- preserve unrelated changes
- commit coherent completed work
- report commit hash

Final report:
STATUS
IMPLEMENTED
TESTS
SECURITY
AI
FILES_CHANGED
COMMITS
BLOCKERS
NEXT_STEP
```

---

# 63. Definition of Done

Une fonctionnalité n'est DONE que si les critères pertinents sont satisfaits :

- fonctionnellement complète ;
- règles métier validées ;
- erreurs gérées ;
- permissions validées ;
- tenant isolation validée ;
- tests automatisés ;
- UX cohérente ;
- responsive validé ;
- audit si action sensible ;
- observabilité appropriée ;
- documentation à jour ;
- commit cohérent effectué ;
- working tree maîtrisé.

---

# 64. Priorité immédiate

Avant tout nouveau développement fonctionnel :

```text
STEP 1
Mettre en place la gouvernance documentaire

↓

STEP 2
Créer / mettre à jour PROJECT_STATUS.md

↓

STEP 3
Créer les ADR initiaux

↓

STEP 4
Faire un commit documentaire propre

↓

STEP 5
Commencer PHASE 0
```

Puis :

```text
PHASE 0
Stabilisation workflow existant

↓

PHASE 1
Fondations techniques

↓

PHASE 2
Multi-Tenant Foundations

↓

PHASE 3
Client 360

↓

PHASE 4
Booking Engine

↓

PHASE 5
Resources & Skills

↓

PHASE 6
Live Operations
```

Les briques commerciales, data et IA viennent ensuite progressivement.

---

# 65. État initial de référence

```text
VISION = VALIDATED

PRODUCT_DIRECTION = VALIDATED

ARCHITECTURE_DIRECTION = VALIDATED

MODULAR_MONOLITH = VALIDATED

AI_VISION = VALIDATED

BASE_DIRECTION = VALIDATED

JV_DIRECTION = VALIDATED

PROVIDER_INDEPENDENCE = VALIDATED

HUMAN_APPROVAL_MODEL = VALIDATED

DOCUMENT_GOVERNANCE = VALIDATED

PHASE_0 = NEXT
```

---

# 66. Prochain checkpoint

Après création de la structure documentaire :

```text
CHECKPOINT — PROJECT GOVERNANCE
```

Gate attendu :

```text
MASTER_PLAN = PASS
PROJECT_STATUS = PASS
ARCHITECTURE_DOC = PASS
PRODUCT_VISION = PASS
ADR_001 = PASS
ADR_002 = PASS
ADR_003 = PASS
ADR_004 = PASS
DOCUMENT_PATHS = PASS
GIT_COMMIT = PASS
```

Puis :

# PHASE 0 — Stabilisation du workflow métier existant