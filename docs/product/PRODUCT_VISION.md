# FlowPilot - Vision produit 2026

Date: 2026-09-28

## Positionnement

FlowPilot doit devenir un logiciel institut nouvelle génération:

- plus complet sur l'opérationnel quotidien
- plus rapide à utiliser en situation réelle
- plus élégant visuellement qu'une solution legacy
- plus intelligent sur l'aide à la décision

## Promesse produit

"Réduire la charge mentale des équipes institut tout en augmentant la qualité de service et la performance business."

## Piliers stratégiques

1. Excellence UX
- parcours centrés tâches réelles (planning, ticket, encaissement, RDV)
- minimisation des actions et erreurs
- feedback instantané sur chaque action critique

2. Excellence UI
- identité visuelle premium, moderne et mémorable
- hiérarchie visuelle claire (priorités, urgences, statuts)
- composants cohérents sur desktop et tablette

3. Excellence métier
- couverture complète du flux institut: accueil -> prestation -> encaissement -> pilotage
- gestion fine des rôles, exceptions et cas limites
- robustesse et traçabilité des opérations

4. Excellence data
- indicateurs temps réel utiles (pas seulement décoratifs)
- alertes proactives (retards, surcharge, goulots)
- analyse de performance par collaboratrice, service et plage horaire

5. Excellence architecture
- modularité stricte pour itérer vite sans dette technique bloquante
- sécurité by design sur tous les flux sensibles
- scalabilité horizontale pour absorber la croissance multi-instituts

## Cibles fonctionnelles (V2+)

1. Opérations temps réel
- timeline planning enrichie (capacité, retards, conflits)
- assignation intelligente avec suggestions
- file d'attente priorisée automatiquement

2. CRM léger intégré
- historique client consolidé
- préférences, fréquence, comportement d'achat
- rappels intelligents post-prestation

3. Pilotage business
- chiffres live actionnables
- comparatifs jour/semaine/mois
- détection des pertes de revenu (annulations, no-show, temps morts)

4. Qualité de service
- contrôle des temps d'attente
- suivi satisfaction simplifié
- workflows anti-erreur à l'encaissement

## Direction UX/UI

1. Style visuel
- interface lumineuse, premium, nette
- densité d'information maîtrisée
- micro-interactions utiles, pas décoratives

2. Ergonomie
- actions critiques toujours visibles
- raccourcis pour tâches répétitives
- navigation stable, prédictible, rapide

3. Accessibilité
- contrastes et taille de typo lisibles en institut
- zones cliquables adaptées au tactile
- états d'erreur explicites et guidés

## Plan d'exécution recommandé

1. Sprint 1 - Fondations design
- définir tokens design (couleurs, typo, espacements, rayons, ombres)
- harmoniser boutons, cards, formulaires, badges statuts
- formaliser les règles responsive tablette/desktop

2. Sprint 2 - Refonte des écrans coeur
- planning institut
- création ticket multi-prestations
- encaissement
- chiffres

3. Sprint 3 - Intelligence opérationnelle
- alertes retards et surcharge
- suggestions d'assignation
- indicateurs temps réel prioritaires

4. Sprint 4 - Finition premium
- animation de transitions clés
- polish visuel
- optimisation performances UI
- tests UX sur scénarios réels

5. Sprint transversal - Architecture robuste
- architecture en couches (domain, application, infrastructure)
- observabilité complète (logs structurés, métriques, traces)
- sécurité applicative et gouvernance des accès
- stratégie tests automatisés (unitaires, intégration, e2e)

## KPI de succès

- temps moyen pour créer et affecter un ticket
- temps moyen de passage en caisse
- taux d'erreur opérationnelle
- taux d'utilisation des fonctionnalités clés
- satisfaction équipe institut
- disponibilité applicative
- latence p95 des endpoints critiques
- taux d'incidents sécurité

## Décision de cap

Ce projet n'est plus un clone. FlowPilot devient un produit original, premium et orienté impact métier.
