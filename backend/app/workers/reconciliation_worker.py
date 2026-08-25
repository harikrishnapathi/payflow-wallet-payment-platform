import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.audit_service import create_audit_log
from app.services.reconciliation_service import (
    reconcile_all_wallets,
)

RECONCILIATION_INTERVAL_SECONDS = 300


def run_reconciliation(db: Session) -> tuple[int, int]:
    """
    Reconcile every wallet.

    Returns:
        (total_wallets, mismatched_wallets)
    """

    results = reconcile_all_wallets(db)

    mismatches = 0

    for result in results:
        if result.is_balanced:
            continue

        mismatches += 1

        create_audit_log(
            db,
            action="RECONCILIATION_MISMATCH",
            resource_type="WALLET",
            resource_id=result.wallet_id,
            metadata={
                "wallet_balance": int(result.wallet_balance),
                "ledger_balance": int(result.ledger_balance),
                "difference": int(result.difference),
                "detected_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )

        print(
            "[RECONCILIATION ALERT] "
            f"wallet={result.wallet_id} "
            f"wallet_balance={result.wallet_balance} "
            f"ledger_balance={result.ledger_balance} "
            f"difference={result.difference}"
        )

    db.commit()

    return len(results), mismatches


def run_once() -> tuple[int, int]:
    db: Session = SessionLocal()

    try:
        return run_reconciliation(db)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def run_worker() -> None:
    print(
        "PayFlow reconciliation worker started."
    )

    while True:
        try:
            total, mismatches = run_once()

            print(
                "[RECONCILIATION] "
                f"checked={total} "
                f"mismatches={mismatches}"
            )

            time.sleep(
                RECONCILIATION_INTERVAL_SECONDS
            )

        except KeyboardInterrupt:
            print(
                "PayFlow reconciliation worker stopped."
            )
            break

        except Exception as exc:
            print(
                f"[RECONCILIATION ERROR] {exc}"
            )

            time.sleep(30)


if __name__ == "__main__":
    run_worker()