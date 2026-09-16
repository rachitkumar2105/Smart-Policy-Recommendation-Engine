from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Policy(Base):
    __tablename__ = "policies"

    policy_id = Column(Integer, primary_key=True, autoincrement=True)
    policy_name = Column(String(100), nullable=False)
    policy_type = Column(String(30), nullable=False)  # HEALTH, AUTO, LIFE, PROPERTY
    description = Column(Text)
    base_premium = Column(Numeric(10, 2), nullable=False)
    min_age = Column(Integer, default=18)
    max_age = Column(Integer, default=100)
    min_income = Column(Numeric(12, 2), default=0)
    coverage_amount = Column(Numeric(15, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_policy_filter", "policy_type", "min_age", "max_age"),)


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    monthly_income = Column(Numeric(12, 2), nullable=False)
    occupation = Column(String(50))  # DESK_JOB, HAZARDOUS, UNEMPLOYED
    is_smoker = Column(Boolean, default=False)
    has_chronic_illness = Column(Boolean, default=False)
    owns_vehicle = Column(Boolean, default=False)
    vehicle_value = Column(Numeric(12, 2), default=0)
    owns_property = Column(Boolean, default=False)
    property_value = Column(Numeric(15, 2), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    recommendation_logs = relationship("RecommendationLog", back_populates="customer")


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.policy_id"), nullable=False)
    calculated_suitability_score = Column(Numeric(5, 2), nullable=False)
    final_premium_quoted = Column(Numeric(10, 2), nullable=False)
    recommendation_rank = Column(Integer, nullable=False)
    generated_reasoning = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="recommendation_logs")
    policy = relationship("Policy")

    __table_args__ = (Index("idx_logs_customer", "customer_id"),)
