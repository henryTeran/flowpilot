CURRENT_PHASE = PHASE 0
CURRENT_CHECKPOINT = 0C — Idempotence création de ticket

CORE_WORKFLOW = PASS
TEST_ENVIRONMENT = PASS
START_SERVICE_GUARD = PASS
FINISH_SERVICE_GUARD = PASS
PAYMENT_GUARD = PASS
WORKFLOW_TARGETED_TESTS = PASS
ANALYTICS_SINGLE_COUNT = PASS
CREATE_TICKET_IDEMPOTENCE = PASS
PERMISSIONS = BLOCKED
refund = NOT_IMPLEMENTED

TESTS =
- Tests ciblés 0C:
	backend/tests/test_ticket_workflow.py
- Exécution validée:
	py -3.13 -m pytest tests/test_ticket_workflow.py -q
	Résultat: 6 passed, 2 warnings.

EVIDENCE =
- Même idempotency_key = même ticket retourné.
- Clés différentes = tickets distincts.
- Mécanisme minimal robuste : idempotency_key + contrainte DB unique (institute_id, idempotency_key).
- Permissions hors scope: non touché.

BLOCKERS =
- Aucune régression 0C détectée.
- Permissions / refund / AI restent hors périmètre.

NEXT_STEP =
- Aucune étape supplémentaire : fin de la phase 0C.

WORKING_TREE =
- Changements préexistants préservés hors scope 0C:
	.env.example
	backend/app/core/config.py
	backend/app/main.py
	backend/app/core/http.py
	frontend/src/components/Sidebar.tsx (suppression)
	frontend/src/components/TopBar.tsx (suppression)
	frontend/src/styles.css
