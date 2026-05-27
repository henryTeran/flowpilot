from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    countries = relationship("Country", back_populates="company")


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    company = relationship("Company", back_populates="countries")
    regions = relationship("Region", back_populates="country")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    country_id: Mapped[str] = mapped_column(ForeignKey("countries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    country = relationship("Country", back_populates="regions")
    institutes = relationship("Institute", back_populates="region")


class Institute(Base):
    __tablename__ = "institutes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Zurich", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    region = relationship("Region", back_populates="institutes")
