from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from app.models.models import (
    RoleEnum, IndustryEnum, AuditStatusEnum, AuditModeEnum,
    FindingStatusEnum, FindingSeverityEnum, FindingCategoryEnum, FindingEffortEnum,
    KeywordIntentEnum, OAuthProviderEnum
)

# Base Config
class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# Organization
class OrganizationBase(BaseModel):
    name: str = Field(description="The name of the organization.")

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase, ORMBase):
    id: uuid.UUID = Field(description="Unique identifier for the organization.")
    created_at: datetime = Field(description="Timestamp when the organization was created.")

# User
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: Optional[str] = None
    google_sub: Optional[str] = None

class UserResponse(UserBase, ORMBase):
    id: uuid.UUID
    created_at: datetime

# Membership
class MembershipBase(BaseModel):
    role: RoleEnum

class MembershipCreate(MembershipBase):
    user_id: uuid.UUID
    org_id: uuid.UUID

class MembershipResponse(MembershipBase, ORMBase):
    user_id: uuid.UUID
    org_id: uuid.UUID

# Project
class ProjectBase(BaseModel):
    domain: str = Field(description="The root domain of the project (e.g., example.com).")
    name: str = Field(description="The display name of the project.")
    industry: Optional[IndustryEnum] = Field(None, description="The industry category for this project.")
    gsc_connected: bool = Field(False, description="Whether Google Search Console is connected.")

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase, ORMBase):
    id: uuid.UUID = Field(description="Unique identifier for the project.")
    org_id: uuid.UUID = Field(description="The organization this project belongs to.")
    created_at: datetime = Field(description="Timestamp when the project was created.")

# Audit
class AuditBase(BaseModel):
    status: AuditStatusEnum = Field(description="The current execution status of the audit.")
    mode: AuditModeEnum = Field(description="The mode of the audit (full vs single_page).")
    page_limit: int = Field(description="The maximum number of pages to crawl.")
    root_url: str = Field(description="The entrypoint URL for the crawl.")
    score: Optional[float] = Field(None, description="The overall SEO score out of 100.")
    category_scores: Optional[Dict[str, Any]] = Field(None, description="Detailed score breakdown by category.")
    started_at: Optional[datetime] = Field(None, description="When the audit pipeline started.")
    finished_at: Optional[datetime] = Field(None, description="When the audit pipeline finished.")
    error: Optional[str] = Field(None, description="Any top-level error that halted the audit.")

class AuditCreate(AuditBase):
    project_id: uuid.UUID

class AuditResponse(AuditBase, ORMBase):
    id: uuid.UUID = Field(description="Unique identifier for the audit.")
    project_id: uuid.UUID = Field(description="The project this audit belongs to.")
    created_by: Optional[uuid.UUID] = Field(None, description="The user who initiated the audit.")

# Page
class PageBase(BaseModel):
    url: str = Field(description="The absolute URL of the page.")
    status_code: int = Field(description="The HTTP status code returned.")
    rendered: bool = Field(description="Whether JS rendering was used.")
    title: Optional[str] = Field(None, description="The parsed page title.")
    meta_description: Optional[str] = Field(None, description="The parsed meta description.")
    h1: Optional[List[str]] = Field(None, description="A list of H1 tags found.")
    word_count: Optional[int] = Field(None, description="The word count of the main content.")
    snapshot_key: Optional[str] = Field(None, description="S3 key for the raw HTML snapshot.")
    screenshot_key: Optional[str] = Field(None, description="S3 key for the visual screenshot.")
    lab_vitals: Optional[Dict[str, Any]] = Field(None, description="Core Web Vitals lab data.")
    content_text: Optional[str] = Field(None, description="The extracted readable text.")
    links: Optional[List[Dict[str, Any]]] = Field(None, description="Internal and external links.")
    headings: Optional[List[Dict[str, Any]]] = Field(None, description="The heading structure (H1-H6).")
    images: Optional[List[Dict[str, Any]]] = Field(None, description="Images found on the page.")
    json_ld: Optional[List[Dict[str, Any]]] = Field(None, description="Parsed JSON-LD structured data.")

class PageCreate(PageBase):
    audit_id: uuid.UUID

class PageResponse(PageBase, ORMBase):
    id: uuid.UUID
    audit_id: uuid.UUID
    fetched_at: datetime

