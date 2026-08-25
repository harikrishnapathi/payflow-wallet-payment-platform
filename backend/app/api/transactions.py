import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user
from app.db.session import get_db

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_transaction import LedgerTransaction
from app.models.user import User
from app.models.wallet import Wallet
from app.api.rate_limit import transaction_rate_limit

from app.schemas.transaction import (
    DepositRequest,
    LedgerEntryResponse,
    TransactionDetail,
    TransactionResponse,
    TransferRequest,
    WithdrawalRequest,
)

from app.services.deposit_service import deposit
from app.services.transfer_service import transfer
from app.services.withdrawal_service import withdraw


router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


# ============================================================
# WALLET
# ============================================================

def get_user_wallet(
    db: Session,
    user: User,
) -> Wallet:

    wallet = db.scalar(
        select(Wallet)
        .where(
            Wallet.user_id == user.id
        )
    )

    if wallet is None:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found.",
        )

    return wallet


# ============================================================
# TRANSACTION COMMIT HELPER
# ============================================================

def run_transaction(
    fn,
    db: Session,
):
    try:

        transaction = fn()

        db.commit()

        db.refresh(transaction)

        return transaction

    except HTTPException:

        db.rollback()

        raise

    except ValueError as exc:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:

        db.rollback()

        raise


# ============================================================
# TRANSACTION SERIALIZATION
# ============================================================

def serialize_transaction(
    transaction: LedgerTransaction,
    wallet_id: uuid.UUID,
) -> TransactionResponse:

    current_entry = None
    counterparty_entry = None

    # --------------------------------------------------------
    # Find the entry belonging to the current user's wallet.
    # --------------------------------------------------------

    for entry in transaction.entries:

        account = entry.account

        if (
            account is not None
            and account.wallet_id == wallet_id
        ):
            current_entry = entry
            break

    if current_entry is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "Transaction ledger entry "
                "could not be resolved."
            ),
        )

    # --------------------------------------------------------
    # Find the opposite ledger entry.
    #
    # For a transfer:
    #
    # sender wallet -> DEBIT
    # recipient wallet -> CREDIT
    # --------------------------------------------------------

    for entry in transaction.entries:

        if entry.id != current_entry.id:

            account = entry.account

            if account is not None:

                counterparty_entry = entry

                break

    # --------------------------------------------------------
    # Amount
    # --------------------------------------------------------

    amount = current_entry.amount

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    if current_entry.entry_type.value == "CREDIT":

        direction = "IN"

        is_incoming = True

    else:

        direction = "OUT"

        is_incoming = False

    # --------------------------------------------------------
    # Counterparty
    # --------------------------------------------------------

    counterparty_name = None
    counterparty_email = None
    counterparty_wallet_id = None

    # Counterparty only exists when the opposite
    # ledger account belongs to another wallet.
    if (
        counterparty_entry is not None
        and counterparty_entry.account is not None
    ):

        counterparty_wallet = (
            counterparty_entry
            .account
            .wallet
        )

        if counterparty_wallet is not None:

            counterparty_wallet_id = (
                counterparty_wallet.id
            )

            counterparty_user = (
                counterparty_wallet.user
            )

            if counterparty_user is not None:

                counterparty_name = (
                    f"{counterparty_user.first_name} "
                    f"{counterparty_user.last_name}"
                ).strip()

                counterparty_email = (
                    counterparty_user.email
                )

    # --------------------------------------------------------
    # Return API response
    # --------------------------------------------------------

    return TransactionResponse(
        id=transaction.id,

        transaction_type=(
            transaction.transaction_type.value
        ),

        reference_id=transaction.reference_id,

        currency=transaction.currency,

        description=transaction.description,

        idempotency_key=transaction.idempotency_key,

        created_at=transaction.created_at,

        amount=amount,

        entry_type=(
            current_entry.entry_type.value
        ),

        direction=direction,

        counterparty_name=counterparty_name,

        counterparty_email=counterparty_email,

        counterparty_wallet_id=counterparty_wallet_id,

        is_incoming=is_incoming,
    )


# ============================================================
# COMMON TRANSACTION QUERY
# ============================================================

