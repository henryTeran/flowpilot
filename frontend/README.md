# Frontend FlowPilot Institut Manager

Interface React/TypeScript du MVP.

## Démarrage

```powershell
npm install
npm run dev
```

Puis ouvrir :

```text
http://localhost:5173
```

Le frontend attend le backend sur :

```text
http://localhost:8001/api/v1
```

Si besoin, copier `.env.example` vers `.env` et adapter `VITE_API_URL`.

## Session et passages anonymes

Se connecter avec un compte accueil ou responsable d’institut. Le token de
session accompagne les requêtes HTTP et le WebSocket ; le backend conserve les
contrôles de rôle et d’institut. L’identification de la collaboratrice dans le
ticket reste distincte de cette connexion.

Pour un passage anonyme : créer un ticket, sélectionner la prestation, puis
« Ajouter à la file ». Aucun nom ou téléphone n’est requis. Le ticket apparaît
immédiatement ; les positions suivent l’arrivée puis l’identifiant en cas
d’égalité. « Remettre en attente » libère une affectation sans annuler le ticket.

```powershell
npm test
npm run build
```

Les tests de composants utilisent un DOM simulé. Le chronométrage terrain
(objectif de moins de 15 secondes) et la validation visuelle sur tablette
restent des vérifications opérateur.
