from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet, WalletStatus


def search_recipients(
    db: Session,
    *,
    current_user_id,
    query: str,
    limit: int = 10,
):
    query = query.strip()

    if len(query) < 3:
        return []

    search_pattern = f"%{query}%"

    statement = (
        select(User, Wallet)
        .join(
            Wallet,
            Wallet.user_id == User.id,
        )
        .where(
            User.id != current_user_id,
            User.is_active.is_(True),
            Wallet.status == WalletStatus.ACTIVE,
            or_(
                User.email.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                (
                    User.first_name
                    + " "
                    + User.last_name
                ).ilike(search_pattern),
            ),
        )
        .order_by(
            User.first_name.asc(),
            User.last_name.asc(),
        )
        .limit(min(limit, 10))
    )

    return db.execute(statement).all()