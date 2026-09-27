CURRENT_PHASE = PHASE 0
CURRENT_CHECKPOINT = 0B — Durcissement transitions critiques + tests ciblés

CORE_WORKFLOW = PASS
TEST_ENVIRONMENT = PASS
START_SERVICE_GUARD = PASS
FINISH_SERVICE_GUARD = PASS
PAYMENT_GUARD = PASS
WORKFLOW_TARGETED_TESTS = PASS
ANALYTICS_SINGLE_COUNT = PASS
CREATE_TICKET_IDEMPOTENCE = DEFERRED_WITH_EVIDENCE
PERMISSIONS = BLOCKED
refund = NOT_IMPLEMENTED

TESTS =
- Suites ciblées ajoutées:
	backend/tests/conftest.py
	backend/tests/test_ticket_workflow.py
	backend/tests/test_planning_workflow.py
	backend/tests/test_checkout_workflow.py
	backend/tests/test_smoke.py
- Exécution validée:
	py -3.13 -m pytest tests/test_smoke.py tests/test_ticket_workflow.py tests/test_planning_workflow.py tests/test_checkout_workflow.py -q
	Résultat: 20 passed, 2 warnings.

EVIDENCE =
- Idempotence création ticket:
	test_create_ticket_replay_creates_distinct_tickets_current_behavior confirme qu'un rejeu crée 2 tickets distincts.
- Permissions:
	Les routes critiques workflow ne sont pas protégées via dépendance auth/role côté route; wiring permission non finalisable sans décision d'architecture auth globale.

BLOCKERS =
- Aucun blocker technique bloquant le checkpoint 0B.
- Sujet permissions restant hors scope minimal de ce checkpoint (nécessite cadrage auth/RBAC transversal).

NEXT_STEP =
- CHECKPOINT 0C — Décider et implémenter stratégie d'idempotence création ticket (idempotency key/client_request_id + contrainte DB), puis lancer câblage permissions route-level de façon homogène.

WORKING_TREE =
- Changements préexistants préservés hors scope checkpoint 0B:
	.env.example
	backend/app/core/config.py
	backend/app/main.py
	backend/app/core/http.py
	frontend/src/components/Sidebar.tsx (suppression)
	frontend/src/components/TopBar.tsx (suppression)
	frontend/src/styles.css
