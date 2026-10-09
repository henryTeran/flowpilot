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
Walk-in Queue
Planning
Clients
Réservations hybrides
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
Règles métier                -> FlowPilot
Permissions                  -> FlowPilot
Calculs                     -> FlowPilot
Scores                      -> FlowPilot
Workflows                   -> FlowPilot
Optimisation                -> FlowPilot
Données                     -> FlowPilot
Validation                  -> FlowPilot
Décisions critiques         -> FlowPilot + humain

Compréhension langage       -> LLM
Génération texte            -> LLM
Synthèse                    -> LLM
Conversation                -> LLM
Speech-to-text              -> provider vocal
```

Principe :

```text
LLM != intelligence métier
```

### Règle d'alignement opérationnel

```text
WaitingTimeEngine / CapacityEngine
= déterministe FlowPilot domain logic

JV
= analyse métier structurée et preuve

BASE
= orchestration

LLM
= langage, synthèse et explication
```

Exemple de principe :

```text
CAUSES = FlowPilot / JV
LANGUAGE = LLM
```

Le LLM ne calcule jamais le temps d'attente officiel ni la disponibilité officielle.

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
│   ├── WaitingTimeEngine
│   ├── CapacityEngine
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

BASE désigne le framework officiel [AI Swiss BASE](https://github.com/ai-swiss/base), et non un moteur interne portant ce nom. Le framework structure les agents, procédures et ressources versionnées; les adaptateurs FlowPilot assurent les contrôles et les appels au domaine. Voir [le plan corrigé](../architecture/BASE_UPSTREAM_INTEGRATION.md).

BASE n'est pas un simple chatbot.

Les adaptateurs applicatifs FlowPilot autour du framework doivent assurer :

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

# 24. Phase 3 — Flow & Queue Domain

Le cœur opérationnel de FlowPilot doit être orienté walk-in first.

## Flux principal 1 — WALK-IN FLOW

```text
arrival
→ anonymous ticket
→ queue
→ estimated wait
→ assignment
→ service
→ checkout
```

## Flux principal 2 — APPOINTMENT FLOW

```text
booking
→ reserved collaborator/resource
→ service
→ checkout
```

Les deux flux convergent vers le même moteur opérationnel.

### Règles métier additives

- les tickets walk-in peuvent rester anonymes ;
- name/email/phone ne sont pas obligatoires pour un ticket walk-in basique ;
- la durée de service est une donnée essentielle de planification ;
- les états collaborateurs doivent inclure au minimum :
  AVAILABLE, BUSY, PAUSE, ABSENT ;
- l'extension d'un service actif déclenche un recalcul de capacité et de temps d'attente ;
- une assignation walk-in ne doit pas créer de conflit avec un rendez-vous imminent ;
- un service dépendant d'une ressource ne peut pas être planifié si la ressource requise n'est pas disponible.

## Gate

```text
WALK_IN_FLOW = PASS
ANONYMOUS_TICKETS = PASS
QUEUE_LIFECYCLE = PASS
COLLABORATOR_STATES = PASS
WAITING_TIME_FOUNDATION = PASS
```

---

# 25. Phase 4 — Scheduling & Capacity Engine

Le cœur métier est le moteur Flow & Capacity Engine.

Il combine :

```text
walk-in queue
+
appointments
+
collaborator availability
+
collaborator status
+
standard service durations
+
active services
+
service extensions
+
breaks
+
skills
+
rooms
+
machines
+
equipment
+
existing bookings
```

Il produit :

- next available slot ;
- estimated wait time ;
- queue priority ;
- collaborator availability ;
- resource availability ;
- assignment options.

## Gate

```text
FLOW_CAPACITY_ENGINE = PASS
WAITING_TIME_ENGINE = PASS
AVAILABILITY_ENGINE = PASS
QUEUE_ASSIGNMENT = PASS
SERVICE_EXTENSION_IMPACT = PASS
CONFLICT_HANDLING = PASS
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

# 27. Phase 6 — Hybrid Booking Engine

Le booking devient hybride et coexiste avec la charge walk-in.

