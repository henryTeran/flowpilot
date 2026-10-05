# ADR-006 — Gift-card credit and payment allocation

Date: 2026-10-05
Status: accepted; issuance implemented, checkout allocation remains next.

## Evidence

Phase 8 requires gift-card issuance, use, expiry and balance. Existing ticket lines
and totals contain monetary amounts without currency. The checkout API accepts
`carte_cadeau`/`mixte` labels without a gift-card balance or payment allocation.
Those labels alone cannot establish that stored value paid an invoice.

## Decision

- Keep the modular monolith and the existing institute transaction lock.
- Configure gift-card currency explicitly per institute (CHF/EUR initially). Do
  not infer it from country, browser locale or an AI suggestion. Once a card is
  issued, its institute's gift-card currency cannot change.
- Manager issuance grants stored value with a mandatory reason, signed actor,
  precise decimal amount, validity snapshot and replay fingerprint. It does not
  claim a paid sale or external settlement. Recipient linkage is optional; cards
  are bearer instruments usable only within the issuing institute.
- Codes use cryptographically random tokens. Only manager issuance/replay returns
  the code; operator lookup accepts it in a POST body and does not echo it. Codes
  must not be added to URLs, request audit metadata or ordinary list responses.
- Future redemption must record a currency-matched payment allocation, preserve
  service prices/revenue and serialize debit, replay and reversal with checkout.
  Expiry disables usable credit without erasing recorded balance/history.
- Until that allocation exists, refuse new checkout closure with gift/mixed
  labels. Preserve same-intent recovery for already recorded historical paid
  tickets, without retroactively asserting that their payment was backed.

## Consequences and remaining work

Issuance/lookup is an API foundation, not the full gift-card gate. Currency-bearing
checkout facts, allocation/debit/reversal, remaining due, manager/cashier interface
and payment-provider settlement still require implementation and verification.
No exchange-rate conversion or cross-institute/BASE-JV credit pooling is introduced.
