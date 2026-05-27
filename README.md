# BodyMinute Flow Manager - Starter MVP

Socle technique initial pour démarrer le développement du MVP.

## Objectif de cette version

Cette base couvre la Phase 1 du développement :

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

La prochaine étape logique est la Phase 2 : créer le frontend React/TypeScript avec la vue planning horizontal, le curseur Maintenant et la file d'attente.
