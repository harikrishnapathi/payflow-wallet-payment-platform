import concurrent.futures
import uuid

import httpx


BASE_URL = "http://127.0.0.1:8000/api/v1"

USER_A_EMAIL = "concurrency-a2@example.com"
USER_A_PASSWORD = "Test@12345678"

USER_B_EMAIL = "concurrency-b2@example.com"
USER_B_PASSWORD = "Test@12345678"

TRANSFER_AMOUNT = 40000

def login(email: str, password: str) -> str:
    response = httpx.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    response.raise_for_status()

    return response.json()["access_token"]


def get_wallet(token: str) -> dict:
    response = httpx.get(
        f"{BASE_URL}/wallet/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    response.raise_for_status()

    return response.json()


def transfer(
    token: str,
    recipient_wallet_id: str,
    key: str,
) -> tuple[int, str]:

    response = httpx.post(
        f"{BASE_URL}/transactions/transfer",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": key,
        },
        json={
            "recipient_wallet_id": recipient_wallet_id,
            "amount": TRANSFER_AMOUNT,
            "description": "Concurrent transfer test",
        },
    )

    return response.status_code, response.text


def main():

    print("Logging in...")

    user_a_token = login(
        USER_A_EMAIL,
        USER_A_PASSWORD,
    )

    user_b_token = login(
        USER_B_EMAIL,
        USER_B_PASSWORD,
    )

    user_a_wallet = get_wallet(user_a_token)
    user_b_wallet = get_wallet(user_b_token)

    print()
    print("BEFORE")
    print("User A:", user_a_wallet["available_balance"])
    print("User B:", user_b_wallet["available_balance"])

    print()
    print("Sending two concurrent ₹400 transfers...")

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        futures = [
            executor.submit(
                transfer,
                user_a_token,
                user_b_wallet["id"],
                f"concurrency-{uuid.uuid4()}",
            )
            for _ in range(2)
        ]

        results = [
            future.result()
            for future in futures
        ]

    print()
    print("RESULTS")

    for index, result in enumerate(results, start=1):
        print(
            f"Request {index}: "
            f"HTTP {result[0]} -> {result[1]}"
        )

    user_a_wallet = get_wallet(user_a_token)
    user_b_wallet = get_wallet(user_b_token)

    print()
    print("AFTER")
    print("User A:", user_a_wallet["available_balance"])
    print("User B:", user_b_wallet["available_balance"])


if __name__ == "__main__":
    main()