Fonctions :

- création de rendez-vous ;
- modification ;
- annulation ;
- confirmation ;
- réservation cliente ;
- contraintes de ressource ;
- déplacement / annulation d'un RDV sans générer de conflit avec la file d'attente.

## Gate

```text
HYBRID_BOOKING = PASS
BOOKING_CREATE = PASS
BOOKING_MOVE = PASS
BOOKING_CANCEL = PASS
RESOURCE_RESERVATION = PASS
COEXISTENCE_WALKIN_BOOKING = PASS
```

---

# 28. Phase 7 — Live Operations

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
PAUSE
EXTEND
PAY
```

Synchronisation via WebSocket.

## Gate

```text
LIVE_BOARD = PASS
REALTIME_SYNC = PASS
RECONNECT = PASS
TABLET_UX = PASS
LIVE_RECALCULATION = PASS
```

---

# 29. Phase 8 — Commerce

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

# 30. Phase 9 — Payments

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

# 31. Phase 10 — Inventory

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


Phase 10G checkpoint: native completed-execution consumption worklist and explicit
measured/no-material authoring are implemented with original request recovery,
visible original norm/deviation and automatic stock refresh. Scoped pending and
confirmed pagination uses one bounded SQL UNION. Evidence and remaining gates:
PROJECT_STATUS.md and ADR-010. Phase 10H resolves legitimate checkout corrections
by retaining original line/basis/consumption facts and excluding signed removals
from invoice, payment and loyalty totals (ADR-011). Phase 10I also fixes queue/event
instant metadata and institute-local cashier hours, verified in foreign-workstation
Edge cases. Phase 10J captures original appointment invoice provenance and shows
billing exclusion independently of measured consumption (ADR-012), with no
historical backfill or automatic zero usage. Phase 10K adds the signed institute
supplier directory and original creation recovery (ADR-013). Phase 10L adds
immutable purchase orders and atomic exact partial receipt APIs (ADR-014),
with original recovery independent of current budgets. Phase 10M adds native
order/partial-receipt authoring, original request recovery, explicit measured
quantities and fresh progress/stock verification. Reorder and forecasts remain
required. Phase 10N adds exact scoped outlook and explicit service-volume scenario
read APIs using selected original norms, with partial coverage and conditional
incoming quantities (ADR-015). Phase 10O adds native bounded outlook, explicit
original-version scenario review and institute civil-date conversion with
partial coverage. Scheduled/observed demand integration remains required. No physical tablet, production settlement
or complete Phase 10 claim.

Phases 10P-10S subsequently add exact elapsed-time projection windows,
recorded upcoming appointment/explicit waiting-queue demand, signed measured
usage by actual completion and native review of both source views (ADR-016).
Missing/legacy/undated sources preserve unknown complete totals; provisional
upcoming norms and observed constant-pace projections are alternatives.
Controlled frontend/Edge evidence is recorded in PROJECT_STATUS.md. Inventory
requirement/production acceptance and Phase 24 gates remain to be audited;
no physical tablet or full production closure is inferred from these checks.

# 32. Phase 11 — Workforce

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

Phase 11AM verifies these four functional gates in the controlled environment:
the twelve Employee 360 subjects and Skill Matrix map to current shared-source
APIs/native bindings in `docs/architecture/WORKFORCE_GATE_AUDIT.md`. At code commit
`85800ec`, all 28 Phase 11 backend test files pass (83 tests on owned SQLite and
actual PostgreSQL fixtures), and all 16 signed Workforce browser spec files pass
(44 Edge desktop/touch-tablet scenarios). Current frontend evidence includes 227
passing tests and the browser launcher's production build. This scope does not
claim the full backend suite, unrelated browser suites, a physical device,
application-database migration, payment settlement or production readiness.
Those existing gates remain open while canonical Phase 12 proceeds.

---

# 33. Phase 12 — CRM & Customer Lifecycle

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

Phase 12AQ functional acceptance: all four section 33 gates PASS after the
requirement-by-requirement audit in `CRM_PHASE12_ACCEPTANCE.md`. Full backend CRM
(25 files, migrations and actual PostgreSQL included): 175 passed in 272.44s;
signed native desktop/touch-tablet CRM suite: 12 passed in 2.2m. Physical and
production gates remain OPEN; declared conditional CLV/recorded care basis and
no external delivery claims are preserved. Earlier checkpoint OPEN entries are
historical. The full canonical goal continues into Phase 13.

# 34. Phase 13 — Marketing

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

# 35. Phase 14 — Revenue Intelligence

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

# 36. Phase 15 — Smart Waitlist

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

# 37. Phase 16 — Scheduling Optimizer

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

# 38. Phase 17 — BASE Foundation

Intégrer effectivement ai-swiss/base: dépendance officielle verrouillée, ressources `base.resource.v1`, corpus validé, routage upstream testé, puis adaptateur authentifié vers les services FlowPilot. Les checkpoints historiques 17A–17O sont des fondations applicatives, pas une preuve d’intégration upstream. Voir [le plan corrigé](../architecture/BASE_UPSTREAM_INTEGRATION.md).

Responsabilités des adaptateurs FlowPilot :

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
BASE_UPSTREAM_CORPUS = PASS
BASE_UPSTREAM_ROUTING = PASS
BASE_APPLICATION_ADAPTER = PASS
BASE_CONTEXT = PASS
BASE_INTENT = PASS
BASE_CAPABILITIES = PASS
BASE_PERMISSIONS = PASS
BASE_GUARDS = PASS
BASE_AUDIT = PASS
```

