# Phase BASE rouverte : audit et implémentation applicative

Demande utilisateur du 8 octobre 2026, reprise le 9 octobre. Le checkpoint `6e639c1` préparait l’intégration; il ne clôturait pas la phase. Les phases précédentes restent acquises dans leur périmètre de preuve.

## Audit à la reprise

| Gate demandé | État à la reprise | Preuve ou manque |
| --- | --- | --- |
| BASE_UPSTREAM_INTEGRATION | PARTIAL | Dépendance verrouillée, corpus valide, aucun appel runtime métier |
| BASE_ADAPTER_LAYER | MISSING | Aucun orchestrateur applicatif utilisant upstream |
| CONTEXT_RESOLVER | PARTIAL | Contrôles historiques, aucun contexte de requête upstream |
| INTENT_RESOLVER | PARTIAL | Résolveur local historique non connecté au framework |
| CAPABILITY_REGISTRY | PARTIAL | Trois capacités historiques, lectures opérationnelles recommandées absentes |
| PERMISSION_GUARD | PARTIAL | Contrôles historiques; chaîne upstream non testée |
| BUSINESS_RULE_GUARD | PARTIAL | Services existants vérifiés; raccordement manquant |
| EVIDENCE_BUILDER | PARTIAL | Preuves historiques; réponse query manquante |
| FLOWPILOT_SERVICE_INTEGRATION | MISSING | Aucune requête allant du framework aux services |
| FAKE_PROVIDER_TESTS | PARTIAL | Contrat historique seulement |
| TENANT_ISOLATION | PARTIAL | Tests historiques seulement |
| BASE_READ_VERTICAL_SLICE | MISSING | Aucun endpoint query upstream |
| TESTS | PARTIAL | Validation du corpus et des composants séparés |

## Premier raccordement : checkpoint 17Q

`POST /api/v1/base/query` reçoit un message et un contexte UI optionnel avec uniquement `employee_id`, `ticket_id`, `service_id`. L’identité et l’institut proviennent du JWT vérifié avec l’autorisation existante `can_manage_ticket`. Aucun champ d’identité, SQL, niveau d’exécution ou capacité libre n’est accepté.

Le bridge Node appelle réellement `routeRequest` et `contextPack` du package upstream installé. Le mode lexical est explicitement choisi, indépendant des réglages de modèles d’une machine. Le message passe par stdin, sans shell, avec limites de taille et timeout. Si le framework est indisponible ou renvoie un résultat invalide, la requête échoue sans routeur parallèle de secours.

Les quatre procédures upstream ont une correspondance fermée avec `EMPLOYEE_AVAILABILITY` (0), `QUEUE_ASSIGNMENT_OPTIONS` (1), `QUEUE_READ` (0) et `PLANNING_READ` (0). Une sélection manquante ou un processus hors de cette correspondance entraîne une clarification. Les modèles Pydantic valident les sélections et sorties; `GET /api/v1/base/query-capabilities` publie leurs schémas JSON et permissions.

Les adaptateurs appellent les services existants de scheduling et planning. Une projection de lecture ajoutée au service tickets réutilise le dépôt et les positions de file existants. Aucun calcul métier de disponibilité, affectation, statut ou ordre de file n’est dupliqué. Les capacités n’autorisent aucune écriture.

La réponse contient `answer`, `intent`, `capability`, `evidence`, `actions` vide et `request_id`. Les faits omettent noms clients, notes, prix et noms des collaboratrices. Les raisons d’indisponibilité ou d’affectation viennent du moteur existant. Le SHA couvre la représentation JSON complète des preuves; il n’est ni une signature ni un original retenu. Les horodatages délimitent la lecture; aucune capture globale atomique n’est revendiquée.

Un provider optionnel ne reçoit que le message et les noms de capacités. Sa proposition doit être valide et correspondre au processus choisi par BASE; elle ne peut créer une nouvelle autorité. Une panne du provider conserve le chemin déterministe upstream; une sortie invalide est refusée. Aucun fournisseur concret ni appel distant n’est configuré. `analysis_contract.py` définit seulement les ports futurs JV et langage; il n’implémente pas la phase JV.

