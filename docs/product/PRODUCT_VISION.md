# FlowPilot - Vision produit 2026

Date: 2026-09-28

## Positionnement

FlowPilot est une plateforme d'opération institut orientée walk-in first, capable de supporter aussi le booking hybride.

Le produit est conçu pour les instituts où :

- les clients arrivent souvent sans rendez-vous ;
- la réception doit connaître rapidement la capacité réelle disponible ;
- les collaborateurs ne doivent pas être interrompus pour répondre à des questions de disponibilité ;
- le planning doit refléter en temps réel les changements d'activité ;
- l'exploitation doit rester fluide même avec une coexistence de clients walk-in et de clients avec réservation.

## Promesse produit

"Offrir une estimation fiable du temps d'attente, une visibilité opérationnelle en temps réel, et une expérience premium à l'accueil, au planning et à l'encaissement."

## Objectif métier

FlowPilot vise à centraliser le cœur opérationnel d'un institut :

- accueil client ;
- gestion de la file d'attente ;
- gestion des disponibilités ;
- affectation des collaborateurs et ressources ;
- suivi en cours de service ;
- recalcul immédiat du temps d'attente et de la capacité ;
- convergence entre flow walk-in et flow réservation.

## Principes product

1. Walk-in first
- la file d'attente et le temps d'attente sont des priorités opérationnelles majeures ;
- l'accueil doit pouvoir créer un ticket anonyme sans friction ;
- la queue doit être exploitable même sans renseignements complets sur le client.

2. Hybrid booking
- les rendez-vous restent nécessaires pour certains services ou ressources ;
- les réservations et les walk-ins partagent le même moteur opérationnel.

3. Reliable operational visibility
- l'équipe doit voir immédiatement la capacité disponible ;
- les temps d'attente doivent reposer sur des règles métier déterministes ;
- les dépassements, extensions et pauses doivent recalculer l'état du système.

4. Premium operational UX
- l'expérience ne doit pas être lourde ni confuse pour le staff ;
- les décisions doivent être lisibles et rapides ;
- le flux est pensé pour réduire les interruptions internes et les erreurs d'assignation.

## Valeur ajoutée stratégique

FlowPilot ne ressemble pas à un outil de réservation isolé. Il s'adresse à une réalité de terrain plus complexe :

- client walk-in sans rendez-vous ;
- réservation sur ressources spécifiques ;
- file d'attente variable ;
- service pouvant être prolongé ;
- disponibilité réelle dépendant des états collaborateurs, ressources et services actifs ;
- besoin d'un pilotage opérationnel en temps réel.

Le produit combine donc :

- fiabilité opérationnelle ;
- qualité d'expérience client ;
- visibilité pour la réception ;
- flexibilité pour le staff ;
- architecture prête pour l'intégration progressive et l'extension premium.

## Piliers stratégiques

1. Excellence UX
- parcours centrés sur les tâches opérationnelles réelles
- minimisation des actions inutiles et des erreurs
- feedback instantané sur les états critiques

2. Excellence métier
- support du walk-in et du booking dans un même système
- logique de disponibilité déterministe
- règles de priorité, conflit et recalcul intégrées au cœur du produit

3. Excellence data
- temps d'attente, capacité, occupation et disponibilité visibles
- indicateurs temps réel utiles pour la décision
- analyse de performance par collaborateur, service et créneau

4. Excellence architecture
- modularité pour évoluer sans dette technique bloquante
- sécurité by design pour les flux sensibles
- support du mode shadow / intégration progressive

## Cibles fonctionnelles

### Opérations temps réel
- file d'attente priorisée ;
- estimation du temps d'attente ;
- recalcul après extension, pause, fin de service ou arrivée ;
- assignation compatible avec les ressources et l'état du collaborateur.

### Hybrid scheduling
- walk-in first avec ticket anonyme ;
- réservations spécifiques avec ressources impliquées ;
- coexistence des flux de travail sans rupture de logique opérationnelle.

### Pilotage business
- visibilité temps réel sur charge, occupation et conflits ;
- identification des goulots de capacité ;
- réduction des interruptions et des erreurs de planification.

### Qualité de service
- contrôle du temps d'attente ;
- réduction des ambiguïtés réception / planning ;
- parcours premium pour la gestion quotidienne de l'institut.

## KPI de succès

- temps moyen de réponse à l'accueil pour un walk-in
- précision de l'estimation de temps d'attente
- taux de conflits d'assignation évités
- temps moyen pour affecter un client à un créneau
- taux d'occupation réel vs planifié
- satisfaction équipe institut
- disponibilité applicative
- latence p95 des endpoints critiques

## Décision de cap

FlowPilot est un produit original, premium et orienté performance opérationnelle. Il n'est ni un simple ticketing de réception, ni un simple agenda de rendez-vous : il est conçu comme un moteur de flux et de capacité pour un institut hybride, en temps réel, avec une logique métier déterministe et fiable.
