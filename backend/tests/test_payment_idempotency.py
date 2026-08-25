from app.services.transaction_service import fingerprint


def test_payment_fingerprint_is_deterministic():
    wallet_id = "0aa4d397-6cd8-47b5-ab65-50e10bbfd5c3"

    first = fingerprint(
        transaction_type="PAYMENT",
        amount=5000,
        currency="INR",
        source_wallet_id=wallet_id,
        description=None,
    )

    second = fingerprint(
        transaction_type="PAYMENT",
        amount=5000,
        currency="INR",
        source_wallet_id=wallet_id,
        description=None,
    )

    assert first == second


def test_payment_fingerprint_changes_when_amount_changes():
    wallet_id = "0aa4d397-6cd8-47b5-ab65-50e10bbfd5c3"

    first = fingerprint(
        transaction_type="PAYMENT",
        amount=5000,
        currency="INR",
        source_wallet_id=wallet_id,
        description=None,
    )

    second = fingerprint(
        transaction_type="PAYMENT",
        amount=6000,
        currency="INR",
        source_wallet_id=wallet_id,
        description=None,
    )

    assert first != second


def test_payment_fingerprint_changes_when_wallet_changes():
    first = fingerprint(
        transaction_type="PAYMENT",
        amount=5000,
        currency="INR",
        source_wallet_id="wallet-a",
        description=None,
    )

    second = fingerprint(
        transaction_type="PAYMENT",
        amount=5000,
        currency="INR",
        source_wallet_id="wallet-b",
        description=None,
    )

    assert first != second