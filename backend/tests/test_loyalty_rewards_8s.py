from test_ticket_workflow import _auth_headers, _bootstrap_reference_data


def test_reward_terms_are_explicit_scoped_immutable_and_replay_safe(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    manager = _auth_headers("responsable_institut", institute)
    operator = _auth_headers(institute_id=institute)
    path = f"/api/v1/loyalty/institutes/{institute}/rewards"
    payload = dict(name="Avantage aisselles", service_id=services[0]["id"],
                   points_cost=10, minimum_points=20, discount_amount="2.50", currency="CHF", idempotency_key="reward")
    assert client.get(path, headers=operator).json() == []
    assert client.post(path, headers=manager, json=payload).status_code == 400
    settings = f"/api/v1/gift-cards/institutes/{institute}/settings"
    assert client.put(settings, headers=manager, json={"currency": "CHF"}).status_code == 200
    assert client.post(path, headers=operator, json=payload).status_code == 403
    for headers in (_auth_headers(institute_id=None), _auth_headers(institute_id="other")):
        assert client.get(path, headers=headers).status_code == 403
    for changes in ({"points_cost": True}, {"points_cost": 0}, {"minimum_points": -1},
                    {"discount_amount": "2.501"}, {"currency": "USD"}):
        assert client.post(path, headers=manager, json={**payload, **changes}).status_code == 422
    for changes in ({"service_id": "missing"}, {"currency": "EUR"}):
        assert client.post(path, headers=manager, json={**payload, **changes}).status_code == 400
    result = client.post(path, headers=manager, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["actor_id"] == "test-user"
    assert client.post(path, headers=manager, json=payload).json() == result.json()
    assert client.post(path, headers=manager, json={**payload, "points_cost": 11}).status_code == 400
    assert client.get(path, headers=operator).json() == [result.json()]
    assert client.put(settings, headers=manager, json={"currency": "EUR"}).status_code == 400

    from pathlib import Path
    import pytest
    from alembic import command
    from alembic.config import Config
    import app.main as main_module
    from app.core.config import settings as configuration
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with monkeypatch.context() as patch:
        patch.setattr(configuration, "DATABASE_URL", main_module.engine.url.render_as_string(hide_password=False))
        command.stamp(config, "0acd45f2157a")
        with pytest.raises(RuntimeError, match="cannot preserve"):
            command.downgrade(config, "f9bc34e10469")


from test_postgres_scheduling_4d import postgres_flow, race


def test_reward_creation_serializes_with_currency_and_duplicate_intents(postgres_flow):
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.modules.loyalty.service import create_reward
    from app.modules.loyalty.schemas import RewardCreate
    from app.modules.loyalty.models import LoyaltyReward
    from app.modules.gift_cards.service import configure_currency
    from app.modules.gift_cards.models import GiftCardSettings
    engine, institute, employee, care = postgres_flow
    payload = RewardCreate(name="Reward", service_id=care, points_cost=10, minimum_points=0,
                           discount_amount="2.50", currency="CHF", idempotency_key="reward")
    with Session(engine) as db:
        configure_currency(db, institute, "CHF", "manager")
    def change_currency(db):
        from types import SimpleNamespace
        configure_currency(db, institute, "EUR", "manager")
        return SimpleNamespace(id="currency-change")
    results = race(engine, [lambda db: create_reward(db, institute, payload, "manager"),
                           change_currency])
    assert sorted(row[0] for row in results) == ["conflict", "ok"]
    with Session(engine) as db:
        rewards = list(db.scalars(select(LoyaltyReward)))
        assert db.get(GiftCardSettings, institute).currency == ("CHF" if rewards else "EUR")
        if not rewards:
            configure_currency(db, institute, "CHF", "manager")
    results = race(engine, [lambda db: create_reward(db, institute, payload, "manager"),
                           lambda db: create_reward(db, institute, payload, "manager")])
    assert all(row[0] == "ok" for row in results)
    assert results[0][1] == results[1][1]
    with Session(engine) as db:
        assert len(list(db.scalars(select(LoyaltyReward)))) == 1
