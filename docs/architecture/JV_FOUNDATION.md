# JV : analyses déterministes et preuves sources

La phase 18 suit la clôture BASE 17V. Sa référence est le Master Plan, sections 9 et 39 : calculs structurés, diagnostics, comparaison, scoring, aide à la décision, preuves et explicabilité, indépendamment du provider de langage.

## Checkpoint 18A : noyau descriptif opérationnel

`app.modules.jv.operational.OperationalAnalyzer` implémente le port déterministe établi en phase BASE. Il accepte une preuve serveur capturée par les quatre services READ/SUGGEST, reconstruit ses modèles imbriqués et vérifie son SHA complet, la correspondance avec le registre, le type de résultat, la chronologie et les identifiants imbriqués de scope/ressource.

Il produit des métriques typées : nombre de tickets et de tickets affectés, disponibilité de la collaboratrice sélectionnée et nombre de créneaux à venir, nombre d’options et d’options affectables, nombre de collaboratrices et sessions de planning. La disponibilité et les motifs d’affectation sont repris du service source. Le noyau ne recalcule pas les règles de planning ni d’affectation et n’autorise aucune action.

Chaque métrique et diagnostic cite le SHA de preuve et un pointeur JSON dans la source. La sortie précise sa version de règles, son scope, la source, les inconnues et son propre SHA. Les mêmes faits produisent la même sortie sans horloge, base, framework, réseau ou modèle de langage supplémentaires. Une file observée vide donne un compte connu de zéro; aucun revenu, demande non observée, effet causal ou garantie de disponibilité future n’en est déduit.

Cette frontière est **interne** : une empreinte valide ne prouve pas l’origine, l’authentification, l’actualité ou l’exhaustivité des faits. Elle ne doit pas devenir un endpoint qui accepte des preuves arbitraires fournies par un client. Le raccordement HTTP devra construire la source via les lectures signées et services existants. Les valeurs inconnues restent inconnues et les logs ne remplacent pas les originaux métier.

## Checkpoint 18B : capture authentifiée et analyse

`POST /api/v1/jv/query` reçoit le même message et contexte UI limité que BASE. L’identité, le rôle et l’institut viennent du JWT vérifié. Aucun champ `evidence`, `analysis`, acteur, institut, SQL ou provider fourni par le client n’est accepté. Le service appelle l’orchestrateur BASE existant puis le noyau JV sur sa preuve, sans nouvelle requête métier ni deuxième routage.

La réponse associe `source` (réponse BASE complète, avec son ID de requête et sa preuve) et `analysis` (faits JV citant exactement cette preuve). Une clarification BASE donne une analyse nulle. Une indisponibilité du framework refuse; une preuve incohérente détectée par JV refuse avec 503 sans exposer de détail privé. Aucun résumé inventé ne remplace des faits manquants.

Le logger applicatif JV associe résultat et SHA d’analyse à l’ID d’interaction BASE, à l’acteur signé, à l’institut et au SHA de source, sans texte brut. Les lectures et analyses ne produisent aucune mutation SQL. Ce raccordement ne constitue pas une politique de rétention des logs ou une garantie de fraîcheur après la lecture; les horodatages de source restent explicites.

Validation Windows SQLite/PostgreSQL 16.15 : **22 tests réussis en 49,74 s**, aucun échec ni test ignoré, couvrant routes JV, noyau et régression query BASE. Les quatre captures signées, empreintes liées, refus inter-instituts et file étrangère vide sont vérifiés sur les deux moteurs; un observateur SQL confirme l’absence d’écriture pendant ces lectures. Les fixtures PostgreSQL possèdent des schémas aléatoires supprimés après les tests; zéro schéma résiduel et serveur temporaire arrêté. Les tests de contrat vérifient injection/auth avant routage, clarification sans analyse et refus de panne/preuve invalide sans détail privé. Aucune validation Linux/native/production supplémentaire n’est revendiquée.

## Acceptation restante

`JV_RULES`, `JV_EVIDENCE`, `JV_PROVIDER_INDEPENDENCE` restent **PARTIAL** pour la phase entière. Le noyau descriptif seul ne ferme pas la phase.

La suite ajoute comparaison et scoring avec critères explicites et explications vérifiables. Les diagnostics économiques et contributions au CA doivent utiliser les faits financiers/workforce réellement enregistrés et leurs règles existantes; aucune causalité ou perte financière ne doit être inférée d’un compte de file ou d’un planning. Les tests de phase devront couvrir ces calculs, les inconnues, le scope, les refus et l’indépendance de provider avant clôture.
