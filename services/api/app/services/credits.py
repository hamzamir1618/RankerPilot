import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.models.models import CreditLedger

logger = logging.getLogger(__name__)

class InsufficientCreditsError(Exception):
    def __init__(self, current_balance: int, required: int):
        self.current_balance = current_balance
        self.required = required
        self.shortfall = required - current_balance
        super().__init__(f"Insufficient credits. Need {required}, have {current_balance}.")

async def get_balance(db: AsyncSession, org_id: uuid.UUID | str) -> int:
    """
    Computes the total credit balance for an organization directly from the ledger.
    Leverages the index on org_id.
    """
    if isinstance(org_id, str):
        org_id = uuid.UUID(org_id)
        
    result = await db.scalar(select(func.sum(CreditLedger.delta)).where(CreditLedger.org_id == org_id))
    return int(result or 0)

def debit(
    db: AsyncSession, 
    org_id: uuid.UUID, 
    amount: int, 
    reason: str, 
    ref_type: Optional[str] = None, 
    ref_id: Optional[uuid.UUID] = None
) -> CreditLedger:
    """
    Records a negative ledger entry.
    Must be called within a transaction (and ideally while the org is locked).
    """
    if amount < 0:
        raise ValueError("Debit amount must be positive")
        
    entry = CreditLedger(
        org_id=org_id,
        delta=-amount,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id
    )
    db.add(entry)
    return entry

def credit(
    db: AsyncSession, 
    org_id: uuid.UUID, 
    amount: int, 
    reason: str, 
    ref_type: Optional[str] = None, 
    ref_id: Optional[uuid.UUID] = None
) -> CreditLedger:
    """
    Records a positive ledger entry.
    Must be called within a transaction.
    """
    if amount < 0:
        raise ValueError("Credit amount must be positive")
        
    entry = CreditLedger(
        org_id=org_id,
        delta=amount,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id
    )
    db.add(entry)
    return entry

async def refund_transaction(
    db: AsyncSession, 
    org_id: uuid.UUID, 
    ref_type: str, 
    ref_id: uuid.UUID, 
    reason: str
) -> Optional[CreditLedger]:
    """
    Finds the original debit for a given reference and issues a compensating credit.
    If multiple debits exist for the same reference, it refunds the sum of them.
    If a refund already happened (e.g. sum of all deltas for that ref >= 0), it won't over-refund.
    """
    # Find net delta for this reference
    query = select(func.sum(CreditLedger.delta)).where(
        CreditLedger.org_id == org_id,
        CreditLedger.ref_type == ref_type,
        CreditLedger.ref_id == ref_id
    )
    net_delta = await db.scalar(query)
    
    if net_delta is None or net_delta >= 0:
        logger.warning(f"Skipping refund for {ref_type}:{ref_id} - net delta is {net_delta} (not a debit)")
        return None
        
    # net_delta is negative. We issue a positive credit for the absolute value.
    refund_amount = abs(int(net_delta))
    
    refund_entry = credit(db, org_id, refund_amount, reason=reason, ref_type=ref_type, ref_id=ref_id)
    return refund_entry
