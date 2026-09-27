CURRENT_PHASE = PHASE 0

CURRENT_CHECKPOINT = 0A — Workflow Audit

CORE_WORKFLOW = PARTIAL

IDENTIFICATION = PARTIAL
TICKETS = PARTIAL
PLANNING = PARTIAL
CHECKOUT = PARTIAL
ANALYTICS = PARTIAL

TESTS =
- Suites ciblées disponibles: backend/tests/test_smoke.py uniquement.
- Exécution ciblée impossible localement: python -m pytest -q tests/test_smoke.py -> No module named pytest.

BLOCKERS =
- Environnement de test incomplet localement (pytest manquant).
- Pas de tests automatisés dédiés tickets/planning/checkout/chiffres à ce stade.

NEXT_STEP =
- CHECKPOINT 0B — Durcir les transitions critiques et l'idempotence (start/finish/payment), puis ajouter tests ciblés workflow métier.

WORKING_TREE =
- Changements préexistants préservés hors scope checkpoint 0A:
	.env.example
	backend/app/core/config.py
	backend/app/main.py
	backend/app/core/http.py
	frontend/src/components/Sidebar.tsx (suppression)
	frontend/src/components/TopBar.tsx (suppression)
	frontend/src/styles.css
