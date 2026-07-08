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
    name: str

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase, ORMBase):
    id: uuid.UUID
    created_at: datetime

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
    domain: str
    name: str
    industry: Optional[IndustryEnum] = None
    gsc_connected: bool = False

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase, ORMBase):
    id: uuid.UUID
    org_id: uuid.UUID
    created_at: datetime

# Audit
class AuditBase(BaseModel):
    status: AuditStatusEnum
    mode: AuditModeEnum
    page_limit: int
    root_url: str
    score: Optional[float] = None
    category_scores: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None

class AuditCreate(AuditBase):
    project_id: uuid.UUID

class AuditResponse(AuditBase, ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_by: uuid.UUID

# Page
class PageBase(BaseModel):
    url: str
    status_code: int
    rendered: bool
    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[List[str]] = None
    word_count: Optional[int] = None
    snapshot_key: Optional[str] = None
    screenshot_key: Optional[str] = None
    lab_vitals: Optional[Dict[str, Any]] = None

class PageCreate(PageBase):
    audit_id: uuid.UUID

class PageResponse(PageBase, ORMBase):
    id: uuid.UUID
    audit_id: uuid.UUID
    fetched_at: datetime

# Finding
class FindingBase(BaseModel):
    agent: str
    check_id: str
    status: FindingStatusEnum
    severity: Optional[FindingSeverityEnum] = None
    category: FindingCategoryEnum
    title: str
    evidence: Optional[Dict[str, Any]] = None
    fix: Optional[str] = None
    fix_code: Optional[str] = None
    effort: Optional[FindingEffortEnum] = None

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
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime

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
    id: uuid.UUID
    org_id: uuid.UUID
    last_used_at: Optional[datetime] = None
