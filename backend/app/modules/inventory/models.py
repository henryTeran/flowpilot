from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class StockReorderOriginal(Base):
    __tablename__ = "stock_reorder_originals"
    __table_args__ = (
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_reorder_replay"),
        Index("ix_stock_reorder_history", "institute_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    original: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class StockSupplier(Base):
    __tablename__ = "stock_suppliers"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_stock_supplier_owner"),
        UniqueConstraint("institute_id", "reference", name="uq_stock_supplier_reference"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_supplier_replay"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_stock_item_owner"),
        UniqueConstraint("institute_id", "sku", name="uq_stock_item_sku"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_item_replay"),
        CheckConstraint("category IN ('retail','cabine','consumable')", name="ck_stock_item_category"),
        CheckConstraint("unit IN ('ml','g','unit')", name="ck_stock_item_unit"),
        CheckConstraint("reorder_milli >= 0 AND reorder_milli <= 999999999999999", name="ck_stock_item_threshold"),
        CheckConstraint("unit != 'unit' OR reorder_milli % 1000 = 0", name="ck_stock_item_whole_threshold"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    reorder_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint("institute_id", "item_id", "id", name="uq_stock_movement_item_owner"),
        ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_movement_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_movement_replay"),
        CheckConstraint("kind IN ('receipt','adjustment','consumption')", name="ck_stock_movement_kind"),
        CheckConstraint("quantity_milli != 0 AND quantity_milli BETWEEN -999999999999999 AND 999999999999999", name="ck_stock_movement_quantity"),
        CheckConstraint("kind != 'receipt' OR quantity_milli > 0", name="ck_stock_receipt_positive"),
        ForeignKeyConstraint(["institute_id", "consumption_id"], ["stock_consumptions.institute_id", "stock_consumptions.id"], name="fk_stock_movement_consumption_owner"),
        UniqueConstraint("consumption_id", "item_id", name="uq_stock_consumption_item"),
        CheckConstraint("(kind = 'consumption' AND consumption_id IS NOT NULL AND quantity_milli < 0) OR (kind != 'consumption' AND consumption_id IS NULL)", name="ck_stock_consumption_movement"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    consumption_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockPurchaseOrder(Base):
    __tablename__ = "stock_purchase_orders"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_stock_order_owner"),
        UniqueConstraint("institute_id", "reference", name="uq_stock_order_reference"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_order_replay"),
        ForeignKeyConstraint(["institute_id", "supplier_id"], ["stock_suppliers.institute_id", "stock_suppliers.id"], name="fk_stock_order_supplier_owner"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(80), nullable=False)
    supplier_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    reference: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockPurchaseOrderLine(Base):
    __tablename__ = "stock_purchase_order_lines"
    __table_args__ = (
        UniqueConstraint("institute_id", "order_id", "item_id", "unit", name="uq_stock_order_line_owner"),
        ForeignKeyConstraint(["institute_id", "order_id"], ["stock_purchase_orders.institute_id", "stock_purchase_orders.id"], name="fk_stock_order_line_owner"),
        ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_order_line_item"),
        CheckConstraint("quantity_milli BETWEEN 1 AND 999999999999999", name="ck_stock_order_line_quantity"),
        CheckConstraint("unit IN ('ml','g','unit') AND (unit != 'unit' OR quantity_milli % 1000 = 0)", name="ck_stock_order_line_unit"),
    )
    order_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    item_sku: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)


class StockPurchaseReceipt(Base):
    __tablename__ = "stock_purchase_receipts"
    __table_args__ = (
        UniqueConstraint("institute_id", "order_id", "id", name="uq_stock_purchase_receipt_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_purchase_receipt_replay"),
        ForeignKeyConstraint(["institute_id", "order_id"], ["stock_purchase_orders.institute_id", "stock_purchase_orders.id"], name="fk_stock_purchase_receipt_order"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockPurchaseReceiptLine(Base):
    __tablename__ = "stock_purchase_receipt_lines"
    __table_args__ = (
        Index("ix_stock_purchase_receipt_line_order", "institute_id", "order_id", "item_id"),
        ForeignKeyConstraint(["institute_id", "order_id", "receipt_id"], ["stock_purchase_receipts.institute_id", "stock_purchase_receipts.order_id", "stock_purchase_receipts.id"], name="fk_stock_purchase_receipt_line_owner"),
        ForeignKeyConstraint(["institute_id", "order_id", "item_id", "unit"], ["stock_purchase_order_lines.institute_id", "stock_purchase_order_lines.order_id", "stock_purchase_order_lines.item_id", "stock_purchase_order_lines.unit"], name="fk_stock_purchase_receipt_order_line"),
        ForeignKeyConstraint(["institute_id", "item_id", "movement_id"], ["stock_movements.institute_id", "stock_movements.item_id", "stock_movements.id"], name="fk_stock_purchase_receipt_movement"),
        UniqueConstraint("movement_id", name="uq_stock_purchase_receipt_movement"),
        CheckConstraint("quantity_milli BETWEEN 1 AND 999999999999999", name="ck_stock_purchase_receipt_quantity"),
        CheckConstraint("unit IN ('ml','g','unit') AND (unit != 'unit' OR quantity_milli % 1000 = 0)", name="ck_stock_purchase_receipt_unit"),
    )
    receipt_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(80), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)
    movement_id: Mapped[str] = mapped_column(String(80), nullable=False)


class StockRecipe(Base):
    __tablename__ = "stock_recipes"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_stock_recipe_owner"),
        UniqueConstraint("institute_id", "service_id", "revision", name="uq_stock_recipe_revision"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_recipe_replay"),
        CheckConstraint("revision BETWEEN 1 AND 1000000000", name="ck_stock_recipe_revision"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockRecipeLine(Base):
    __tablename__ = "stock_recipe_lines"
    __table_args__ = (
        ForeignKeyConstraint(["institute_id", "recipe_id"], ["stock_recipes.institute_id", "stock_recipes.id"], name="fk_stock_recipe_line_owner"),
        ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_recipe_line_item"),
        CheckConstraint("quantity_milli BETWEEN 1 AND 999999999999999", name="ck_stock_recipe_line_quantity"),
        CheckConstraint("unit IN ('ml','g','unit')", name="ck_stock_recipe_line_unit"),
        CheckConstraint("unit != 'unit' OR quantity_milli % 1000 = 0", name="ck_stock_recipe_line_whole"),
    )
    recipe_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    quantity_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False)


class StockServiceBasis(Base):
    """Original recipe per performed line, captured atomically with actual start."""
    __tablename__ = "stock_service_bases"
    __table_args__ = (
        Index("uq_stock_basis_owner", "institute_id", "id", unique=True),
        ForeignKeyConstraint(["institute_id", "recipe_id"], ["stock_recipes.institute_id", "stock_recipes.id"], name="fk_stock_basis_recipe_owner"),
        ForeignKeyConstraint(["institute_id", "session_id"], ["service_sessions.institute_id", "service_sessions.id"], name="fk_stock_basis_session_owner"),
        ForeignKeyConstraint(["institute_id", "appointment_id"], ["appointments.institute_id", "appointments.id"], name="fk_stock_basis_appointment_owner"),
        UniqueConstraint("session_id", "ticket_line_id", name="uq_stock_basis_session_line"),
        UniqueConstraint("appointment_id", name="uq_stock_basis_appointment"),
        CheckConstraint("(session_id IS NOT NULL AND ticket_line_id IS NOT NULL AND appointment_id IS NULL) OR (session_id IS NULL AND ticket_line_id IS NULL AND appointment_id IS NOT NULL)", name="ck_stock_basis_source"),
        CheckConstraint("quantity > 0", name="ck_stock_basis_quantity"),
        CheckConstraint("(state = 'unconfigured' AND recipe_id IS NULL) OR (state IN ('enabled','disabled') AND recipe_id IS NOT NULL)", name="ck_stock_basis_configuration"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ticket_line_id: Mapped[str | None] = mapped_column(ForeignKey("ticket_lines.id"), nullable=True)
    appointment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recipe_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockConsumption(Base):
    __tablename__ = "stock_consumptions"
    __table_args__ = (
        UniqueConstraint("institute_id", "id", name="uq_stock_consumption_owner"),
        UniqueConstraint("basis_id", name="uq_stock_consumption_basis"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_consumption_replay"),
        ForeignKeyConstraint(["institute_id", "basis_id"], ["stock_service_bases.institute_id", "stock_service_bases.id"], name="fk_stock_consumption_basis_owner"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    basis_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
