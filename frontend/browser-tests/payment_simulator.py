"""Browser-fixture-only adapter; never represents a bank or verified settlement."""
from threading import Lock
from app.modules.payments.provider import ProviderResult, ProviderStatus


class PaymentSimulator:
    def __init__(self):
        self.results = {}
        self.lock = Lock()

    def _result(self, kind, request, reference, status):
        key = (kind, request.institute_id, request.ticket_id, request.idempotency_key)
        with self.lock:
            if key in self.results:
                original, original_reference, result = self.results[key]
                if original != request or original_reference != reference:
                    raise ValueError("Changed simulator replay terms")
                return result
            result = ProviderResult(reference, status, request.value)
            self.results[key] = (request, reference, result)
            if kind == "authorize":
                # Simulate an accepted operation whose first transport reply is lost.
                raise TimeoutError("SIMULATOR PRIVATE TRANSPORT DETAIL")
            return result

    def authorize(self, request):
        return self._result("authorize", request, "simulated-" + request.idempotency_key, ProviderStatus.AUTHORIZED)

    def capture(self, request, reference):
        return self._result("capture", request, reference, ProviderStatus.CAPTURED)

    def cancel(self, request, reference):
        return self._result("cancel", request, reference, ProviderStatus.CANCELLED)

    def refund(self, request, reference):
        return self._result("refund", request, reference, ProviderStatus.REFUNDED)

    def webhook(self, event):
        raise PermissionError("Simulator does not verify provider signatures")