Clôture de fondation enregistrée le 9 octobre 2026 : [preuves et audit final 17V](../architecture/BASE_PHASE_REOPENED.md). La traçabilité opérationnelle et les originaux métier ne constituent pas une certification de rétention des logs ou de production. La phase 18 poursuit l’objectif global.

---

# 39. Phase 18 — JV

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

Clôture de fondation le 9 octobre 2026 : [audit 18F et preuves runtime](../architecture/JV_FOUNDATION.md). Les faits inconnus et causes non prouvées restent explicitement indisponibles; la clôture JV ne certifie pas la couche provider ni la préparation de production.

---

# 40. Phase 19 — AI Provider Layer

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

Clôture de fondation le 9 octobre 2026 : [audit 19E et preuves d’image](../architecture/AI_PROVIDER_LAYER.md). La qualification distante des modèles/credentials, les futures transmissions métier et la préparation de production restent distinctes de ces gates de contrats et isolation.

---

# 41. Phase 20 — FlowPilot Copilot

Creation revocation browser acceptance:4 PASS1.1m (.cache/20-creation-revocation-browser.log), including existing decline compatibility2 and new revocation2 desktop/tablet. Actual signed API/pinned official BASE: exact retained creation separately approved then explicitly revoked, previous approval ID bound; independent history reread stays revoked, execution control absent/no execution POST, native agenda empty and room still available. Tablet screenshot inspected; fixture removed/terminal exit0. After terminal completion redundant copied decline test removed from new file (original remains in copilot-creation-panel.spec.ts); new revocation test behavior unchanged, title corrected. No production change; package67/frontend584 remain current. Remaining expiry and decision races/browser adverse acceptance require reconciliation. Goal ACTIVE, Phase20 PARTIAL.


Marketing catalogue pagination/original preservation acceptance:2 PASS55.0s desktop/tablet (.cache/20-marketing-pagination-browser.log). Actual signed API/pinned official BASE with22+ retained audiences/current template heads; both next/previous navigation exercised, exact old audience and chosen original selected. Later native template revision before preview does not replace selected original body/subject/source ID. Lost retention response recovers after reload with one new DRAFT/one retention POST, no delivery authorization/external message. Initial2 failures were test navigation synchronization: selection attempted before previous page reload; explicit enabled-catalogue wait fixes test only. Tablet screenshot inspected; owned fixture removed/listeners0/terminal exit0. Current-head catalogue does not expose arbitrary template revision history; chosen original remains immutable after head changes. No production change; packaged67/frontend584 baselines current. Remaining decision expiry/creation revocation/races and named adverse marketing verification require final reconciliation; goal ACTIVE, Phase20 PARTIAL.


