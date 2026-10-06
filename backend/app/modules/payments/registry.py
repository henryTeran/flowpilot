"""Explicit server-owned payment bindings; no default or request-selected adapter."""
from types import MappingProxyType
from fastapi import HTTPException, Request
from app.modules.payments.dispatch import ProviderBinding
from app.database.session import SessionLocal


class PaymentRegistry:
    def __init__(self, bindings=()):
        rows = {}
        for binding in bindings:
            if not isinstance(binding, ProviderBinding) or binding.institute_id in rows:
                raise ValueError("One explicit payment binding per institute required")
            rows[binding.institute_id] = binding
        self._bindings = MappingProxyType(rows)

    def resolve(self, institute_id):
        binding = self._bindings.get(institute_id)
        if binding is None:
            raise HTTPException(503, "Prestataire de paiement non configure pour cet institut")
        return binding


def configured_binding(institute_id: str, request: Request):
    registry = getattr(request.app.state, "payment_registry", None)
    if not isinstance(registry, PaymentRegistry):
        raise HTTPException(503, "Configuration des paiements indisponible")
    return registry.resolve(institute_id)


def payment_sessions():
    # Dispatch owns short sessions and closes all SQL transactions before I/O.
    return SessionLocal
