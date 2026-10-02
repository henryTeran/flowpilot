# Phase 4 — Scheduling & Capacity Engine

**Kickoff Date**: 2026-10-02  
**Status**: ACTIVE  
**Predecessor**: Phase 3 (Walk-in Queue) ✅ CLOSED  
**Reference**: [docs/product/FLOWPILOT_MASTER_PLAN.md](FLOWPILOT_MASTER_PLAN.md#25-phase-4--scheduling--capacity-engine)

---

## Overview

Phase 4 builds the **Scheduling & Capacity Engine** — the core business logic combining walk-in queue (Phase 3), appointments (Phase 2), and availability constraints to produce:

- Next available slot for a given service
- Estimated wait time (duration-based)
- Queue priority (arrival time ordering)
- Collaborator availability (status-aware assignment)
- Resource availability (rooms, equipment)
- Assignment options (employee selection)

**Key Principle**: No inventory model yet — Phase 4 focuses on scheduling determinism and conflict-free assignment, not optimization (that comes later in Phase 16+).

---

## Phase 3 Handoff

### What Phase 3 Delivered

✅ Queue domain (anonymous walk-in arrivals, FIFO ordering, atomic lifecycle)  
✅ Ticket model (service_id, created_by_id, status transitions)  
✅ Idempotent ticket creation (fingerprint-based replay safety)  
✅ Employee status tracking (available, busy, pause, absent, offline)  
✅ Session lifecycle (planned → in_progress → completed)  
✅ Basic appointment model (exists, but no scheduling engine)  
✅ PostgreSQL runtime validated (Docker instance, migrations applied)  
✅ Concurrency-safe transactions (79 tests PASS)  
✅ Tenant isolation (all 25+ endpoints scoped by institute_id)  
✅ Responsive UX (< 15s walk-in creation, 1-2 click operations)  

### What Phase 4 Must Build

The scheduling layer that answers:
> "Given a walk-in ticket requesting service X now, which collaborator can handle it, when will they be available, and how long will the client wait?"

---

## Phase 4 Scope

### 4.A — Waiting Time Foundation (READY)

**Status**: Already implemented in Phase 3 (foundation layer exists)

**Current State**:
- ✅ Ticket `arrival_time` (FIFO base)
- ✅ Ticket `estimated_start_time` (calculated on assignment)
- ✅ Session `duration` tracking (minutes, from service definition)
- ✅ Employee status (available, busy, pause, absent, offline)

**What Remains**:
- [ ] Refine waiting time calculation: `estimated_start_time = max(now, employee.next_available_time)`
- [ ] Duration lookup: `service.standard_duration` + `session.extensions` (if any)
- [ ] Caching: Pre-compute next 50 slots in real-time without repeated DB scans

---

### 4.B — Availability Engine (CORE)

**Definition**: Given an employee, compute their **next N available slots** considering:
- Current status (available, busy, pause, absent, offline)
- Active session (if `status = in_progress`, employee unavailable until finish)
- Breaks (lunch, breaks — currently not modeled, can be appointments)
- Resource constraints (room availability, equipment, etc. — Phase 5)

**Implementation**:
```
AvailabilitySlot {
  start: datetime (e.g., 14:30 today)
  end: datetime (e.g., 14:45 today)
  employee_id: str
  ticket_id: Optional[str] (if pre-assigned)
  reason: str (available|in_progress_until|pause_until|break|unavailable)
}

availabilityEngine(employee_id, service_id, look_ahead_minutes=480) -> List[AvailabilitySlot]
```

**Database Queries** (required additions):
- Employee current status + end time of current session (if any)
- Next 5 appointments for this employee (with durations)
- Service standard duration
- Breaks (if modeled as calendar)

**Implementation Order**:
1. Query employee + active session
2. Query next appointments
3. Compute slot gaps
4. Return N slots with durations

---

### 4.C — Queue Assignment Engine (CORE)

**Definition**: When a ticket enters the queue (waiting status), immediately compute:
- Which collaborators can handle the service (skills match — Phase 5, skip for Phase 4)
- Who is available soonest
- Estimated wait time for each option

**Implementation**:
```
assignmentOptions(ticket_id) -> List[AssignmentOption] {
  AssignmentOption {
    employee_id: str
    estimated_start_time: datetime
    estimated_wait_minutes: int
    reason: str (e.g., "available now", "busy until 14:45")
  }
}

bestAssignment(ticket_id) -> Optional[AssignmentOption]
  // Returns first available (earliest estimated_start_time)
```

**Workflow** (on ticket creation):
1. POST /tickets → ticket.status = waiting
2. Trigger: availabilityEngine for all employees (pool)
3. Compute: assignmentOptions(ticket)
4. Display: Queue shows estimated start times per employee
5. Assignment: Operator clicks → PATCH /tickets/{id}/assign → lock employee + estimated_start_time

---

### 4.D — Conflict Handling (CORE)

**Scenarios**:

| Scenario | Current State | Phase 4 Behavior |
|----------|---------------|------------------|
| Employee becomes unavailable after ticket assigned | Ticket waits | Safe: Next available slot recalculated |
| Service duration extended (session continues) | Session continues | Cascading: Next tickets pushed back |
| Appointment appears during active session | (Rare — appointment booking checks) | Exception: Appointment auto-cancels or reschedules |
| Cancellation of waiting ticket | Removed from queue | Safe: No side effects |
| Cancellation of in-progress | Not supported yet | Phase 4: Mark as cancelled, free employee |

**Implementation**:
- Use atomic transactions (SQLAlchemy session.commit())
- Recalculate affected tickets on state change
- Broadcast WebSocket updates to dashboard in real-time

---

### 4.E — Service Duration Model (OPTIONAL — Phase 4)

**Current State**:
- Service has `name`, `category_id`, `price`
- No `standard_duration` field yet

**Decision**:
- [ ] Add `standard_duration: int` (minutes) to Service model
  - Migration: `ALTER TABLE service ADD COLUMN standard_duration INT DEFAULT 30;`
  - Seed: Default 30 min for all services initially
  - UI: Service edit → duration picker
- [ ] Session can extend duration: `session.duration_minutes` (current), `session.extensions` (future)

**For Phase 4**:
- Use service.standard_duration as the base wait calculation
- Extensions handled separately (operator can mark session as "extended" manually)

---

## Phase 4 Implementation Roadmap

### Checkpoint 4A: Waiting Time Foundation + Availability Engine

**Objective**: Calculate next available slot for any employee

**Tasks**:
1. Add `standard_duration` column to Service model (if not exists)
2. Create `AvailabilitySlot` data class in `backend/app/modules/scheduling/models.py`
3. Implement `availabilityEngine(employee_id, service_id, look_ahead_minutes)` in `backend/app/modules/scheduling/service.py`
4. Add endpoint: `GET /employees/{employee_id}/availability?service_id=...&look_ahead=480`
5. Write tests: 5+ scenarios (available now, busy, pause, absent, offline)
6. Gate: AVAILABILITY_ENGINE = PASS

**Files Created**:
```
backend/app/modules/scheduling/
  ├── __init__.py
  ├── models.py          (AvailabilitySlot, AvailabilityOption)
  ├── routes.py          (GET /employees/{id}/availability)
  ├── service.py         (availabilityEngine logic)
  └── repository.py      (DB queries for employee status, sessions, appointments)
```

**Test Coverage**:
```
tests/test_availability_engine_4a.py
  - test_employee_available_now
  - test_employee_busy_until
  - test_employee_offline
  - test_employee_pause
  - test_employee_unavailable_all_day
```

---

### Checkpoint 4B: Queue Assignment Options

**Objective**: Show all employees who can take a ticket + estimated wait time

**Tasks**:
1. Implement `assignmentOptions(ticket_id)` → calls availabilityEngine for all employees
2. Add endpoint: `GET /tickets/{ticket_id}/assignment_options`
3. Modify QueuePanel UI to show "Estimated start" for each employee option
4. Add operator workflow: Select employee → PATCH /tickets/{id}/assign → estimated_start_time locked
5. Gate: QUEUE_ASSIGNMENT = PASS

**Files Modified**:
```
backend/app/modules/tickets/service.py
  + assignmentOptions(ticket_id) -> List[AssignmentOption]

backend/app/modules/scheduling/routes.py
  + GET /tickets/{ticket_id}/assignment_options

frontend/src/components/QueuePanel.tsx
  - Display "Estimated start: 14:45" for each employee option
  - Show "Wait: 12 min" vs employee
```

**Test Coverage**:
```
tests/test_queue_assignment_4b.py
  - test_assignment_options_single_employee_available
  - test_assignment_options_multiple_employees
  - test_assignment_options_no_availability_today
  - test_assignment_changes_estimated_time_for_queue
```

---

### Checkpoint 4C: Conflict Detection & Resolution

**Objective**: Handle edge cases (employee unavailable, service extended, cancellations)

**Tasks**:
1. When employee status changes → recalculate queue estimated times (WebSocket broadcast)
2. When session duration extended → cascade updates to subsequent tickets
3. When ticket cancelled → free up the slot, recalculate queue
4. Add tests for race conditions: concurrent changes + cascade updates
5. Gate: CONFLICT_HANDLING = PASS

**Implementation**:
```python
# In tickets/service.py
async def extend_session(session_id: str, additional_minutes: int):
    session.duration_minutes += additional_minutes
    await cascade_update_queue(session.ticket_id)

async def cascade_update_queue(ticket_id: str):
    # Find all tickets after this one in queue for same institute
    # Recalculate each estimated_start_time
    # Broadcast WebSocket updates
```

**Test Coverage**:
```
tests/test_conflict_handling_4c.py
  - test_employee_status_change_updates_queue
  - test_session_extension_cascades_to_next_tickets
  - test_cancellation_recalculates_queue
  - test_concurrent_assign_and_status_change
  - test_cross_institute_isolation_under_scheduling
```

---

### Checkpoint 4D: Service Duration Model

**Objective**: Add standard_duration to Service; use in calculations

**Tasks**:
1. Alembic migration: Add `standard_duration INT DEFAULT 30` to service table
2. Pydantic schema: ServiceUpdate includes duration picker (5-120 min in 5-min increments)
3. Seed: All existing services → 30 min default
4. Service edit UI: Add duration field
5. Tests: Verify duration used in wait calculations
6. Gate: SERVICE_EXTENSION_IMPACT = PASS

**Migration**:
```python
# backend/migrations/versions/...
def upgrade():
    op.add_column('service', sa.Column('standard_duration', sa.Integer(), nullable=False, server_default='30'))

def downgrade():
    op.drop_column('service', 'standard_duration')
```

**Test Coverage**:
```
tests/test_service_duration_4d.py
  - test_create_service_with_custom_duration
  - test_duration_affects_estimated_start_time
  - test_duration_extension_shifts_queue
```

---

## Phase 4 Success Criteria

### Gates (All Must = PASS)

1. **FLOW_CAPACITY_ENGINE** ✓ Platform can compute next N available slots for any employee
2. **WAITING_TIME_ENGINE** ✓ Estimated wait time calculated correctly for each queue ticket
3. **AVAILABILITY_ENGINE** ✓ Real-time availability respects employee status + active sessions
4. **QUEUE_ASSIGNMENT** ✓ Operator can see assignment options + select best fit
5. **SERVICE_EXTENSION_IMPACT** ✓ Session extension cascades to dependent tickets
6. **CONFLICT_HANDLING** ✓ All edge cases handled (unavailability, cancellations, races)

### Test Requirements

- **Backend**: 100+ new tests covering scheduling logic, conflict scenarios, concurrency
- **Integration**: E2E test: walk-in arrives → assignment options shown → operator assigns → estimated time locked
- **Load**: 50+ concurrent tickets + scheduling operations; no race condition failures
- **Migration**: Alembic upgrade/downgrade validated on PostgreSQL

### Documentation

- `docs/architecture/PHASE4_SCHEDULING_ENGINE.md` — Technical deep-dive
- `docs/API_SCHEDULING.md` — Endpoints (availabilityEngine, assignmentOptions, etc.)
- Operator manual: "How to Assign Using Estimated Wait Times"

---

## Risk Assessment

### High Risk
- **Cascading Updates**: If session extension triggers many cascades, performance could degrade. Mitigation: Batch updates, async broadcast.
- **Concurrency**: Multiple operators assigning same ticket simultaneously. Mitigation: Database UNIQUE + atomic PATCH.

### Medium Risk
- **Skills Matching**: Currently skipped; Phase 5 will add complexity. Mitigation: Fallback to all-available-employees for Phase 4.
- **Resource Constraints**: Room/equipment not yet modeled. Mitigation: Assume unlimited resources for Phase 4; Phase 5 adds constraints.

### Low Risk
- **Appointment Conflicts**: Rare; can be handled as exceptions. Mitigation: Appointments checked before assignment.

---

## Phase 4 Integration Points

### Depends On (Must Be Ready)

- ✅ Phase 3: Queue domain + appointment model
- ✅ Phase 2: Employee status + tenant isolation
- ✅ Phase 1: PostgreSQL + Alembic migrations

### Prepares For (Phase 5+)

- Phase 5: Resources (rooms, equipment) + skills matching
- Phase 6: Hybrid booking engine (appointment scheduling)
- Phase 7: Client 360 (customer preferences, history)
- Phase 16: Scheduling optimizer (ML-based recommendations)

---

## Estimated Effort

- **Development**: 3–4 weeks (checkpoints 4A, 4B, 4C, 4D)
- **Testing**: 1–2 weeks (100+ tests, load validation)
- **Documentation**: 3–5 days
- **Deployment**: 2–3 days (production migration, validation)

**Total**: ~6–8 weeks from kickoff to Phase 5 entry

---

## Next Immediate Steps

1. **Code Review**: Review Phase 3 closure (commit 0da366f) for architecture patterns
2. **Model Design**: Define `AvailabilitySlot`, `AssignmentOption` schemas + DB fields
3. **Spike**: Implement availabilityEngine POC in `scheduling/service.py`
4. **Test Skeleton**: Create `tests/test_availability_engine_4a.py` with 5+ scenarios
5. **Checkpoint 4A Target**: End-of-sprint ready for vet

---

## Commands for Phase 4 Setup

### Create scheduling module structure

```bash
cd backend/app/modules
mkdir -p scheduling/{__init__.py,models.py,routes.py,service.py,repository.py}
```

### Alembic migration template

```bash
cd backend
alembic revision -m "Add standard_duration to Service; create AvailabilitySlot table"
```

### Test file template

```bash
cd backend/tests
touch test_availability_engine_4a.py
```

---

**Kickoff Owner**: Scheduling Engine Lead  
**Next Review**: After Checkpoint 4A (Availability Engine PASS)  
**Escalation**: Any gate failure blocks Phase 5 entry