Push marketing refusal acceptance:2 PASS42.3s desktop/tablet (.cache/20-marketing-push-refusal-browser.log). Native retained push audience has eligible_count0 because recorded permission is unsupported_channel; literal push original template selected. Copilot displays admissible-audience refusal, no preview/retain control and zero UI POSTs; native campaign catalogue unchanged. Tablet screenshot inspected; owned fixture removed/listeners0/terminal exit0. This is local eligibility refusal, not BASE routing evidence (no language request dispatched). No production change; package67/frontend584 baselines remain current. Historical catalogue pagination and other named progressive variants remain open; goal ACTIVE, Phase20 PARTIAL.


SMS marketing browser acceptance:2 PASS58.9s desktop/tablet (.cache/20-marketing-sms-browser.log), actual signed API/pinned official BASE. Native explicit SMS marketing permission, retained NEW audience and SMS original template with null subject/literal placeholder/whitespace/emoji. Preview and stored DRAFT retain exact body/source identities; lost retention acknowledgement recovered after reload, exactly one retention POST/one new campaign, external_message_sent and delivery_authorized false. Tablet screenshot inspected; owned fixture removed/listeners0/terminal exit0. No production change; packaged67/frontend584 remain current. Email and SMS positive paths proved; push is domain unsupported_channel and needs adverse UI acceptance, as do historical catalogue pagination and remaining adverse variants. Whole goal ACTIVE, Phase20 gates PARTIAL.


Move changed-source browser acceptance:2 PASS1.0m desktop/tablet (.cache/20-move-source-change-browser.log), actual signed API/pinned official BASE. Native appointment notes changed after exact retained preparation/human approval; UI execution receives400, retains frozen request/no receipt, and explicit rejection verification clears intent only after independent absence read. Exactly one execution POST; edited original booking remains unchanged by execution, original room still blocked/proposed slot free. Tablet screenshot inspected; owned fixture removed/listeners0/terminal exit0. No production change; packaged67/frontend584 remain current. Source-change refusal proves this move path, not all decision races or expiry. Goal ACTIVE; remaining creation revocation/expiry/race and marketing historical-page/channel/adverse acceptance required.


Move revocation browser acceptance:2 PASS1.1m desktop/tablet (.cache/20-move-revocation-browser.log), actual signed API/pinned official BASE. Exact retained preview and approval followed by explicit UI revocation bound to original approval ID; independently reread chain remains revoked, execution control absent/no execution POST/receipt, original appointment unchanged. Native resource previews confirm original room still blocked and proposed interval free. Tablet screenshot inspected; owned fixture removed/listeners0/terminal exit0. Production source unchanged; current packaged67 and frontend584 baselines remain current. This proves move revocation UI only; creation revocation, expiry, changed-source/race and marketing variants remain required. Goal ACTIVE, progressive gates PARTIAL.


Current acceptance update (supersedes earlier outstanding package/changed-target statements):
- Current packaged backend at source98b4050, image sha256:0ab9df22afd9ee645dd09c66f4c447a964ef19b1e53733d812738af23427b5f4:67 PASS, zero failures/skips,341.06s (.cache/20-current-package-regression.log). Python3.12.15, Node22.23.3, PostgreSQL16.14; SQLite and isolated PostgreSQL contracts, native domain previews, reorder migration/races and relocated pinned official BASE runtime covered. Temporary schemas0; invocation-labelled containers/network absent after terminal exit0. Reproduce from Linux/WSL: bash backend/scripts/validate-copilot-package.sh. Tests/migrations mounted read-only; no production migration/deployment or remote inference claimed.
- Changed-target move browser2 PASS1.7m (.cache/20-move-targets-browser.log): desktop/tablet real signed API and pinned official BASE, native linked customer, explicit Camille/aisselles target instead of Angela/50min room care. Preparation/approval leave appointment unchanged; guarded execution preserves original ID/customer/name/phone/notes/status, changes duration to10min, frees original room/employee. Lost acknowledgement recovered after reload through original receipt, exactly one execution POST. Screenshots inspected; fixture removed/listeners0/exit0. Added copilot-move-targets.spec.ts; production source unchanged.
- Initial populated consultation/suggestion variants and current package evidence are now present. Final gate reconciliation remains required; named decision revocation/expiry/changed-source/race and marketing historical-page/channel/adverse browser acceptance remain open. Whole26-phase goal ACTIVE; progressive gates PARTIAL. Earlier checkpoint paragraphs are historical, not additional outstanding work.


