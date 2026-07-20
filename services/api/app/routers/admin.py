import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.deps import get_db, get_current_user
from app.models.models import Organization, Membership, RoleEnum, User
from app.services.credits import credit, get_balance

router = APIRouter(prefix="/v1", tags=["admin"])

class TopUpRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount of credits to add")
    reason: str = Field(..., max_length=60)

@router.post("/organizations/{org_id}/credits/top-up")
async def top_up_credits(
    org_id: uuid.UUID,
    req: TopUpRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Check permissions: User must be an owner or admin of the target organization
    # Alternatively, a system-wide admin check could go here. We'll use the Membership role.
    membership = await db.scalar(
        select(Membership)
        .where(Membership.user_id == user.id)
        .where(Membership.org_id == org_id)
    )
    
    if not membership or membership.role not in (RoleEnum.owner, RoleEnum.admin):
        raise HTTPException(status_code=403, detail="Not enough permissions to top up credits")
        
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    # Apply top-up within a transaction
    try:
        await db.execute(select(Organization).where(Organization.id == org_id).with_for_update())
        
        entry = credit(db, org_id, req.amount, reason=req.reason, ref_type="manual_topup")
        await db.commit()
        
        new_balance = await get_balance(db, org_id)
    except Exception as e:
        await db.rollback()
        raise e
        
    return {
        "status": "success",
        "added": req.amount,
        "new_balance": new_balance,
        "transaction_id": entry.id
    }
