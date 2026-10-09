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

## Packaging runtime : checkpoint 17S

Le Dockerfile backend passe à un build avec contexte racine et un stage Node. Le stage installe le package officiel verrouillé, puis valide le corpus et les exemples. L’image finale garde l’application à `/app/app`, avec Node et l’intégration à `/opt/flowpilot-base`. `BASE_RUNTIME_DIRECTORY` est un paramètre de déploiement serveur; un emplacement configuré manquant refuse avec 503, sans fallback vers le dépôt.

Compose cible ce Dockerfile et conserve son montage applicatif. Une allowlist `.dockerignore` exclut les fichiers locaux inutiles, secrets, traces et brouillons. `docker compose config --quiet` passe sans lancer les services ni modifier la base persistante.

Un test copie le package upstream complet et le corpus dans un dossier temporaire indépendant, puis appelle réellement le bridge depuis cet emplacement. Une première exécution a exposé MAX_PATH sur les exemples upstream; les chemins longs Windows corrigent la copie sans retirer de fichiers du package. Test de relocation et refus d’emplacement manquant : 2 réussis. Régression finale packaging/query/récupération : 14 réussis, aucun échec ni test ignoré.

Docker demeure indisponible sur la machine : le build et le smoke test de l’image sont **non vérifiés**. Aucun résultat de test local n’est présenté comme une preuve Linux ou une validation du conteneur final. La validation PostgreSQL est poursuivie dans une instance temporaire isolée, indépendamment des conteneurs persistants.

## PostgreSQL et image Linux : checkpoint 17T

La validation indépendante utilise PostgreSQL 16.15 Windows dans un cluster temporaire du cache, sur un port loopback distinct. Les tests possèdent chacun un schéma aléatoire. Le Python 3.12 enregistré localement était obsolète; Python 3.13 standard est utilisé dans un environnement séparé. Le premier lancement (26 réussis, 6 erreurs de setup) nécessitait une URL explicite `postgresql+psycopg2` pour le driver du backend. Après correction : 32 réussis, aucun échec ou test ignoré. La régression complète des 18 modules BASE : **128 réussis en 217,58 s**, aucun échec ou test ignoré. Les schémas temporaires ont tous disparu et le serveur temporaire a été arrêté.

Le client Docker Windows ne trouvait pas sa named pipe, mais le moteur Docker existant est accessible depuis Ubuntu/WSL. Le build du Dockerfile corrigé réussit, avec validation de 14 ressources et 25 exemples upstream. Aucun conteneur persistant n’est relancé. Node 22.23.3 exécute réellement le broker dans l’image Python 3.12.

Un PostgreSQL 16.14 Linux distinct, sans port publié et avec stockage tmpfs, sert aux tests dans cette image. Les tests sont montés en lecture seule; seul le client HTTP de test est installé dans le conteneur éphémère. Première validation : 14 réussis. Un test supplémentaire reproduit ensuite un 503 incorrect pour 2 000 emojis valides : sérialisation ASCII et comptage UTF-16 ne respectaient pas le comptage Unicode de Python. Le bridge utilise UTF-8 et le nombre de codepoints, avec une limite de trame cohérente. Test de reproduction avant correction : 1 échec; après correction : 1 réussi.

Image finale reconstruite : `sha256:2d48b70add93e2cc48cc4a04be24eaccaf972d4008497f44b78e14da67577590`. Validation finale de cette image et de PostgreSQL Linux : **15 réussis en 73,11 s**, aucun échec ou test ignoré. Les nouvelles lectures, permissions, fake providers, isolation inter-instituts, empreintes, absence de mutations, relocation et frontière Unicode sont couvertes. Zéro schéma temporaire résiduel; conteneur et réseau de validation retirés après vérification de leur label de propriété.

Ces preuves lèvent les manques PostgreSQL et build/smoke Linux des checkpoints précédents. La fermeture de phase exige encore l’audit final des gates et du périmètre d’audit des interactions. Aucune validation de production, migration persistante, entrée humaine physique, fournisseur distant, publication ou push n’est revendiquée.

## Corrélation des interactions : checkpoint 17U

L’audit final a découvert que le logger initial `flowpilot.base.query` ne descendait pas du logger applicatif configuré `app` : son message INFO ne constituait pas une preuve d’émission effective. Le nouveau logger `app.modules.base.audit` utilise le formateur JSON existant. Les 21 handlers historiques et les deux nouvelles frontières query/discovery émettent tentative et résultat, identité et institut signés, action fermée et empreintes, sans texte brut ni détail privé des exceptions. Les refus d’authentification et de validation antérieurs au handler restent dans la journalisation HTTP générale, sans identité applicative inventée.

Le request ID HTTP et l’ID UUID de l’interaction ont des champs distincts. La réponse query reprend l’ID d’interaction. Un ContextVar transmet cet ID, l’acteur et l’institut au sous-processus officiel via `BASE_TRACE_ACTOR`, sans mutation globale de l’environnement. Les traces réelles upstream permettent de joindre les deux couches; leurs `args_hash` conservent le format upstream `sha256:<digest>`. Aucun identifiant de sélection ni fait métier n’est transmis au routage.

Les logs opérationnels ne sont pas des reçus métier durables, une signature ou une garantie de rétention. Les originaux d’opération, décisions et exécutions existants restent les preuves transactionnelles. Le brouillon de journal HTTP conservé dans le stash n’est pas restauré et les lectures n’ajoutent aucune écriture SQL.

Tests Windows ciblés : **50 réussis en 35,71 s**, aucun échec ni test ignoré. Ils vérifient l’émission JSON réelle, la corrélation signée jusque dans les fichiers de trace upstream, les empreintes de preuve, les refus/erreurs sans contenu privé, la séparation de deux contextes concurrents et la couverture de toutes les actions historiques. La première exécution Linux avait une assertion incorrecte sur le préfixe de hash officiel : 1 échec / 48 réussis; après correction de cette assertion, 49 réussis. La régression finale des handlers instrumentés et PostgreSQL est consignée ci-dessous après son résultat terminal.

Image finale `sha256:4a636f2577375d32a3bce549e21b23e5b9a120951a83c7049461b0ddf6bd1a53` : **65 réussis en 227,83 s**, aucun échec; **14 tests PostgreSQL ignorés** car cette exécution utilise SQLite. Cette régression couvre les routes historiques, plans, décisions et exécutions instrumentés en plus du bridge officiel, des intentions et des nouvelles lectures. Les tests PostgreSQL sont exécutés séparément sur le cluster temporaire Windows, sans utiliser la base persistante de l’application.

Régression complémentaire SQLite/PostgreSQL réelle : **34 réussis en 213,16 s**, aucun échec ni test ignoré. Elle couvre les handlers signés, originaux de plans, décisions, exécutions et la chaîne official BASE → HTTP → quatre lectures PostgreSQL, avec refus inter-instituts et observateur SQL sans mutation. Zéro schéma temporaire résiduel; serveur temporaire arrêté. Le conteneur Linux de test est retiré automatiquement. Les avertissements sont des dépréciations existantes et des constructions volontairement invalides dans les tests de garde.