Current capacity opportunity evidence: Actual signed API/pinned official BASE capacity opportunity plus populated planning browser4 PASS59.5s desktop/tablet (.cache/20-capacity-opportunity-browser.log). Dedicated owned fixture50min service requires one room with explicit capability. Active room produces conditional original queue projection; native maintenance yields capacity_unknown/no slot; restoring active restores projection. Exact local horizon, duration, original employee/skills/resource needs/queue counts and no-reservation/no-action/no-value boundaries checked. All appointment and resource-reservation snapshots, plus resource rows per consultation, unchanged;3browser writes are query POSTs only. Original test tried maintenance on room bearing conflict fixtures and correctly got400; dedicated room/service avoids altering those reservations. Visual inspection found internal cause code in summary; backend now maps all three closed unavailable causes to French text, browser asserts raw code absent. SQLite opportunities regression1 PASS7.83s,1PostgreSQL test deselected (.cache/20-capacity-wording-sqlite.log); current PG/Linux package remains required. Final tablet maintenance/desktop restored screenshots inspected; fixture removed/listeners0/exit0. This proves conditional projection, not opening hours or physical availability. Initial populated consultation/suggestion variants identified in audit now have UI evidence; named progressive variants and current backend/database/Linux acceptance remain. Frontend584 regression remains current because frontend production source unchanged. Goal ACTIVE, gates PARTIAL.

Current institute rebooking evidence: Actual signed API/pinned official BASE customer plus institute rebooking browser2 PASS52.7s desktop/tablet (.cache/20-rebooking-institute-browser.log). Existing four customer review states retained. Added native registered customer/completed ticket session and institute REVENUE_OPPORTUNITIES/rebooking consultation: exactly1due candidate with original policy/ticket source, matching native counts/diagnostics/candidate terms. Separate native linked future booking suppresses that candidate:0remaining and already-booked count increases1. Both institute reads preserve native appointment lists and current policy;6UI writes are query POSTs only. Contact/action/history authority remains false and estimated value null. Explicit1us rule tests declared timing, not a recommended care interval. Desktop due/tablet suppressed screenshots inspected; owned fixture removed/listeners0, exit0. Production unchanged; frontend584 regression remains current. Populated capacity suggestion, named progressive variants and current backend/database/Linux acceptance still required. Goal ACTIVE, gates PARTIAL.

Final coexistence regression:6 PASS1.7m desktop/tablet (.cache/20-closures-regression-browser.log), combining new financial consultations with historical revenue-closure-flow. Review detected a fixture filename collision: original closure_fixture.py restored byte-for-byte from preceding commit, new startup helper separated as copilot_closure_fixture.py. Combined fixtures correctly add institute-wide terminal legacy records; new test compares the exact count to the native institute read instead of assuming only its own fixture exists. Final original-source/read/recovery checks pass, fixture removed/listeners0/exit0. No production edit.

Current populated closure evidence: Actual signed API/pinned official BASE financial browser4 PASS54.3s desktop/tablet (.cache/20-closures-populated-browser.log), combining new populated loss/follow-up tests and existing mixed-revenue regression. Owned opt-in revenue fixture now creates25 native booking closures (13cancelled/12no-show), one terminal booking without event,4 native walk-in cancellations with retained CHF/EUR/unknown/missing amounts, and one legacy unpriced cancellation. Historical event clocks are patched only inside fixture seeding and restored before HTTP serving. Real loss UI preserves counts, original retained values and financial_loss null/causal_loss false. Follow-up UI renders first20of25booking events and all5walk-ins, exact native event references and known1.01CHF/2.02EUR retained values; unknown or missing values stay unestablished. Delivery/action/recovery/history authority remains false/null. Only2query POSTs in the new flow; booking statuses/events, ticket statuses and original cancellation terms unchanged. Desktop loss/tablet follow-up screenshots inspected; owned fixture removed/listeners0, exit0. Existing Windows socket-reset warning did not fail tests or cleanup. Remaining populated capacity/rebooking revenue suggestions, named progressive variants and current backend/Linux acceptance keep gates PARTIAL/goal ACTIVE. Production source unchanged; frontend584 regression remains current.

