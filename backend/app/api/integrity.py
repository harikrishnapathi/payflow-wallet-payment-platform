import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.ledger_integrity_service import (
    run_integrity_check,
)

router = APIRouter(
    prefix="/admin/integrity",
    tags=["Financial Integrity"],
)


class IntegrityIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    message: str
    transaction_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None


class IntegrityReportResponse(BaseModel):
    healthy: bool
    total_issues: int
    issues: list[IntegrityIssueResponse]


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role.value != "ADMIN":
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )

    return user


@router.get(
    "",
    response_model=IntegrityReportResponse,
)
def get_integrity_report(
    _: User = Depends(require_admin),
    db=Depends(get_db),
):
    issues = run_integrity_check(db)

    return IntegrityReportResponse(
        healthy=len(issues) == 0,
        total_issues=len(issues),
        issues=[
            IntegrityIssueResponse(
                code=issue.code,
                message=issue.message,
                transaction_id=issue.transaction_id,
                wallet_id=issue.wallet_id,
            )
            for issue in issues
        ],
    )