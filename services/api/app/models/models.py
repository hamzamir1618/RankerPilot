import datetime
from sqlalchemy import (
    Integer, String, Boolean, Text, Numeric, BigInteger,
    ForeignKey, UniqueConstraint, Index, func, text,
    LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, CITEXT
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base
import enum
import uuid

# Enums
class RoleEnum(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    client_viewer = "client_viewer"

class IndustryEnum(str, enum.Enum):
    saas = "saas"
    local_service = "local_service"
    ecommerce = "ecommerce"
    publisher = "publisher"
    agency = "agency"

class AuditStatusEnum(str, enum.Enum):
    queued = "queued"
    crawling = "crawling"
    analyzing = "analyzing"
    done = "done"
    partial = "partial"
    failed = "failed"

class AuditModeEnum(str, enum.Enum):
    full = "full"
    single_page = "single_page"

class FindingStatusEnum(str, enum.Enum):
    pass_ = "pass"
    fail = "fail"
    warn = "warn"
    info = "info"

class FindingSeverityEnum(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

class FindingCategoryEnum(str, enum.Enum):
    content = "content"
    technical = "technical"
    onpage = "onpage"
    schema = "schema"
    performance = "performance"
    ai_readiness = "ai_readiness"
    images = "images"
    local = "local"

class FindingEffortEnum(str, enum.Enum):
    immediate = "immediate"
    one_week = "one_week"
    one_month = "one_month"
    backlog = "backlog"

class KeywordIntentEnum(str, enum.Enum):
    informational = "informational"
    commercial = "commercial"
    transactional = "transactional"
    navigational = "navigational"

class OAuthProviderEnum(str, enum.Enum):
    gsc = "gsc"
    ga4 = "ga4"
    gbp = "gbp"

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    theme_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme_primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    theme_agency_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    role: Mapped[RoleEnum] = mapped_column(String, nullable=False)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    domain: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[IndustryEnum | None] = mapped_column(String, nullable=True)
    gsc_connected: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint("org_id", "domain", name="uq_project_org_domain"),
    )

class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[AuditStatusEnum] = mapped_column(String, nullable=False)
    mode: Mapped[AuditModeEnum] = mapped_column(String, nullable=False)
    page_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    root_url: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    category_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class Page(Base):
    __tablename__ = "pages"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audits.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    lab_vitals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    links: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    headings: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    images: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    json_ld: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    internal_pagerank: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    
    __table_args__ = (
        Index("ix_pages_audit_id", "audit_id"),
    )

class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audits.id"), nullable=False)
    page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    agent: Mapped[str] = mapped_column(String(40), nullable=False)
    check_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[FindingStatusEnum] = mapped_column(String, nullable=False)
    severity: Mapped[FindingSeverityEnum | None] = mapped_column(String, nullable=True)
    category: Mapped[FindingCategoryEnum] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    fix_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    effort: Mapped[FindingEffortEnum | None] = mapped_column(String, nullable=True)
    
    __table_args__ = (
        Index("ix_findings_audit_id_severity", "audit_id", "severity"),
        UniqueConstraint("audit_id", "page_id", "check_id", name="uq_finding_audit_page_check"),
    )

class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class DriftEvent(Base):
    __tablename__ = "drift_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    rule: Mapped[str] = mapped_column(String(60), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    detected_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    acknowledged: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    
    __table_args__ = (
        Index("ix_drift_events_project_id_acknowledged", "project_id", "acknowledged"),
    )

class KeywordSet(Base):
    __tablename__ = "keyword_sets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class Keyword(Base):
    __tablename__ = "keywords"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("keyword_sets.id"), nullable=False)
    term: Mapped[str] = mapped_column(CITEXT, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    language: Mapped[str] = mapped_column(String(2), nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    intent: Mapped[KeywordIntentEnum | None] = mapped_column(String, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    is_tracked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    serp_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    refreshed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

class RankSnapshot(Base):
    __tablename__ = "rank_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    keyword_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("keywords.id"), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    serp_features: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    captured_at: Mapped[datetime.datetime] = mapped_column(primary_key=True, server_default=func.now())

    __table_args__ = (
        Index("ix_rank_snapshots_keyword_id_captured_at_desc", "keyword_id", "captured_at", postgresql_using="btree"),
        {"postgresql_partition_by": "RANGE (captured_at)"},
    )

class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(60), nullable=False)
    ref_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    
    __table_args__ = (
        Index("ix_credit_ledger_org_id", "org_id"),
    )

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[OAuthProviderEnum] = mapped_column(String, nullable=False)
    encrypted_refresh_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

class ProjectSchedule(Base):
    __tablename__ = "project_schedules"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    audit_cadence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rank_cadence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class SharedReportToken(Base):
    __tablename__ = "shared_report_tokens"
    token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audits.id"), nullable=False)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    events: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhooks.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

