"""
Phase 4A: Availability Engine — Deterministic Unit Tests

Test all availability scenarios with strict determinism:
- Employee status states (available, busy, pause, absent, offline)
- Active sessions blocking availability
- Appointments blocking availability
- Tenant isolation
- Edge case timing
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.models import AvailabilityReason
from app.modules.scheduling.service import (
    availability_engine,
    availability_pool,
    next_available_time_for_employee,
    earliest_available_employee,
)
from app.shared.ids import new_id


# Test database setup (in-memory SQLite)
@pytest.fixture(scope="function")
def db_session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


# Fixtures for test data
@pytest.fixture
def now():
    """Current time (UTC aware)."""
    return datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def institute_id():
    return "inst-test-001"


@pytest.fixture
def employee_available(db_session, institute_id):
    """Employee with status=available, no sessions."""
    emp = Employee(
        id="emp-available-001",
        institute_id=institute_id,
        first_name="Alice",
        status="available",
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture
def employee_pause(db_session, institute_id):
    """Employee with status=pause."""
    emp = Employee(
        id="emp-pause-001",
        institute_id=institute_id,
        first_name="Bob",
        status="pause",
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture
def employee_absent(db_session, institute_id):
    """Employee with status=absent."""
    emp = Employee(
        id="emp-absent-001",
        institute_id=institute_id,
        first_name="Charlie",
        status="absent",
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture
def active_session(db_session, institute_id, employee_available, now):
    """Active service session blocking employee."""
    session = ServiceSession(
        id="sess-001",
        ticket_line_id="line-001",
        institute_id=institute_id,
        employee_id=employee_available.id,
        service_id="svc-001",
        start_time=now - timedelta(minutes=30),
        planned_end_time=now + timedelta(minutes=15),  # Ends in 15 min
        duration_minutes=45,
        status="in_progress",
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def appointment_now(db_session, institute_id, employee_available, now):
    """Appointment occupying employee right now."""
    appt = Appointment(
        id="appt-now-001",
        institute_id=institute_id,
        service_id="svc-001",
        employee_id=employee_available.id,
        customer_name="Customer A",
        start_time=now - timedelta(minutes=10),
        end_time=now + timedelta(minutes=20),  # Currently occupying
        status="in_progress",
    )
    db_session.add(appt)
    db_session.commit()
    return appt


@pytest.fixture
def appointment_future(db_session, institute_id, employee_available, now):
    """Appointment in future."""
    appt = Appointment(
        id="appt-future-001",
        institute_id=institute_id,
        service_id="svc-001",
        employee_id=employee_available.id,
        customer_name="Customer B",
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()
    return appt


# ============================================================================
# DETERMINISTIC TESTS
# ============================================================================

class TestAvailabilityEngine:
    """Test availability engine deterministic behavior."""
    
    def test_employee_available_now(self, db_session, institute_id, employee_available, now):
        """Employee with available status and no sessions → available_now."""
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        assert result.available is True
        assert result.current_slot is not None
        assert result.current_slot.reason == AvailabilityReason.AVAILABLE_NOW
        assert result.current_slot.available_from == now
        assert result.current_slot.blocking_session_id is None
    
    
    def test_employee_busy_with_active_session(
        self, db_session, institute_id, employee_available, active_session, now
    ):
        """Employee with active session → unavailable until session ends."""
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        assert result.available is False
        assert result.current_slot is not None
        assert result.current_slot.reason == AvailabilityReason.IN_PROGRESS_SESSION
        assert result.current_slot.blocking_session_id == active_session.id
        # Available time = session planned_end_time (ensure both timezone-aware for comparison)
        from datetime import timezone as tz
        result_time = result.current_slot.available_from
        session_time = active_session.planned_end_time
        if result_time.tzinfo is None:
            result_time = result_time.replace(tzinfo=tz.utc)
        if session_time.tzinfo is None:
            session_time = session_time.replace(tzinfo=tz.utc)
        assert result_time == session_time
    
    
    def test_employee_with_current_appointment(
        self, db_session, institute_id, employee_available, appointment_now, now
    ):
        """Employee with current appointment → unavailable until appointment ends."""
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        assert result.available is False
        assert result.current_slot is not None
        assert result.current_slot.reason == AvailabilityReason.UPCOMING_APPOINTMENT
        assert result.current_slot.blocking_appointment_id == appointment_now.id
        # Handle timezone-aware comparison
        from datetime import timezone as tz
        result_time = result.current_slot.available_from
        appt_time = appointment_now.end_time
        if result_time.tzinfo is None:
            result_time = result_time.replace(tzinfo=tz.utc)
        if appt_time.tzinfo is None:
            appt_time = appt_time.replace(tzinfo=tz.utc)
        assert result_time == appt_time
    
    
    def test_employee_pause_status(self, db_session, institute_id, employee_pause, now):
        """Employee with pause status → unavailable (blocked state)."""
        result = availability_engine(db_session, institute_id, employee_pause.id, now=now)
        
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.EMPLOYEE_PAUSE
        assert result.current_slot.available_until is None  # Unbounded
    
    
    def test_employee_absent_status(self, db_session, institute_id, employee_absent, now):
        """Employee with absent status → unavailable."""
        result = availability_engine(db_session, institute_id, employee_absent.id, now=now)
        
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.EMPLOYEE_ABSENT
    
    
    def test_employee_offline_status(self, db_session, institute_id, now):
        """Employee with offline status → unavailable."""
        offline_emp = Employee(
            id="emp-offline-001",
            institute_id=institute_id,
            first_name="Dave",
            status="offline",
        )
        db_session.add(offline_emp)
        db_session.commit()
        
        result = availability_engine(db_session, institute_id, offline_emp.id, now=now)
        
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.EMPLOYEE_OFFLINE
    
    
    def test_employee_available_with_future_appointment(
        self, db_session, institute_id, employee_available, appointment_future, now
    ):
        """Employee available now but has future appointment → available_until appointment start."""
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        assert result.available is True
        assert result.current_slot.reason == AvailabilityReason.AVAILABLE_NOW
        assert result.current_slot.available_from == now
        # Availability is bounded by appointment start time (handle timezone)
        from datetime import timezone as tz
        result_time = result.current_slot.available_until
        appt_time = appointment_future.start_time
        if result_time and result_time.tzinfo is None:
            result_time = result_time.replace(tzinfo=tz.utc)
        if appt_time.tzinfo is None:
            appt_time = appt_time.replace(tzinfo=tz.utc)
        assert result_time == appt_time
    
    
    def test_tenant_isolation_cross_institute_denied(
        self, db_session, employee_available, now
    ):
        """Employee from one institute should not be visible to another."""
        other_institute = "inst-other-999"
        
        result = availability_engine(db_session, other_institute, employee_available.id, now=now)
        
        # Engine should treat employee as not found / offline
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.EMPLOYEE_OFFLINE
    
    
    def test_nonexistent_employee(self, db_session, institute_id, now):
        """Nonexistent employee → unavailable."""
        result = availability_engine(db_session, institute_id, "emp-does-not-exist", now=now)
        
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.EMPLOYEE_OFFLINE


class TestAvailabilityPool:
    """Test pool queries for assignment options."""
    
    def test_availability_pool_orders_by_availability(
        self, db_session, institute_id, now
    ):
        """Pool should sort: available employees first, then by available_from time."""
        # Create 3 employees: 1 available now, 1 busy, 1 pause
        avail_now = Employee(
            id="pool-avail-001",
            institute_id=institute_id,
            first_name="Alice",
            status="available",
        )
        busy = Employee(
            id="pool-busy-001",
            institute_id=institute_id,
            first_name="Bob",
            status="available",
        )
        paused = Employee(
            id="pool-pause-001",
            institute_id=institute_id,
            first_name="Charlie",
            status="pause",
        )
        db_session.add_all([avail_now, busy, paused])
        db_session.commit()
        
        # Add active session to busy employee
        session = ServiceSession(
            id="sess-pool-001",
            ticket_line_id="line-001",
            institute_id=institute_id,
            employee_id=busy.id,
            service_id="svc-001",
            start_time=now - timedelta(minutes=10),
            planned_end_time=now + timedelta(minutes=5),  # Busy for 5 more min
            duration_minutes=15,
            status="in_progress",
        )
        db_session.add(session)
        db_session.commit()
        
        results = availability_pool(db_session, institute_id, now=now)
        
        assert len(results) == 3
        # First should be available now
        assert results[0].available is True
        assert results[0].employee_id == avail_now.id
        # The other two should not be available
        not_available_ids = {results[1].employee_id, results[2].employee_id}
        assert not_available_ids == {busy.id, paused.id}


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_session_ends_exactly_now(self, db_session, institute_id, employee_available, now):
        """An active session at its planned end remains blocked with unknown capacity."""
        # Session that ended exactly now (planned_end_time = now)
        session = ServiceSession(
            id="sess-edge-001",
            ticket_line_id="line-001",
            institute_id=institute_id,
            employee_id=employee_available.id,
            service_id="svc-001",
            start_time=now - timedelta(minutes=30),
            planned_end_time=now,  # Just ended
            duration_minutes=30,
            status="in_progress",
        )
        db_session.add(session)
        db_session.commit()
        
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        # Session blocks until it ends; if it ends at now, still blocks
        assert result.available is False
        assert result.current_slot.reason == AvailabilityReason.SESSION_OVERDUE
        assert result.current_slot.available_from is None
    
    
    def test_appointment_ends_exactly_now(self, db_session, institute_id, employee_available, now):
        """Appointment ending exactly at current time → employee available (no overlap)."""
        # Appointment that ends exactly now (end_time = now)
        appt = Appointment(
            id="appt-edge-001",
            institute_id=institute_id,
            service_id="svc-001",
            employee_id=employee_available.id,
            customer_name="Customer",
            start_time=now - timedelta(minutes=30),
            end_time=now,  # Just ended
            status="in_progress",
        )
        db_session.add(appt)
        db_session.commit()
        
        result = availability_engine(db_session, institute_id, employee_available.id, now=now)
        
        # Appointment overlap check: start_time <= now AND end_time > now
        # At now, end_time is NOT > now, so no overlap
        assert result.available is True
        assert result.current_slot.reason == AvailabilityReason.AVAILABLE_NOW
    
    
    def test_multiple_employees_same_institute(self, db_session, institute_id, now):
        """Multiple employees in same institute should be independent."""
        emp1 = Employee(
            id="emp-multi-001",
            institute_id=institute_id,
            first_name="Employee 1",
            status="available",
        )
        emp2 = Employee(
            id="emp-multi-002",
            institute_id=institute_id,
            first_name="Employee 2",
            status="pause",
        )
        db_session.add_all([emp1, emp2])
        db_session.commit()
        
        result1 = availability_engine(db_session, institute_id, emp1.id, now=now)
        result2 = availability_engine(db_session, institute_id, emp2.id, now=now)
        
        assert result1.available is True
        assert result2.available is False
        assert result1.current_slot.reason != result2.current_slot.reason


class TestHelperFunctions:
    """Test convenience functions."""
    
    def test_next_available_time_for_employee_available_now(
        self, db_session, institute_id, employee_available, now
    ):
        """If employee available now, returns now."""
        available_time = next_available_time_for_employee(
            db_session, institute_id, employee_available.id, now
        )
        assert available_time == now
    
    
    def test_next_available_time_for_employee_busy(
        self, db_session, institute_id, employee_available, active_session, now
    ):
        """If employee busy, returns when session ends."""
        available_time = next_available_time_for_employee(
            db_session, institute_id, employee_available.id, now
        )
        # Handle timezone comparison
        from datetime import timezone as tz
        result_time = available_time
        session_time = active_session.planned_end_time
        if result_time.tzinfo is None:
            result_time = result_time.replace(tzinfo=tz.utc)
        if session_time.tzinfo is None:
            session_time = session_time.replace(tzinfo=tz.utc)
        assert result_time == session_time
    
    
    def test_earliest_available_employee_in_pool(
        self, db_session, institute_id, now
    ):
        """Returns earliest available employee from pool."""
        emp1 = Employee(
            id="earliest-001",
            institute_id=institute_id,
            first_name="Alice",
            status="available",
        )
        emp2 = Employee(
            id="earliest-002",
            institute_id=institute_id,
            first_name="Bob",
            status="available",
        )
        db_session.add_all([emp1, emp2])
        db_session.commit()
        
        # Add session to emp1 (busy)
        session = ServiceSession(
            id="sess-earliest-001",
            ticket_line_id="line-001",
            institute_id=institute_id,
            employee_id=emp1.id,
            service_id="svc-001",
            start_time=now,
            planned_end_time=now + timedelta(minutes=30),
            duration_minutes=30,
            status="in_progress",
        )
        db_session.add(session)
        db_session.commit()
        
        result = earliest_available_employee(db_session, institute_id, now=now)
        
        # emp2 is available now; emp1 busy for 30 min
        # Should return emp2
        assert result is not None
        employee_id, available_time = result
        assert employee_id == emp2.id
        assert available_time == now


# ============================================================================
# INTEGRATION TEST: Full workflow
# ============================================================================

class TestFullWorkflow:
    """Test realistic workflow scenario."""
    
    def test_walk_in_ticket_assignment_scenario(self, db_session, institute_id, now):
        """Scenario: Walk-in arrives, show assignment options."""
        # Setup: 3 employees
        available = Employee(
            id="wf-avail-001",
            institute_id=institute_id,
            first_name="Available",
            status="available",
        )
        busy_30min = Employee(
            id="wf-busy-001",
            institute_id=institute_id,
            first_name="Busy30",
            status="available",
        )
        busy_60min = Employee(
            id="wf-busy-002",
            institute_id=institute_id,
            first_name="Busy60",
            status="available",
        )
        db_session.add_all([available, busy_30min, busy_60min])
        db_session.commit()
        
        # Add sessions
        session_30 = ServiceSession(
            id="wf-sess-30",
            ticket_line_id="wf-line-30",
            institute_id=institute_id,
            employee_id=busy_30min.id,
            service_id="svc-001",
            start_time=now,
            planned_end_time=now + timedelta(minutes=30),
            duration_minutes=30,
            status="in_progress",
        )
        session_60 = ServiceSession(
            id="wf-sess-60",
            ticket_line_id="wf-line-60",
            institute_id=institute_id,
            employee_id=busy_60min.id,
            service_id="svc-001",
            start_time=now,
            planned_end_time=now + timedelta(minutes=60),
            duration_minutes=60,
            status="in_progress",
        )
        db_session.add_all([session_30, session_60])
        db_session.commit()
        
        # Query availability pool
        results = availability_pool(db_session, institute_id, now=now)
        
        # Validate results
        assert len(results) == 3
        # Results should be sorted: available first, then by available_from
        assert results[0].available is True  # available employee
        assert results[0].employee_id == available.id
        
        assert results[1].available is False  # busy for 30 min
        assert results[1].employee_id == busy_30min.id
        
        assert results[2].available is False  # busy for 60 min
        assert results[2].employee_id == busy_60min.id
        
        # Check that the ordering is by availability time
        assert results[1].current_slot.available_from < results[2].current_slot.available_from