Current mixed revenue evidence: Actual signed API/pinned official BASE mixed-currency revenue browser2 PASS51.4s desktop/tablet (.cache/20-revenue-populated-browser.log). Opt-in --revenue-fixture seeds observed historical paid-ticket/invoice snapshots only in the owned new database, with no clock override or bank adapter. On the25h DST period,5tickets/4active lines produce CHF known2000cents with1missing amount/complete total null, EUR725cents complete, and unknown-currency800cents/complete total null. Care/retail source mix matches native original;2tickets without active lines keep retail attachment unknown. Exact original totals/averages/coverage, UI separate amounts/incomplete wording, and false completeness/settlement/projected-revenue boundaries checked. One query POST only; native aggregates/mix and fixture ticket/line snapshots unchanged. First failures were nested test locator scope and decimal-comma expectations against existing exact decimal-point formatter; corrected tests, no production edit. Desktop/tablet screenshots inspected; fixture removed/listeners0, terminal exit0. Snapshot reading does not prove historical checkout execution or bank settlement. Remaining nonzero closure/opportunity facts, progressive variants and current backend/Linux regression keep gates PARTIAL/goal ACTIVE. Frontend584 regression remains current; production source unchanged.

Current populated planning evidence: Actual signed API/pinned official BASE populated capacity/conflict browser2 PASS45.5s desktop/tablet (.cache/20-planning-populated-browser.log). Explicit --planning-fixture imports historical completed activity and intentionally conflicting legacy bookings/reservations only in the owned new database, with no clock override. Native work declarations cover all4employees for2h each on the25h DST day. Three completed records yield60min occupied union,45min covered/15min outside work; aggregate unoccupied7h15/Angela1h15 remain recorded measures, not bookable or physically proven capacity. Employee/resource each show exactly one30min overlap from3sources; touching endpoints produce no extra conflict. Browser makes only3query POSTs; original booking/reservation snapshots and native work/activity totals unchanged. Initial tablet fixture attempted duplicate hours under a new key and correctly received400; corrected setup replays the exact shared key, no production change. Desktop capacity/tablet resource screenshots inspected; fixture removed/listeners0, exit0. Remaining mixed-currency revenue, nonzero closure/opportunity facts, named progressive variants and current backend/Linux regression keep gates PARTIAL/goal ACTIVE. Production source unchanged; frontend584 evidence remains current.

Current historical CRM evidence: Actual signed API/pinned official BASE historical CRM browser2 PASS46.8s desktop/tablet (.cache/20-crm-history-browser.log). Explicit opt-in --crm-history-fixture seeds only the owned new temporary database before serving, with no overridden application clock: customers registered500days ago and legacy observed paid snapshots75/120/400days ago, plus no-payment customer. Retained365day horizon/60day risk/90day dormancy policy yields AT_RISK/DORMANT even with3tickets/4500CHF cents exceeding VIP criteria. Outside-window and absent payments remain null/no_observed_closing, rendered Segment non etabli, never inferred NEW/DORMANT. Exact customer/policy/state/count/currency/closing identity, hidden phone and incomplete-history boundary checked. Only four query POSTs occur during browser reads; native counts/currency totals/last closing/current policy unchanged. Historical snapshots are fixture records, not proof of historical checkout execution or complete ledger. Desktop risk/tablet outside-window screenshots inspected; fixture removed/listeners0, exit0. Together with NEW and native paid ACTIVE/LOYAL/VIP acceptance, all six CRM classification presentations now have real API/BASE browser evidence. Production source unchanged; frontend584 regression remains current. Remaining activity/conflict/revenue/closure-opportunity, progressive variants and current backend/Linux gates remain PARTIAL; goal ACTIVE.