# Finding
class FindingBase(BaseModel):
    agent: str = Field(description="The agent that generated this finding.")
    check_id: str = Field(description="The unique check identifier.")
    status: FindingStatusEnum = Field(description="Pass/Fail status.")
    severity: Optional[FindingSeverityEnum] = Field(None, description="Severity if it failed.")
    category: FindingCategoryEnum = Field(description="SEO Category of the finding.")
    title: str = Field(description="Human-readable title.")
    evidence: Optional[Dict[str, Any]] = Field(None, description="JSON evidence supporting the finding.")
    fix: Optional[str] = Field(None, description="Plain text instructions on how to fix.")
    fix_code: Optional[str] = Field(None, description="Code snippet for the fix.")
    effort: Optional[FindingEffortEnum] = Field(None, description="Estimated effort to fix.")

class FindingCreate(FindingBase):
    audit_id: uuid.UUID
    page_id: Optional[uuid.UUID] = None

class FindingResponse(FindingBase, ORMBase):
    id: uuid.UUID
    audit_id: uuid.UUID
    page_id: Optional[uuid.UUID] = None

# Baseline
class BaselineBase(BaseModel):
    page_url: str
    snapshot: Dict[str, Any]

class BaselineCreate(BaselineBase):
    project_id: uuid.UUID

class BaselineResponse(BaselineBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime

# DriftEvent
class DriftEventBase(BaseModel):
    page_url: str
    rule: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    acknowledged: bool = False

class DriftEventCreate(DriftEventBase):
    project_id: uuid.UUID

class DriftEventResponse(DriftEventBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    detected_at: datetime

# KeywordSet
class KeywordSetBase(BaseModel):
    name: str

class KeywordSetCreate(KeywordSetBase):
    project_id: uuid.UUID

class KeywordSetResponse(KeywordSetBase, ORMBase):
    id: uuid.UUID = Field(description="Unique ID of the keyword set.")
    project_id: uuid.UUID = Field(description="The project this set belongs to.")
    created_at: datetime = Field(description="Creation timestamp.")

# Keyword
class KeywordBase(BaseModel):
    term: str
    country: str = Field(..., max_length=2)
    language: str = Field(..., max_length=2)
    volume: Optional[int] = None
    difficulty: Optional[float] = None
    cpc: Optional[float] = None
    intent: Optional[KeywordIntentEnum] = None
    opportunity_score: Optional[float] = None
    serp_snapshot: Optional[Dict[str, Any]] = None

class KeywordCreate(KeywordBase):
    set_id: uuid.UUID

class KeywordResponse(KeywordBase, ORMBase):
    id: uuid.UUID
    set_id: uuid.UUID
    refreshed_at: Optional[datetime] = None

# RankSnapshot
class RankSnapshotBase(BaseModel):
    position: Optional[int] = None
    url: Optional[str] = None
    serp_features: Optional[List[str]] = None

class RankSnapshotCreate(RankSnapshotBase):
    keyword_id: uuid.UUID

class RankSnapshotResponse(RankSnapshotBase, ORMBase):
    id: int
    keyword_id: uuid.UUID
    captured_at: datetime

# CreditLedger
class CreditLedgerBase(BaseModel):
    delta: int
    reason: str
    ref_type: Optional[str] = None
    ref_id: Optional[uuid.UUID] = None

class CreditLedgerCreate(CreditLedgerBase):
    org_id: uuid.UUID

class CreditLedgerResponse(CreditLedgerBase, ORMBase):
    id: int
    org_id: uuid.UUID
    created_at: datetime

# OAuthToken
class OAuthTokenBase(BaseModel):
    provider: OAuthProviderEnum
    scopes: List[str]

class OAuthTokenCreate(OAuthTokenBase):
    user_id: uuid.UUID
    encrypted_refresh_token: bytes

class OAuthTokenResponse(OAuthTokenBase, ORMBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    # intentionally hiding encrypted_refresh_token from response

# ApiKey
class ApiKeyBase(BaseModel):
    prefix: str
    name: str

class ApiKeyCreate(ApiKeyBase):
    org_id: uuid.UUID
    hash: bytes

class ApiKeyResponse(ApiKeyBase, ORMBase):
    id: uuid.UUID = Field(description="Unique API key ID.")
    org_id: uuid.UUID = Field(description="The organization owning the key.")
    last_used_at: Optional[datetime] = Field(None, description="Last used timestamp.")
