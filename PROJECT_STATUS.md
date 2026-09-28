CURRENT_PHASE = PHASE 0
CURRENT_CHECKPOINT = 0D — Permissions workflow

CORE_WORKFLOW = PASS
TEST_ENVIRONMENT = PASS
START_SERVICE_GUARD = PROTECTED
FINISH_SERVICE_GUARD = PROTECTED
PAYMENT_GUARD = PROTECTED
WORKFLOW_TARGETED_TESTS = PASS
ANALYTICS_SINGLE_COUNT = PASS
CREATE_TICKET_IDEMPOTENCE = PASS
PERMISSIONS = PASS
refund = NOT_IMPLEMENTED

TESTS =
- Tests ciblés 0D:
	backend/tests/test_ticket_workflow.py
	backend/tests/test_planning_workflow.py
	backend/tests/test_checkout_workflow.py
- Exécution validée:
	py -3.13 -m pytest tests/test_ticket_workflow.py tests/test_planning_workflow.py tests/test_checkout_workflow.py -q
	Résultat: 25 passed, 2 warnings in 15.01s.
- Les warnings restent sur des dépréciations FastAPI `on_event`, sans régression fonctionnelle.

EVIDENCE =
- Les endpoints critiques appliquent la garde JWT existante via `require_ticket_manager`.
- Les workflows de test ont été alignés sur le contrat `Authorization: Bearer <token>` attendu par la permission 0D.
- Les cas autorisés, non autorisés et mauvais institut sont validés dans le suite ciblée.
- La logique 0C idempotence reste vérifiée et non perturbée.

BLOCKERS =
- Aucune régression 0D détectée dans le lot ciblé.
- Aucune étape supplémentaire hors périmètre de 0D avant validation de commit.

NEXT_STEP =
- Commit de la correction 0D: `fix(auth): enforce workflow permissions`.
- Ne pas avancer vers 0E ni vers des fonctionnalités hors périmètre.

WORKING_TREE =
- Changements vérifiés 0D:
	backend/app/core/permissions.py
	backend/app/modules/tickets/routes.py
	backend/app/modules/planning/routes.py
	backend/tests/test_ticket_workflow.py
	backend/tests/test_planning_workflow.py
	backend/tests/test_checkout_workflow.py
- Changements préexistants conservés hors scope:
	.env.example
	backend/app/core/config.py
	backend/app/main.py
	backend/app/core/http.py
	frontend/src/components/Sidebar.tsx (suppression)
	frontend/src/components/TopBar.tsx (suppression)
	frontend/src/styles.css
