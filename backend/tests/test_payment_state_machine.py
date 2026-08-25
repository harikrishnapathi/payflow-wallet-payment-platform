
from app.models.payment import PaymentStatus
from app.services.payment_state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidPaymentTransition,
)


def test_created_can_move_to_pending():
    assert (
        PaymentStatus.PENDING
        in ALLOWED_TRANSITIONS[PaymentStatus.CREATED]
    )


def test_pending_can_move_to_processing():
    assert (
        PaymentStatus.PROCESSING
        in ALLOWED_TRANSITIONS[PaymentStatus.PENDING]
    )


def test_processing_can_succeed():
    assert (
        PaymentStatus.SUCCEEDED
        in ALLOWED_TRANSITIONS[PaymentStatus.PROCESSING]
    )


def test_processing_can_fail():
    assert (
        PaymentStatus.FAILED
        in ALLOWED_TRANSITIONS[PaymentStatus.PROCESSING]
    )


def test_succeeded_can_become_refundable():
    assert (
        PaymentStatus.REFUNDABLE
        in ALLOWED_TRANSITIONS[PaymentStatus.SUCCEEDED]
    )


def test_refundable_can_become_refunded():
    assert (
        PaymentStatus.REFUNDED
        in ALLOWED_TRANSITIONS[PaymentStatus.REFUNDABLE]
    )


def test_failed_is_terminal():
    assert ALLOWED_TRANSITIONS[PaymentStatus.FAILED] == set()


def test_refunded_is_terminal():
    assert ALLOWED_TRANSITIONS[PaymentStatus.REFUNDED] == set()