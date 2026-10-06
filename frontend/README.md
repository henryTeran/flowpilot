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

`npm test` discovers all `.test.js`, `.test.ts` and `.test.tsx` files recursively
in `src` and `tests`, including payment recovery and reporting regressions.
It runs them through Node with `tsx`, a 60-second per-test timeout and a nonzero
exit status on failure. No shell wildcard expansion is required on Windows.

Browser regression: `npm run test:browser` builds the frontend, owns a strict-port
loopback preview at 127.0.0.1:4197, and runs desktop/tablet-landscape projects.
Windows uses installed Microsoft Edge by default; another supported browser
channel can be selected with `FLOWPILOT_BROWSER_CHANNEL`. Other platforms use
Playwright Chromium (install its browser binary first). See the official
[Playwright browser documentation](https://playwright.dev/docs/browsers) and
[web-server configuration](https://playwright.dev/docs/test-webserver).

The current cashflow browser cases use controlled API fixtures, not a live payment
provider or backend. Screenshots/traces are stored in ignored `test-results`;
physical tablet acceptance and full backend-connected E2E remain separate gates.

`npm run test:browser:backend` starts a real FastAPI process on 127.0.0.1:4198
and a separately built preview on 127.0.0.1:4199. It requires backend dependencies
in the repository `.venv`. The fixture always overrides DATABASE_URL with a new
temporary SQLite file and generates its own signing key/test users. It never opens
an existing application database or configures a payment adapter. Tests authenticate
through the actual login form; no API interception or injected session token is used.
Current coverage includes manager/cashier access, scoped reads, logout and an
anonymous walk-in through assignment, start, extension, finish and recorded cash
checkout at desktop/tablet landscape sizes. The test explicitly configures its
fixture catalog currency through the signed API. Cash entry is not bank/provider
settlement; appointment conflicts, reconnect and physical-tablet acceptance remain
separate checks. The test-only login limit is 20 to support the complete suite. The owning Node launcher removes its exact `flowpilot-browser-*` temporary
directory after Playwright finishes, including rejected launches. The backend
requires the launcher ownership marker and refuses an existing database. Cleanup
errors fail the command; abrupt termination of the owning launcher itself is not
a verified cleanup path.

The backend browser suite also verifies two signed pages receiving real WebSocket
changes and recovering an arrival missed while one context is offline. Native
socket tracking enables deterministic close; the transport and REST remain real.
Browsers use Europe/Zurich explicitly. This verifies controlled headless reconnect
recovery, not a physical-tablet or production multi-server outage.
