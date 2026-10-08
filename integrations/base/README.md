# BASE officiel pour FlowPilot

Depuis ce dossier: `npm ci --ignore-scripts`, puis `npm run validate`, `npm run index` et `npm test`.

La dépendance officielle est verrouillée sur le commit AI Swiss `cc0e4d1a723565fb5ebb17c6a26664423e5226c1` et le lockfile. Node 18 ou supérieur est requis. Les scripts appellent la CLI du package installé, sans dépendre du clone de recherche dans `.cache`.

`workspace` a été initialisé avec la CLI upstream, puis enrichi d'une procédure FlowPilot. Il est configuré `local-only`, sans données clientes et sans outil métier exécutable. Le raccordement à l'API authentifiée reste ouvert: ces commandes valident le corpus et son routage, pas les services du logiciel.

Attribution du scaffold généré et adapté: BASE, Bâtir des Assistants avec une Structure d'Expertise, par AI Swiss, https://a-i.swiss. Contenus upstream CC BY 4.0; code upstream Apache-2.0. Les licences sont distribuées dans `node_modules/@ai-swiss/base/LICENSES`. Voir [le plan d'intégration](../../docs/architecture/BASE_UPSTREAM_INTEGRATION.md).
