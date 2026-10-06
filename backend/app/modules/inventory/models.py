from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


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
        ForeignKeyConstraint(["institute_id", "item_id"], ["stock_items.institute_id", "stock_items.id"], name="fk_stock_movement_owner"),
        UniqueConstraint("institute_id", "idempotency_key", name="uq_stock_movement_replay"),
        CheckConstraint("kind IN ('receipt','adjustment')", name="ck_stock_movement_kind"),
        CheckConstraint("quantity_milli != 0 AND quantity_milli BETWEEN -999999999999999 AND 999999999999999", name="ck_stock_movement_quantity"),
        CheckConstraint("kind != 'receipt' OR quantity_milli > 0", name="ck_stock_receipt_positive"),
    )
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    institute_id: Mapped[str] = mapped_column(ForeignKey("institutes.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_milli: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
