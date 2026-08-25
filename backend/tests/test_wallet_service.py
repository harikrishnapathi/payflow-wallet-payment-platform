import uuid

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.user import User
from app.models.wallet import Wallet
from app.services.wallet_service import create_user_wallet


def test_create_user_wallet_creates_wallet_and_ledger_account(db):
    user = User(
    id=uuid.uuid4(),
    email=f"wallet-test-{uuid.uuid4()}@example.com",
    password_hash="test-password-hash",
    first_name="Test",
    last_name="User",
)

    db.add(user)
    db.flush()

    wallet = create_user_wallet(
        db,
        user,
    )

    db.flush()

    assert wallet.user_id == user.id
    assert wallet.currency == "INR"
    assert wallet.available_balance == 0
    assert wallet.pending_balance == 0

    account = db.query(LedgerAccount).filter(
        LedgerAccount.wallet_id == wallet.id
    ).one()

    assert account.account_type == LedgerAccountType.USER_WALLET
    assert account.currency == "INR"


def test_create_user_wallet_is_idempotent(db):
    user = User(
    id=uuid.uuid4(),
    email=f"wallet-idempotency-{uuid.uuid4()}@example.com",
    password_hash="test-password-hash",
    first_name="Test",
    last_name="User",
)

    db.add(user)
    db.flush()

    first_wallet = create_user_wallet(
        db,
        user,
    )

    second_wallet = create_user_wallet(
        db,
        user,
    )

    assert first_wallet.id == second_wallet.id

    accounts = db.query(LedgerAccount).filter(
        LedgerAccount.wallet_id == first_wallet.id
    ).all()

    assert len(accounts) == 1