Current populated rebooking evidence: Actual signed API/pinned official BASE rebooking browser2 PASS48.4s desktop/tablet (.cache/20-rebooking-populated-browser.log). Real native customer/ticket/completed session and separately retained six-rule policies prove not_due (explicit one-day interval), disabled, available/due (explicit1us interval), then already_booked with a native future appointment linked to the same customer. Every query binds exact policy, ticket source and actual care completion; delivery/execution/history flags remain false, phone hidden, explicit review wording present. Four UI writes are query POSTs only; native appointment list and current policy unchanged by reads. Initial final assertion incorrectly expected ticket_id on the session response; replaced with source ticket identity/completion checks, no production change. Desktop booked/tablet available screenshots inspected; owned fixture removed/listeners0, terminal exit0. Evidence proves declared-rule behavior, not a clinically recommended interval. Remaining historical CRM, employee activity/conflicts, populated revenue/closure/opportunities, named progressive variants and current backend/Linux acceptance remain. Goal ACTIVE, gates PARTIAL; current full frontend584 evidence unchanged.

Current populated CRM evidence: Actual signed API/pinned official BASE CRM browser acceptance: 2 PASS50.0s desktop/tablet (.cache/20-crm-populated-browser.log). Native explicitly configured CHF and retained policy with1/2/3 completed cash-paid tickets produce ACTIVE/LOYAL/VIP. Exact customer/policy/count/state, known CHF amounts, incomplete-history wording and hidden phone checked. UI writes only three query POSTs; native currency totals/count/last closing and retained policy unchanged. Initial fixture omitted institute currency and correctly failed on null; corrected through native settings before tickets, no production change. Representative tablet VIP screenshot inspected; fixture removed/listeners0, exit0. NEW baseline already proved; historical AT_RISK/DORMANT and other named populated/progressive/current package requirements remain. Goal ACTIVE, gates PARTIAL; existing frontend584 regression remains current because production source unchanged.

État actuel après intégration des interfaces progressives : les 12 consultations et les 4 parcours de création, déplacement, brouillon marketing et proposition de réapprovisionnement sont disponibles. Les parcours réels API/BASE couvrent les effets principaux, la reprise après réponse perdue et plusieurs refus ; le réapprovisionnement inclut normes originales, réceptions partielles, pagination et limite de 50 articles. Restent les cas métier peuplés de certaines consultations, les variantes progressives nommées dans l’audit et une validation backend/Linux du code actuel. Le snapshot 20X est une preuve historique. Les gates restent PARTIAL. Les paragraphes de checkpoints ci-dessous décrivent leurs états antérieurs ; [l’audit courant](../architecture/COPILOT_PHASE20_GATE_AUDIT.md) précise les preuves et le travail restant.

Validation actuelle du déplacement : deux parcours réels API/BASE officiel passent sur ordinateur et tablette. Préparation et approbation laissent le rendez-vous intact ; l’exécution conserve son identité et ses coordonnées, déplace son intervalle et réaffecte la salle. Une réponse perdue est récupérée après rechargement sans seconde exécution. Les variantes de cible et les cas adverses, les interfaces de brouillon marketing et de réapprovisionnement ainsi que les autres preuves métier manquantes restent à traiter. Les gates restent PARTIAL.

Mise à jour de validation de l’interface de création : préparation, décision humaine, exécution et reprise sont maintenant disponibles. Deux parcours réels API/BASE officiel passent sur ordinateur et tablette : aucun rendez-vous avant l’exécution, un seul après, puis récupération après réponse perdue et rechargement sans doublon. La réservation de salle est vérifiée par une disponibilité préalable puis un refus explicite de ressource sur le même créneau. Les interfaces de déplacement, brouillon marketing et proposition de réapprovisionnement, ainsi que les cas adverses et autres données métier peuplées, restent à terminer. Les gates restent PARTIAL ; le paragraphe historique ci-dessous décrit le périmètre des checkpoints antérieurs.

