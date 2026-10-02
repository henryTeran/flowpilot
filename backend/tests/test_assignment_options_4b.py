"""
Phase 4B: Queue Assignment Options — Deterministic Unit Tests

Test that AVAILABLE != ASSIGNABLE:
- Service duration must fit in available window
- Sorting is deterministic
- Tenant isolation enforced
- Complex scenarios with multiple employees
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.planning.models import ServiceSession
from app.modules.scheduling.service import _ensure_aware
from app.modules.scheduling.service_4b import assignment_options_for_ticket
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.ids import new_id


@pytest.fixture(scope="function")
def db_session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def now():
    """Current time (UTC aware)."""
    return datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def institute_id():
    return "inst-4b-001"


@pytest.fixture
def employee_available(db_session, institute_id):
    """Available employee."""
    emp = Employee(
        id="emp-4b-avail-001",
        institute_id=institute_id,
        first_name="Alice",
        status="available",
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture
def employee_busy_until_30min(db_session, institute_id, now):
    """Employee with session ending in 30 minutes."""
    emp = Employee(
        id="emp-4b-busy-30-001",
        institute_id=institute_id,
        first_name="Bob",
        status="available",
    )
    db_session.add(emp)
    db_session.commit()
    
    session = ServiceSession(
        id="sess-4b-30",
        ticket_line_id="line-4b-30",
        institute_id=institute_id,
        employee_id=emp.id,
        service_id="svc-001",
        start_time=now - timedelta(minutes=15),
        planned_end_time=now + timedelta(minutes=30),
        duration_minutes=45,
        status="in_progress",
    )
    db_session.add(session)
    db_session.commit()
    
    return emp


@pytest.fixture
def employee_pause(db_session, institute_id):
    """Employee with pause status."""
    emp = Employee(
        id="emp-4b-pause-001",
        institute_id=institute_id,
        first_name="Charlie",
        status="pause",
    )
    db_session.add(emp)
    db_session.commit()
    return emp


@pytest.fixture
def ticket_30min_service(db_session, institute_id):
    """Ticket with 30-minute service."""
    ticket = QueueTicket(
        id="ticket-4b-30min",
        institute_id=institute_id,
        ticket_number="T-001",
        status="waiting",
        arrival_time=datetime(2026, 10, 2, 13, 30, 0, tzinfo=timezone.utc),
        estimated_start_time=datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ticket)
    db_session.commit()
    
    line = TicketLine(
        id="line-4b-30min",
        ticket_id=ticket.id,
        service_id="svc-001",
        quantity=1,
        duration_minutes=30,
        revenue_category="care",
    )
    db_session.add(line)
    db_session.commit()
    
    return ticket


@pytest.fixture
def ticket_45min_service(db_session, institute_id):
    """Ticket with 45-minute service."""
    ticket = QueueTicket(
        id="ticket-4b-45min",
        institute_id=institute_id,
        ticket_number="T-002",
        status="waiting",
        arrival_time=datetime(2026, 10, 2, 13, 30, 0, tzinfo=timezone.utc),
        estimated_start_time=datetime(2026, 10, 2, 14, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add(ticket)
    db_session.commit()
    
    line = TicketLine(
        id="line-4b-45min",
        ticket_id=ticket.id,
        service_id="svc-002",
        quantity=1,
        duration_minutes=45,
        revenue_category="care",
    )
    db_session.add(line)
    db_session.commit()
    
    return ticket


# ============================================================================
# TESTS
# ============================================================================

class TestImmediatelyAssignable:
    """Test immediately assignable employee."""
    
    def test_available_employee_immediately_assignable(
        self, db_session, institute_id, employee_available, ticket_30min_service, now
    ):
        """Available employee with 30min service → immediately assignable."""
        options = assignment_options_for_ticket(db_session, institute_id, ticket_30min_service.id, now=now)
        
        assert len(options) >= 1
        alice = next((o for o in options if o.employee_id == employee_available.id), None)
        assert alice is not None
        assert alice.assignable is True
        assert alice.available_from == now
        assert alice.service_duration_minutes == 30
        assert alice.projected_end_time is not None


class TestServiceDurationFitting:
    """Test service duration fitting in available window."""
    
    def test_service_fits_before_future_appointment(self, db_session, institute_id, now):
        """Service 30min fits before appointment in 45min → assignable."""
        emp = Employee(
            id="emp-fits-001",
            institute_id=institute_id,
            first_name="David",
            status="available",
        )
        db_session.add(emp)
        db_session.commit()
        
        # Appointment in 45 minutes (ensure timezone aware)
        appt = Appointment(
            id="appt-fits-001",
            institute_id=institute_id,
            service_id="svc-001",
            employee_id=emp.id,
            customer_name="Customer",
            start_time=(now + timedelta(minutes=45)).replace(tzinfo=timezone.utc),
            end_time=(now + timedelta(minutes=75)).replace(tzinfo=timezone.utc),
            status="scheduled",
        )
        db_session.add(appt)
        db_session.commit()
        
        # Create 30min ticket (ensure UTC-aware datetimes)
        ticket = QueueTicket(
            id="ticket-fits-001",
            institute_id=institute_id,
            ticket_number="T-003",
            status="waiting",
            arrival_time=(now - timedelta(minutes=5)).replace(tzinfo=timezone.utc),
            estimated_start_time=now.replace(tzinfo=timezone.utc),
        )
        db_session.add(ticket)
        db_session.flush()
        
        line = TicketLine(
            id="line-fits-001",
            ticket_id=ticket.id,
            service_id="svc-001",
            quantity=1,
            duration_minutes=30,
            revenue_category="care",
        )
        db_session.add(line)
        db_session.commit()
        
        options = assignment_options_for_ticket(db_session, institute_id, ticket.id, now=now)
        
        david_option = next((o for o in options if o.employee_id == emp.id), None)
        assert david_option is not None
        assert david_option.assignable is True
        assert david_option.service_duration_minutes == 30
        # Projected end should be exactly at appointment start (or before)
        # Ensure both are timezone-aware for comparison
        projected_end = _ensure_aware(david_option.projected_end_time)
        appt_start = _ensure_aware(appt.start_time)
        assert projected_end <= appt_start
    
    
    def test_service_does_not_fit_before_future_appointment(self, db_session, institute_id, now):
        """Service 45min does NOT fit before appointment in 30min → NOT assignable."""
        emp = Employee(
            id="emp-no-fit-001",
            institute_id=institute_id,
            first_name="Eve",
            status="available",
        )
        db_session.add(emp)
        db_session.commit()
        
        # Appointment in 30 minutes
        appt = Appointment(
            id="appt-no-fit-001",
            institute_id=institute_id,
            service_id="svc-002",
            employee_id=emp.id,
            customer_name="Customer",
            start_time=now + timedelta(minutes=30),
            end_time=now + timedelta(minutes=60),
            status="scheduled",
        )
        db_session.add(appt)
        db_session.commit()
        
        # Create 45min ticket (ensure UTC-aware datetimes)
        ticket = QueueTicket(
            id="ticket-no-fit-001",
            institute_id=institute_id,
            ticket_number="T-004",
            status="waiting",
            arrival_time=(now - timedelta(minutes=5)).replace(tzinfo=timezone.utc),
            estimated_start_time=now.replace(tzinfo=timezone.utc),
        )
        db_session.add(ticket)
        db_session.flush()
        
        line = TicketLine(
            id="line-no-fit-001",
            ticket_id=ticket.id,
            service_id="svc-002",
            quantity=1,
            duration_minutes=45,
            revenue_category="care",
        )
        db_session.add(line)
        db_session.commit()
        
        options = assignment_options_for_ticket(db_session, institute_id, ticket.id, now=now)
        
        eve_option = next((o for o in options if o.employee_id == emp.id), None)
        assert eve_option is not None
        assert eve_option.assignable is False
        assert "doesn't fit" in eve_option.reason


class TestBusyEmployee:
    """Test busy employee (active session)."""
    
    def test_busy_employee_not_immediately_assignable(
        self, db_session, institute_id, employee_busy_until_30min, ticket_30min_service, now
    ):
        """Employee busy for 30min with 30min service → not immediately assignable."""
        options = assignment_options_for_ticket(
            db_session, institute_id, ticket_30min_service.id, now=now
        )
        
        bob_option = next((o for o in options if o.employee_id == employee_busy_until_30min.id), None)
        assert bob_option is not None
        assert bob_option.assignable is False
        # Should be assignable after 30min when session ends
        assert bob_option.available_from > now


class TestUnavailableEmployees:
    """Test pause and absent employees."""
    
    def test_pause_employee_not_assignable(
        self, db_session, institute_id, employee_pause, ticket_30min_service, now
    ):
        """Employee with pause status → not assignable."""
        options = assignment_options_for_ticket(
            db_session, institute_id, ticket_30min_service.id, now=now
        )
        
        charlie_option = next((o for o in options if o.employee_id == employee_pause.id), None)
        assert charlie_option is not None
        assert charlie_option.assignable is False


class TestTenantIsolation:
    """Test cross-institute denial."""
    
    def test_cross_institute_denial(self, db_session, employee_available, ticket_30min_service, now):
        """Ticket from one institute not visible to another."""
        other_institute = "inst-other-999"
        
        with pytest.raises(ValueError):
            assignment_options_for_ticket(db_session, other_institute, ticket_30min_service.id, now=now)


class TestDeterministicOrdering:
    """Test deterministic sorting."""
    
    def test_assignable_employees_first_then_by_time(self, db_session, institute_id, now):
        """Assignable employees first, then by available_from time."""
        # Create 3 employees:
        # 1. Available now (assignable)
        # 2. Busy for 20 min (not immediately assignable)
        # 3. Pause (never assignable)
        
        avail = Employee(id="emp-sort-1", institute_id=institute_id, first_name="Alice", status="available")
        busy = Employee(id="emp-sort-2", institute_id=institute_id, first_name="Bob", status="available")
        paused = Employee(id="emp-sort-3", institute_id=institute_id, first_name="Charlie", status="pause")
        
        db_session.add_all([avail, busy, paused])
        db_session.commit()
        
        # Add session to busy employee (ends in 20 min)
        session = ServiceSession(
            id="sess-sort-1",
            ticket_line_id="line-sort-1",
            institute_id=institute_id,
            employee_id=busy.id,
            service_id="svc-001",
            start_time=now - timedelta(minutes=10),
            planned_end_time=now + timedelta(minutes=20),
            duration_minutes=30,
            status="in_progress",
        )
        db_session.add(session)
        db_session.commit()
        
        # Create 30min ticket (ensure UTC-aware datetimes)
        ticket = QueueTicket(
            id="ticket-sort-1",
            institute_id=institute_id,
            ticket_number="T-005",
            status="waiting",
            arrival_time=(now - timedelta(minutes=5)).replace(tzinfo=timezone.utc),
            estimated_start_time=now.replace(tzinfo=timezone.utc),
        )
        db_session.add(ticket)
        db_session.flush()
        
        line = TicketLine(
            id="line-sort-1",
            ticket_id=ticket.id,
            service_id="svc-001",
            quantity=1,
            duration_minutes=30,
            revenue_category="care",
        )
        db_session.add(line)
        db_session.commit()
        
        options = assignment_options_for_ticket(db_session, institute_id, ticket.id, now=now)
        
        assert len(options) == 3
        # First should be assignable (Alice)
        assert options[0].assignable is True
        assert options[0].employee_id == avail.id
        # Next two are not assignable; should be ordered by available_from
        assert options[1].assignable is False
        assert options[2].assignable is False


class TestNonexistentTicket:
    """Test error handling."""
    
    def test_nonexistent_ticket_raises_not_found(self, db_session, institute_id, now):
        """Nonexistent ticket → ValueError exception."""
        with pytest.raises(ValueError):
            assignment_options_for_ticket(db_session, institute_id, "ticket-does-not-exist", now=now)


class TestMultiServiceTicket:
    """Test ticket with multiple services."""
    
    def test_multi_service_duration_cumulative(self, db_session, institute_id, now):
        """Ticket with 2 services (30+45min=75min) → uses cumulative duration."""
        emp = Employee(
            id="emp-multi-001",
            institute_id=institute_id,
            first_name="Frank",
            status="available",
        )
        db_session.add(emp)
        db_session.commit()
        
        # Appointment in 80 minutes (75min service + 5min buffer fits)
        appt = Appointment(
            id="appt-multi-001",
            institute_id=institute_id,
            service_id="svc-001",
            employee_id=emp.id,
            customer_name="Customer",
            start_time=now + timedelta(minutes=80),
            end_time=now + timedelta(minutes=110),
            status="scheduled",
        )
        db_session.add(appt)
        db_session.commit()
        
        # Create ticket with 2 services (ensure UTC-aware datetimes)
        ticket = QueueTicket(
            id="ticket-multi-001",
            institute_id=institute_id,
            ticket_number="T-006",
            status="waiting",
            arrival_time=(now - timedelta(minutes=5)).replace(tzinfo=timezone.utc),
            estimated_start_time=now.replace(tzinfo=timezone.utc),
        )
        db_session.add(ticket)
        db_session.flush()
        
        line1 = TicketLine(
            id="line-multi-1",
            ticket_id=ticket.id,
            service_id="svc-001",
            quantity=1,
            duration_minutes=30,
            revenue_category="care",
        )
        line2 = TicketLine(
            id="line-multi-2",
            ticket_id=ticket.id,
            service_id="svc-002",
            quantity=1,
            duration_minutes=45,
            revenue_category="care",
        )
        db_session.add_all([line1, line2])
        db_session.commit()
        
        options = assignment_options_for_ticket(db_session, institute_id, ticket.id, now=now)
        
        frank = next((o for o in options if o.employee_id == emp.id), None)
        assert frank is not None
        # Total duration is 75 minutes
        assert frank.service_duration_minutes == 75
        assert frank.assignable is True
        assert frank.projected_end_time == now + timedelta(minutes=75)


class TestAlreadyAssignedTicket:
    """Test assigned or completed tickets."""
    
    def test_assigned_ticket_still_returns_options(self, db_session, institute_id, now):
        """Even assigned tickets can show assignment options."""
        emp = Employee(
            id="emp-assign-test",
            institute_id=institute_id,
            first_name="Grace",
            status="available",
        )
        db_session.add(emp)
        db_session.commit()
        
        # Create assigned ticket (ensure UTC-aware datetimes)
        ticket = QueueTicket(
            id="ticket-assigned-001",
            institute_id=institute_id,
            ticket_number="T-007",
            status="assigned",  # Already assigned
            arrival_time=(now - timedelta(minutes=5)).replace(tzinfo=timezone.utc),
            estimated_start_time=now.replace(tzinfo=timezone.utc),
            assigned_employee_id=emp.id,
            assigned_at=now.replace(tzinfo=timezone.utc),
        )
        db_session.add(ticket)
        db_session.flush()
        
        line = TicketLine(
            id="line-assigned-001",
            ticket_id=ticket.id,
            service_id="svc-001",
            quantity=1,
            duration_minutes=30,
            revenue_category="care",
        )
        db_session.add(line)
        db_session.commit()
        
        # Should still return options
        options = assignment_options_for_ticket(db_session, institute_id, ticket.id, now=now)
        assert len(options) > 0
