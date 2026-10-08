# Intégration du framework BASE d’AI Swiss

Correction de référence du 8 octobre 2026, demandée par l’utilisateur.

BASE désigne exclusivement [ai-swiss/base](https://github.com/ai-swiss/base), le framework ouvert de ressources, agents et procédures versionnées. La référence étudiée est la version 1.5.1, commit `cc0e4d1a723565fb5ebb17c6a26664423e5226c1`. Le standard de ressources est `base.resource.v1`.

## Répartition des responsabilités

Le framework fournit le corpus de méthode, sa validation, sa découverte et son routage. FlowPilot fournit les adaptateurs authentifiés vers les services métier, le périmètre institut, les permissions, les décisions humaines et les preuves transactionnelles. JV reste la source des faits structurés; le modèle produit leur formulation.

Les composants Python et navigateur développés aux checkpoints 17A–17O sont des fondations applicatives FlowPilot. Leurs tests restent valables pour ces composants; ils ne démontrent pas une intégration du framework upstream. Les noms historiques `base` sont conservés pour éviter une migration prématurée, sans équivalence avec le package officiel.

## Plan corrigé de la phase 17

1. Installer la dépendance officielle à une révision verrouillée dans `integrations/base`, avec lockfile et attribution.
2. Déclarer un agent FlowPilot et ses procédures au format officiel; valider le corpus et rejouer le routage avec la CLI upstream.
3. Relier les procédures aux capacités applicatives par un adaptateur serveur explicite. Aucun identifiant utilisateur, institut ou droit fourni par le modèle ne fait autorité.
4. Vérifier de bout en bout découverte, choix/abstention, contexte minimal, refus de permission et preuves des lectures réelles.
5. Brancher les opérations sensibles uniquement sur les préparations, décisions et exécutions déjà contrôlées par le domaine. Les confirmations de fichiers du broker BASE ne remplacent pas les décisions métier.
6. Évaluer les sorties et les frontières de transmission avant toute connexion distante, MCP ou fournisseur.

La configuration initiale est `local-only`. Une consigne dans un fichier ne prouve pas un contrôle mécanique: les garanties du broker ne s’appliquent qu’aux chemins effectivement médiés. Le premier corpus ne contient aucune donnée cliente et ne dispose d’aucun outil d’écriture métier.

## Acceptation

`BASE_UPSTREAM_CORPUS`, `BASE_UPSTREAM_ROUTING` et `BASE_APPLICATION_ADAPTER` complètent les six objectifs historiques. Les deux premiers exigent les commandes upstream; le troisième exige une requête réelle passant du framework au service autorisé. La phase reste partielle tant que cette chaîne et ses refus ne sont pas vérifiés. Une validation de corpus seule ne clôture pas la phase.

## Attribution

BASE, Bâtir des Assistants avec une Structure d’Expertise, par AI Swiss, https://a-i.swiss. Le code upstream est sous Apache-2.0; les contenus de méthode, exemples et documents upstream sont sous CC BY 4.0. Le scaffold de `workspace` est généré par `base init`, puis adapté pour FlowPilot. Voir les licences distribuées dans le package installé et [LICENSING.md upstream](https://github.com/ai-swiss/base/blob/cc0e4d1a723565fb5ebb17c6a26664423e5226c1/LICENSING.md).