def get_wallet_transactions_query(
    wallet_id: uuid.UUID,
):
    """
    Fetch transactions belonging to a wallet.

    selectinload loads:

        Transaction
            ↓
        Ledger Entries
            ↓
        Ledger Accounts
            ↓
        Wallet
            ↓
        User

    This allows the API to identify the sender/recipient
    without doing a separate query for every transaction.
    """

    return (
        select(LedgerTransaction)
        .join(
            LedgerTransaction.entries
        )
        .join(
            LedgerEntry.account
        )
        .where(
            LedgerAccount.wallet_id
            == wallet_id
        )
        .options(
            selectinload(
                LedgerTransaction.entries
            )
            .selectinload(
                LedgerEntry.account
            )
            .selectinload(
                LedgerAccount.wallet
            )
            .selectinload(
                Wallet.user
            )
        )
        .distinct()
        .order_by(
            LedgerTransaction.created_at.desc()
        )
    )


# ============================================================
# DEPOSIT
# ============================================================

@router.post(
    "/deposit",
    response_model=TransactionResponse,
)
def create_deposit(
    request: DepositRequest,
     _: None = Depends(transaction_rate_limit),

    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    wallet = get_user_wallet(
        db,
        current_user,
    )

    transaction = run_transaction(
        lambda: deposit(
            db=db,
            wallet_id=wallet.id,
            amount=request.amount,
            idempotency_key=idempotency_key,
            description=request.description,
        ),
        db,
    )

    return serialize_transaction(
        transaction,
        wallet.id,
    )


# ============================================================
# WITHDRAWAL
# ============================================================

@router.post(
    "/withdraw",
    response_model=TransactionResponse,
)
def create_withdrawal(
    request: WithdrawalRequest,
    _: None = Depends(transaction_rate_limit),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    wallet = get_user_wallet(
        db,
        current_user,
    )

    transaction = run_transaction(
        lambda: withdraw(
            db=db,
            wallet_id=wallet.id,
            amount=request.amount,
            idempotency_key=idempotency_key,
            description=request.description,
        ),
        db,
    )

    return serialize_transaction(
        transaction,
        wallet.id,
    )


# ============================================================
# TRANSFER
# ============================================================

@router.post(
    "/transfer",
    response_model=TransactionResponse,
)
def create_transfer(
    request: TransferRequest,
    _: None = Depends(transaction_rate_limit),

    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    wallet = get_user_wallet(
        db,
        current_user,
    )

    transaction = run_transaction(
        lambda: transfer(
            db=db,
            sender_wallet_id=wallet.id,
            recipient_wallet_id=(
                request.recipient_wallet_id
            ),
            amount=request.amount,
            idempotency_key=idempotency_key,
            description=request.description,
        ),
        db,
    )

    return serialize_transaction(
        transaction,
        wallet.id,
    )


# ============================================================
# LIST TRANSACTIONS
# ============================================================

@router.get(
    "",
    response_model=list[TransactionResponse],
)
def list_transactions(
    limit: int = 50,

    offset: int = 0,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    wallet = get_user_wallet(
        db,
        current_user,
    )

    limit = min(
        max(limit, 1),
        100,
    )

    offset = max(
        offset,
        0,
    )

    query = (
        get_wallet_transactions_query(
            wallet.id
        )
        .limit(limit)
        .offset(offset)
    )

    transactions = list(
        db.scalars(query).unique().all()
    )

    return [
        serialize_transaction(
            transaction,
            wallet.id,
        )
        for transaction in transactions
    ]


# ============================================================
# TRANSACTION DETAIL
# ============================================================

@router.get(
    "/{transaction_id}",
    response_model=TransactionDetail,
)
def transaction_detail(
    transaction_id: uuid.UUID,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    wallet = get_user_wallet(
        db,
        current_user,
    )

    query = (
        get_wallet_transactions_query(
            wallet.id
        )
        .where(
            LedgerTransaction.id
            == transaction_id
        )
    )

    transaction = db.scalars(
        query
    ).unique().first()

    if transaction is None:

        raise HTTPException(
            status_code=404,
            detail="Transaction not found.",
        )

    response = serialize_transaction(
        transaction,
        wallet.id,
    )

    return TransactionDetail(
        **response.model_dump(),
        entries=[
            LedgerEntryResponse.model_validate(
                entry
            )
            for entry in transaction.entries
        ],
    )