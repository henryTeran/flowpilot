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
- Redemption records a currency-matched payment allocation, preserves
  service prices/revenue and serialize debit, replay and reversal with checkout.
  Expiry disables usable credit without erasing recorded balance/history.
- New walk-in and completed-booking tickets snapshot the configured currency in
  a separate immutable fact. Legacy tickets retain unknown currency; an operator
  may explicitly confirm an unpaid checkout against current configuration with
  a reason and signed identity. Paid unknown history cannot be relabeled.
- Current catalog additions and member pricing require a confirmed matching
  ticket currency once configuration exists. A configuration change cannot
  rewrite an earlier ticket or convert its service prices. Original-price
  reversals remain historical corrections, not new catalog quotes.
- Refuse gift/mixed closure without an active recorded allocation. Full gift
  closure requires zero remaining due; mixed closure requires a positive remainder
  and its explicitly confirmed cash/card/cheque method. Snapshot both amounts,
  currency and signed actor in the same transaction as ticket closure. This is
  internal cashier confirmation, not proof of external provider settlement.
  Preserve same-intent recovery for already recorded historical paid
  tickets, without retroactively asserting that their payment was backed.

## Consequences and remaining work

Issuance/lookup is an API foundation, not the full gift-card gate. Currency-bearing
checkout facts, allocation/debit/reversal, gift/mixed closure and remaining due
are implemented at API scope. Manager/cashier configuration and confirmation interface
and payment-provider settlement still require implementation and verification.
Financial reports still require currency-separated aggregation before reporting
mixed or unknown historical units; existing untyped totals are not an FX report.
No exchange-rate conversion or cross-institute/BASE-JV credit pooling is introduced.
