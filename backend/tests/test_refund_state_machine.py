from app.models.refund import RefundStatus
from app.services.refund_state_machine import ALLOWED_TRANSITIONS


def test_created_can_move_to_processing():
    assert (
        RefundStatus.PROCESSING
        in ALLOWED_TRANSITIONS[RefundStatus.CREATED]
    )


def test_processing_can_succeed():
    assert (
        RefundStatus.SUCCEEDED
        in ALLOWED_TRANSITIONS[RefundStatus.PROCESSING]
    )


def test_processing_can_fail():
    assert (
        RefundStatus.FAILED
        in ALLOWED_TRANSITIONS[RefundStatus.PROCESSING]
    )


def test_failed_is_terminal():
    assert ALLOWED_TRANSITIONS[RefundStatus.FAILED] == set()


def test_succeeded_is_terminal():
    assert ALLOWED_TRANSITIONS[RefundStatus.SUCCEEDED] == set()