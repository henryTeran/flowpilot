# BASE officiel pour FlowPilot

Depuis ce dossier: `npm ci --ignore-scripts`, puis `npm run validate`, `npm run index` et `npm test`.

La dépendance officielle est verrouillée sur le commit AI Swiss `cc0e4d1a723565fb5ebb17c6a26664423e5226c1` et le lockfile. Node 18 ou supérieur est requis. Les scripts appellent la CLI du package installé, sans dépendre du clone de recherche dans `.cache`.

`workspace` a été initialisé avec la CLI upstream, puis enrichi de procédures FlowPilot. Il est configuré `local-only`, sans données clientes et sans outil métier exécutable. `runtime.mjs` relie le broker upstream au endpoint backend `/api/v1/base/query`: message sur stdin, mode lexical, contexte de procédure, puis sélection fermée de services côté Python. Ces commandes valident le corpus et son routage; les tests backend vérifient séparément la chaîne réelle vers les services.

Le backend local requiert `node` dans le PATH et ce dossier avec son package installé. `BASE_RUNTIME_DIRECTORY` permet de configurer un emplacement de déploiement fiable; cette configuration n'est jamais acceptée dans les requêtes HTTP. Une dépendance manquante donne 503, sans recours à un moteur interne de remplacement. Voir [l'audit de phase](../../docs/architecture/BASE_PHASE_REOPENED.md).

Le Dockerfile backend utilise désormais le contexte racine: `docker build -f backend/Dockerfile .`. Un stage Node installe la dépendance verrouillée sans scripts d'installation, valide le corpus et rejoue le routage. L'image Python reçoit le binaire Node, le package complet et le corpus dans `/opt/flowpilot-base`. Compose conserve le montage de développement de l'application et configure ce Dockerfile. Le fichier `.dockerignore` limite les sources transmises et exclut traces, réglages locaux et données temporaires.

Le runtime a été testé depuis une copie isolée du package complet. La configuration Compose est validée. L'image Docker elle-même reste à construire et tester: ces vérifications locales ne prouvent pas son exécution sous Linux.

Attribution du scaffold généré et adapté: BASE, Bâtir des Assistants avec une Structure d'Expertise, par AI Swiss, https://a-i.swiss. Contenus upstream CC BY 4.0; code upstream Apache-2.0. Les licences sont distribuées dans `node_modules/@ai-swiss/base/LICENSES`. Voir [le plan d'intégration](../../docs/architecture/BASE_UPSTREAM_INTEGRATION.md).
