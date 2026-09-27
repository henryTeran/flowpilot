# Point d'avancement du projet

Date: 2026-09-28
Branche: pivot/bodyminute-workflow

## Ce qui est déjà fait

- Renommage commercial appliqué: BodyMinute -> FlowPilot Institut Manager.
- Branding mis à jour dans le backend, le frontend, la config et Docker.
- Composant sidebar renommé:
  - `BodyMinuteSidebar.tsx` -> `FlowPilotSidebar.tsx`
  - import mis à jour dans `frontend/src/App.tsx`.
- Vérification frontend OK:
  - `npm run build` réussi.

## État produit actuel

- Backend FastAPI modulaire (auth, tickets, planning, chiffres, realtime, etc.).
- Frontend React/TypeScript avec écrans planning, tickets, encaissement et chiffres.
- Données de démo disponibles via endpoint dev.

## Là où reprendre

1. Lancer l'environnement local:
   - `docker compose up --build`
2. Lancer le frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev`
3. Vérifier le flux complet:
   - identification collaboratrice
   - création ticket
   - assignation / démarrage prestation
   - encaissement
   - affichage chiffres

## Prochaines étapes pour finir le projet

1. Stabiliser le workflow métier ticket -> encaissement (cas limites, validations).
2. Ajouter/compléter les tests backend par module (tickets, planning, chiffres).
3. Ajouter des tests frontend sur les écrans critiques.
4. Nettoyer les endpoints dev et sécuriser la config prod.
5. Préparer une démo recruteur (README avec captures + vidéo courte).

## Notes

- Le dépôt contenait déjà des modifications en cours avant ce passage.
- Ce fichier sert de checkpoint pour reprendre rapidement le travail.
