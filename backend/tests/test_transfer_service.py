import uuid

import pytest

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntryType
from app.models.ledger_transaction import LedgerTransactionType
from app.models.user import User
from app.services.deposit_service import deposit
from app.services.transfer_service import transfer
from app.services.wallet_service import create_user_wallet


def create_test_user(db, prefix):
    user = User(
        id=uuid.uuid4(),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Transfer",
        last_name="Test",
    )

    db.add(user)
    db.flush()

    return user


def test_transfer_moves_money_between_wallets(db):
    sender_user = create_test_user(db, "sender")
    recipient_user = create_test_user(db, "recipient")

    sender = create_user_wallet(db, sender_user)
    recipient = create_user_wallet(db, recipient_user)

    system = LedgerAccount(
        account_type=LedgerAccountType.SYSTEM,
        currency="INR",
        wallet_id=None,
    )

    db.add(system)
    db.flush()

    deposit(
        db,
        wallet_id=sender.id,
        amount=10000,
        idempotency_key="transfer-funding-001",
        description="Transfer funding",
    )

    tx = transfer(
        db,
        sender_wallet_id=sender.id,
        recipient_wallet_id=recipient.id,
        amount=4000,
        idempotency_key="transfer-test-001",
        description="Test transfer",
    )

    db.flush()

    assert tx.transaction_type == LedgerTransactionType.TRANSFER
    assert tx.currency == "INR"
    assert tx.idempotency_key == "transfer-test-001"

    assert sender.available_balance == 6000
    assert recipient.available_balance == 4000

    assert len(tx.entries) == 2

    debit = next(
        entry
        for entry in tx.entries
        if entry.entry_type == LedgerEntryType.DEBIT
    )

    credit = next(
        entry
        for entry in tx.entries
        if entry.entry_type == LedgerEntryType.CREDIT
    )

    assert debit.amount == 4000
    assert credit.amount == 4000


def test_transfer_rejects_insufficient_balance_without_crediting_recipient(db):
    sender_user = create_test_user(db, "sender-insufficient")
    recipient_user = create_test_user(db, "recipient-insufficient")

    sender = create_user_wallet(db, sender_user)
    recipient = create_user_wallet(db, recipient_user)

    tx = None

    with pytest.raises(
        ValueError,
        match="Insufficient wallet balance",
    ):
        tx = transfer(
            db,
            sender_wallet_id=sender.id,
            recipient_wallet_id=recipient.id,
            amount=5000,
            idempotency_key="transfer-insufficient-001",
            description="Insufficient transfer",
        )

    assert tx is None
    assert sender.available_balance == 0
    assert recipient.available_balance == 0


def test_transfer_rejects_same_wallet(db):
    user = create_test_user(db, "same-wallet")

    wallet = create_user_wallet(
        db,
        user,
    )

    with pytest.raises(
        ValueError,
        match="Cannot transfer to the same wallet",
    ):
        transfer(
            db,
            sender_wallet_id=wallet.id,
            recipient_wallet_id=wallet.id,
            amount=1000,
            idempotency_key="transfer-same-wallet-001",
            description="Same wallet transfer",
        )


def test_transfer_idempotency_does_not_move_money_twice(db):
    sender_user = create_test_user(db, "sender-idempotency")
    recipient_user = create_test_user(db, "recipient-idempotency")

    sender = create_user_wallet(db, sender_user)
    recipient = create_user_wallet(db, recipient_user)

    system = LedgerAccount(
        account_type=LedgerAccountType.SYSTEM,
        currency="INR",
        wallet_id=None,
    )

    db.add(system)
    db.flush()

    deposit(
        db,
        wallet_id=sender.id,
        amount=10000,
        idempotency_key="transfer-idempotency-funding-001",
        description="Transfer funding",
    )

    first = transfer(
        db,
        sender_wallet_id=sender.id,
        recipient_wallet_id=recipient.id,
        amount=4000,
        idempotency_key="transfer-idempotency-001",
        description="Test transfer",
    )

    second = transfer(
        db,
        sender_wallet_id=sender.id,
        recipient_wallet_id=recipient.id,
        amount=4000,
        idempotency_key="transfer-idempotency-001",
        description="Test transfer",
    )

    assert first.id == second.id
    assert sender.available_balance == 6000
    assert recipient.available_balance == 4000