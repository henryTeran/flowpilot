# FlowPilot Institut Manager

Plateforme de pilotage institut orientée performance opérationnelle, expérience collaboratrice et expérience cliente premium.

## Vision produit

L'objectif n'est plus de reproduire un logiciel existant, mais de livrer une solution plus complète, plus intelligente et plus agréable à utiliser.

Cette base couvre le socle de la Phase 1 :

- Backend FastAPI modulaire
- PostgreSQL
- Redis prêt pour le temps réel
- Structure par modules métier
- Modèles initiaux : instituts, collaboratrices, prestations, tickets, sessions planning
- Endpoints REST MVP
- WebSocket de base pour préparer le planning temps réel
- Seed de données de démonstration

## Stack

- Python / FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Docker Compose

## Lancer le projet

```bash
cp .env.example .env
docker compose up --build
```

Puis ouvrir :

- API : http://localhost:8000
- Documentation Swagger : http://localhost:8000/docs

Paramètres utiles d'architecture:

- `AUTO_CREATE_SCHEMA_ON_STARTUP=true` pour bootstrap local rapide
- `AUTO_CREATE_SCHEMA_ON_STARTUP=false` en environnement de production (migrations Alembic)

## Initialiser des données de test

Une fois l'API démarrée :

```bash
curl -X POST http://localhost:8000/api/v1/dev/init-demo-data
```

Ensuite :

```bash
curl http://localhost:8000/api/v1/institutes
curl http://localhost:8000/api/v1/planning/institutes/demo-institute-geneve/today
```

## Organisation backend

```text
backend/app/
  core/          configuration, sécurité, permissions
  database/      session DB, base SQLAlchemy
  shared/        utilitaires communs
  modules/
    auth/
    institutes/
    employees/
    services/
    tickets/
    planning/
    realtime/
    dev/
```

## Prochaine étape

La prochaine étape logique est la Phase 2 premium :

- Design system moderne (tokens, composants UI cohérents, responsive tablette + desktop)
- UX orientée rapidité en institut (moins de clics, états clairs, feedback immédiat)
- Fonctions enrichies (analyse activité, productivité, qualité de service)

## Documentation

- Master plan:
  docs/product/FLOWPILOT_MASTER_PLAN.md

- Product vision:
  docs/product/PRODUCT_VISION.md

- Architecture:
  docs/architecture/ARCHITECTURE_FOUNDATIONS.md

- Architecture decisions:
  docs/adr/

- Current project status:
  PROJECT_STATUS.md