Checkpoints 20A–20Y et extensions : les12 capacités initiales sont enregistrées et présentées dans le Copilot, incluant lecture des stocks, scénarios explicites et opportunités de reprise/suivi des clôtures. APPOINTMENT_CREATE et APPOINTMENT_MOVE conservent une préparation exacte, exigent une approbation explicite et exécutent leur effet, leurs ressources, leur événement et leur reçu dans une transaction unique. Le déplacement préserve les coordonnées et se lie au rendez-vous et à son historique. Routage BASE officiel et services métier réutilisés ; pertes causales et couvertures incomplètes restent indéterminées. Le brouillon marketing lié à une audience et un modèle originaux conserve un DRAFT sans approbation ni envoi ; la proposition de réapprovisionnement conserve les déficits du service de stock avec fournisseur/articles/hypothèse/scénario explicites, sans créer de commande ni modifier le stock. L’audit des16 capacités et la validation Linux du snapshot backend20X (64 tests) sont établis. Les consultations sont vérifiées sur desktop/tablette, notamment une projection peuplée avec recette originale sélectionnée et norme manquante ; plusieurs autres cas métier peuplés restent à vérifier. Restent ces lacunes de validation et les quatre interfaces de préparation, décision, exécution et reprise. [Périmètre et limites](../architecture/COPILOT_INTEGRATION.md). Les gates ci-dessous sont les critères de clôture ; leur état actuel reste PARTIAL dans PROJECT_STATUS.md.

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

# 42. Phase 21 — Voice

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

# 43. Phase 22 — No-Show Risk

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

# 44. Phase 23 — Retention Engine

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

# 45. Phase 24 — Forecasting

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

# 46. Phase 25 — Multi-Institut

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

# 47. Phase 26 — Production Readiness

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

# 48. Stratégie de tests

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

# 49. Tests permanents de non-régression

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

# 50. Sécurité

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

# 51. Observabilité

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

# 52. Prompts IA

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

# 53. Git Strategy

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

# 54. Règles Git pour Codex

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

# 55. Format de checkpoint obligatoire

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

# 56. Anti-Scope-Creep

Pendant une phase, ne pas implémenter arbitrairement une phase future.

Exceptions :

- fondation indispensable ;
- correction sécurité ;
- correction régression ;
- changement nécessaire pour ne pas créer une dette immédiate importante.

Les autres idées vont dans le backlog.

---

# 57. Organisation documentaire officielle

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
    ├── ADR-004-human-approval-ai-actions.md
    └── ADR-005-walk-in-first-hybrid-flow.md
```

À la racine :

```text
PROJECT_STATUS.md
README.md
```

---

# 58. Source de vérité

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

# 59. Rôle de chaque document

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

# 60. ADR

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
ADR-005-walk-in-first-hybrid-flow.md
```

ADR futurs possibles :

```text
ADR-006-multi-tenant-foundation.md
ADR-007-payment-provider-abstraction.md
ADR-008-domain-events.md
```

Ne créer un ADR que pour une décision réellement structurante.

---

# 61. Archives documentaires

Si d'anciens documents deviennent obsolètes mais doivent être conservés :

```text
docs/archive/
```

Ce dossier ne fait pas partie des sources de vérité actives.

Les documents archivés ne doivent pas être utilisés automatiquement par Codex pour prendre des décisions courantes.

---

# 62. Règle de lecture pour Codex

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

# 63. Format recommandé des prompts Codex

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

# 64. Definition of Done

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

# 65. Priorité immédiate

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
Flow & Queue Domain

↓

PHASE 4
Scheduling & Capacity Engine

↓

PHASE 5
Resources & Skills

↓

PHASE 6
Hybrid Booking

↓

PHASE 7
Live Operations

↓

PHASE 8
Client 360
```

Les briques commerciales, data et IA viennent ensuite progressivement.

---

# 66. État initial de référence

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

# 67. Prochain checkpoint

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
