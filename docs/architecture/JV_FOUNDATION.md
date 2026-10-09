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

## Checkpoint 18C : scoring explicable des alternatives

`POST /api/v1/jv/institutes/{institute_id}/optimization` réutilise la permission manager exacte de l’optimiseur et son contrat de sélection : politique retenue et SHA, demande retenue et événement/SHA courants, horizon et politique de matching. Aucun score, poids libre, observation, capacité ou provider du client ne fait autorité.

Le service existant capture les faits et applique la politique explicitement enregistrée. JV vérifie les empreintes et scopes des originaux de politique/demande, la chronologie, les preuves de normalisation et le résultat, en réutilisant `sources.derive`, `policy.scoring_policy` et `domain.score`. Il ne recopie pas leurs calculs. L’analyse expose chaque alternative avec score rationnel exact, rang, contraintes, raisons et contributions reward/penalty, avec pointeur JSON et SHA de la capture complète. La sortie possède également son SHA et le SHA de politique.

Les rangs et ex æquo restent ceux du moteur souverain. Un facteur pondéré inconnu empêche un classement complet; il n’est pas remplacé par zéro. Une contrainte dure ne se compense pas par un score. Une source refusée reste `source_unavailable`, avec le motif existant et aucune alternative. Les valeurs de catalogue sans devise ne deviennent pas un revenu observé, un profit, une prédiction ou une autorisation de réservation. Toute action nécessite toujours revue humaine et revalidation métier.

Validation : **29 tests réussis en 36,80 s**, aucun échec ni test ignoré, incluant routes JV opérationnelles, scoring/revue existants et nouveaux tests signés SQLite/PostgreSQL. Un test supplémentaire de source refusée et de politique étrangère réempreintée réussit (**1 en 3,20 s**). Les tests vérifient réutilisation exacte, contributions/citations, rejet de score et politique altérés, refus RBAC/injection, inconnues pondérées, contraintes et ex æquo du moteur existant. L’observateur SQL confirme zéro mutation pendant lecture et analyse. Zéro schéma temporaire résiduel; serveur temporaire arrêté.

## Checkpoint 18D : comparaison des montants observés

`POST /api/v1/jv/institutes/{institute_id}/billing-comparison` reçoit deux fenêtres explicites, positives, ordonnées et sans recouvrement. La permission manager exacte existante reste obligatoire. Le client ne fournit ni montants, ni sources, ni identité de calcul. Le service de CA existant capture chaque cohorte de tickets payés datés et ses lignes actives; JV réutilise ses agrégats vérifiés.

L’analyse expose les écarts de compte de tickets et, séparément pour CHF et EUR, les totaux enregistrés complets et leur différence en unités mineures. Le pourcentage est le ratio exact `100 × différence / baseline`, sans flottant ni conversion de devise. Une base monétaire nulle donne un écart connu mais un pourcentage indisponible. Une devise inconnue ou un groupe de montants incomplet empêche une différence complète; les diagnostics restent explicites. Un groupe de devise absent d’une capture sans devise inconnue représente zéro dans cette cohorte enregistrée.

Les périodes de durées différentes sont signalées; les écarts restent ceux des totaux bruts, sans ajustement quotidien. Les tickets payés sans date sont un diagnostic à l’échelle de l’institut, sans affectation inventée à une période. La source conserve ses fenêtres et ses horodatages de capture distincts; les agrégats ne certifient ni exhaustivité des ventes, ni règlement externe, ni capture globale atomique. Le SHA lie l’analyse à la capture complète et chaque comparaison cite ses deux groupes sources. Les contributions causales restent vides/inconnues : cette comparaison n’attribue pas une baisse de CA à des annulations ou à une capacité inutilisée.

Validation SQLite/PostgreSQL réelle : **23 réussis en 19,82 s**, aucun échec ni test ignoré, avec régression des kernels/sources de CA et du scoring JV. Après typage des montants non négatifs et ajout du diagnostic durée/date/exhaustivité : **6 tests ciblés réussis en 6,53 s**, zéro échec/skip. SHA sources/sorties, comparaison −12,4 % exacte, séparation des devises, baseline nulle, montants/devise inconnus, durées inégales, faux drapeau d’exhaustivité, scope, injections et SQL sans mutation sont vérifiés. Zéro schéma temporaire résiduel; serveur temporaire arrêté.

## Checkpoint 18E : contributions arithmétiques exactes

La comparaison passe à la règle versionnée `jv.recorded_billing_comparison.v2`. Pour chaque devise complète, avec un nombre de tickets de référence positif, elle expose deux termes rationnels en unités mineures. Si `N0`, `G0`, `N1`, `G1` désignent les comptes et totaux de tickets payés datés de cette devise :

- terme volume : `(N1 − N0) × G0 / N0`;
- terme panier : `G1 − N1 × G0 / N0`.

Leur somme est exactement `G1 − G0`. La règle fixe l’ordre de cette décomposition; il n’existe aucune attribution causale implicite. Les comptes sont ceux du groupe de devise, jamais ceux de l’ensemble multidevise. La validation structurée vérifie les deux formules et leur somme, afin qu’une paire de termes inventés qui se compensent soit aussi refusée.

Un panier de référence observé à zéro reste connu lorsque ses tickets existent : la décomposition peut être calculée même si le pourcentage est indisponible. Aucun ticket de référence signifie une moyenne inconnue et une décomposition indisponible. Une cohorte courante vide donne un terme volume de `−G0` et un terme panier nul, sans inventer une moyenne courante. Les montants incomplets et devises inconnues restent indisponibles. Les contributions causales demeurent vides; les citations et le SHA lient tous ces termes aux deux agrégats observés.

Validation complète des cinq modules JV sur SQLite et PostgreSQL réel : **24 réussis en 32,96 s**, zéro échec/skip. Les nouvelles variantes couvrent fractions exactes sous faible précision décimale, séparation des devises, disparition de la cohorte courante, baseline monétaire nulle, inconnues et faux termes compensés. Les tests HTTP existants vérifient les termes sur de vraies captures payées avec zéro mutation SQL. Zéro schéma temporaire résiduel; serveur temporaire arrêté. La validation Linux et l’audit final des gates restent à réaliser avant clôture de phase.

## Acceptation restante

`JV_RULES`, `JV_EVIDENCE`, `JV_PROVIDER_INDEPENDENCE` restent **PARTIAL** pour la phase entière. Le noyau descriptif seul ne ferme pas la phase.

La suite ajoute comparaison et scoring avec critères explicites et explications vérifiables. Les diagnostics économiques et contributions au CA doivent utiliser les faits financiers/workforce réellement enregistrés et leurs règles existantes; aucune causalité ou perte financière ne doit être inférée d’un compte de file ou d’un planning. Les tests de phase devront couvrir ces calculs, les inconnues, le scope, les refus et l’indépendance de provider avant clôture.