L’audit opérationnel associe request ID, identité signée, institut, résultat et SHA de preuve sans contenu brut. Les traces upstream sont locales et utilisent un hash du message. Ces logs ne remplacent pas un journal métier durable; le brouillon HTTP historique mis de côté n’est pas réactivé.

## Limites et suite

La preuve de ce checkpoint porte sur la CLI officielle, le runtime Node local et l’API avec SQLite isolée. PostgreSQL, image de déploiement avec Node/package/corpus, robustesse en charge, interface utilisateur et audit durable restent à vérifier ou compléter. Le Dockerfile backend historique n’embarque pas encore ce runtime: cet endpoint doit donc refuser avec 503 dans cette image, pas annoncer une intégration disponible.

La phase reste **PARTIAL**, `BASE_PHASE_REOPENED = true`. La fermeture des gates de phase exige les preuves de la chaîne complète dans son environnement cible; aucun résultat historique n’est réattribué à upstream.

| Gate | État après 17Q | Périmètre démontré ou suite |
| --- | --- | --- |
| BASE_UPSTREAM_INTEGRATION | PARTIAL | Runtime local réel; packaging cible manquant |
| BASE_ADAPTER_LAYER | PARTIAL | Quatre lectures raccordées; autres entrées historiques à aligner |
| CONTEXT_RESOLVER | PASS | Session signée, selections explicites, données minimales pour les quatre lectures |
| INTENT_RESOLVER | PARTIAL | Routage lexical/abstention validés; endpoint historique `/intents/resolve` encore indépendant, à subordonner au framework |
| CAPABILITY_REGISTRY | PASS | Quatre capacités fermées, niveaux 0/1, schémas réels et services déclarés |
| PERMISSION_GUARD | PASS | Rôles existants, identité signée, références étrangères refusées dans les tests locaux |
| BUSINESS_RULE_GUARD | PASS | Moteurs existants; pause et réservation d'une collaboratrice conservées |
| EVIDENCE_BUILDER | PASS | Sorties structurées, horodatages, SHA vérifié, aucun effet exécuté |
| FLOWPILOT_SERVICE_INTEGRATION | PARTIAL | Chaîne réelle SQLite validée; PostgreSQL/container non vérifiés |
| FAKE_PROVIDER_TESTS | PASS | Accord valide, panne, sortie malformée et tentative de bypass |
| TENANT_ISOLATION | PARTIAL | Références étrangères refusées avec SQLite; acceptation PostgreSQL à compléter |
| BASE_READ_VERTICAL_SLICE | PASS | API authentifiée, runtime upstream et quatre services réels en local |
| TESTS | PARTIAL | Tests ciblés locaux verts; régressions backend complètes/environnement cible ouverts |

## Alignement des entrées historiques : checkpoint 17R

Les requêtes `/base/institutes/{id}/intents/resolve` et les nouvelles préparations de plans utilisent maintenant `UpstreamInterpreter`, qui dépend du même bridge officiel. Trois procédures spécialisées upstream couvrent `WAITLIST_READ`, `WAITLIST_MATCH` et `PLANNING_OPTIMIZATION`. Le résolveur local historique reste un outil de tests de contrat isolés; aucune entrée applicative de langage ne l’utilise comme routeur.

Le premier guide générique devient un document de référence. Cela supprime sa concurrence avec les procédures spécialisées sans réduire le seuil d’abstention du framework. La CLI valide 14 ressources et 25/25 exemples de routage après correction de deux ambiguïtés observées.

Une nouvelle préparation nécessite BASE; une panne refuse la résolution sans repli indépendant. La récupération idempotente d’un plan déjà retenu vérifie et rend l’original sans rejouer la langue ni le framework. Un test avec panne réelle simulée du bridge démontre refus de la nouvelle préparation, absence d’original pour cette nouvelle clé et récupération exacte de la clé antérieure.

Régression locale des intentions historiques, plans et requêtes : 46 tests réussis, 4 tests PostgreSQL non exécutés faute d’environnement configuré. Test dédié de récupération : 1 réussi. Le contrôle d’intention est raccordé; l’acceptation PostgreSQL et le packaging runtime restent ouverts. La phase n’est pas clôturée.
