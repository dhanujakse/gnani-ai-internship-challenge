import hashlib
import pathlib
import re
import tempfile
import pytest

from sarvagyan_server.security import seal_phone_hash
from fastapi.testclient import TestClient

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


def normalize_phone_e164(raw: str, default_country_code: str = "+91") -> str | None:
    trimmed = raw.strip()
    if not trimmed:
        return None
    cleaned = re.sub(r"[^0-9+]", "", trimmed)
    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned[1:])
        return f"+{digits}" if 7 <= len(digits) <= 15 else None
    if cleaned.startswith("00"):
        digits = re.sub(r"\D", "", cleaned[2:])
        return f"+{digits}" if 7 <= len(digits) <= 15 else None
    cleaned = cleaned.replace("+", "")
    if cleaned.startswith("0") and len(cleaned) == 11:
        return f"{default_country_code}{cleaned[1:]}"
    if len(cleaned) == 10:
        return f"{default_country_code}{cleaned}"
    if len(cleaned) == 12 and cleaned.startswith("91"):
        return f"+{cleaned}"
    if 7 <= len(cleaned) <= 15:
        return f"{default_country_code}{cleaned}"
    return None


def sha256_hex(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()


@pytest.fixture
def contact_test_setup():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key", data_dir=str(tmp), demo_mode=True)
    db = Database(tmp / "test.db")
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    svc = Services(settings, db=db, recognizer=rec, translator=tr, synthesizer_factory=lambda: synth, voicemail_pace_s=0)
    app = create_app(svc)
    with TestClient(app) as client:
        yield client, db


def test_contact_sync_375_contacts(contact_test_setup):
    client, db = contact_test_setup

    # Register main user
    r_main = client.post("/v1/auth/register", json={
        "email": "main_user@example.com",
        "password": "Password123!",
        "display_name": "Main User",
        "username": "main_user",
    })
    assert r_main.status_code == 200
    main_token = r_main.json()["token"]
    headers = {"Authorization": f"Bearer {main_token}"}

    # Register 25 registered users with normalized phone hashes
    registered_uids = []
    registered_numbers = []
    for i in range(1, 26):
        phone_e164 = f"+9198765{i:05d}"
        p_hash = sha256_hex(phone_e164)
        registered_numbers.append(phone_e164)
        u = db.create_user(f"Friend {i}", f"friend{i}@example.com", "h", False, username=f"friend_{i}")
        db.update_user(u["id"], phone_hash=seal_phone_hash(p_hash, b"test-secret-value"))  # stored sealed, as the API does
        registered_uids.append(u["id"])

    # Generate 375 total contacts from phone
    # Contacts 1..25 are the registered users, in varied raw phone formats
    # Contacts 26..375 (350 contacts) are non-registered
    contacts = []
    total_raw_numbers = 0

    # 1. Registered contacts with varied formatting (spaces, trunk 0, missing country code, etc.)
    for i in range(1, 26):
        if i % 4 == 0:
            raw_phone = f"098765{i:05d}"  # 0 prefix
        elif i % 4 == 1:
            raw_phone = f"98765{i:05d}"   # 10 digits without prefix
        elif i % 4 == 2:
            raw_phone = f"+91 98765 {i:05d}"  # spaces with +91
        else:
            raw_phone = f"+91-98765-{i:05d}"  # dashes with +91
        contacts.append({"name": f"Contact Friend {i}", "numbers": [raw_phone]})
        total_raw_numbers += 1

    # 2. Non-registered contacts (350 contacts)
    for i in range(26, 376):
        # Add some multi-number contacts and a couple malformed ones to test reconciliation
        if i == 50:
            # 2 numbers
            raw_nums = [f"91234{i:05d}", f"091234{i:05d}"]
        elif i == 100:
            # malformed invalid number (<7 digits)
            raw_nums = ["123"]
        else:
            raw_nums = [f"91234{i:05d}"]
        contacts.append({"name": f"Phone Contact {i}", "numbers": raw_nums})
        total_raw_numbers += len(raw_nums)

    assert len(contacts) == 375
    assert total_raw_numbers == 376  # 375 contacts, one has 2 numbers

    # Normalization & Reconciliation
    contacts_read = len(contacts)
    numbers_read = total_raw_numbers
    normalized_numbers = 0
    failed_numbers = 0
    device_phone_contacts = []
    seen_hashes = set()

    for c in contacts:
        for num in c["numbers"]:
            norm = normalize_phone_e164(num, "+91")
            if norm:
                normalized_numbers += 1
                h = sha256_hex(norm)
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    device_phone_contacts.append({"name": c["name"], "number": norm, "hash": h})
            else:
                failed_numbers += 1

    # Verify reconciliation rule: numbers_read == normalized_numbers + failed_numbers
    assert numbers_read == normalized_numbers + failed_numbers, (
        f"Counts do not reconcile: {numbers_read} != {normalized_numbers} + {failed_numbers}"
    )
    # The malformed "123" is the 1 failed number
    assert failed_numbers == 1
    assert normalized_numbers == 375

    # Match in chunks of 100
    chunk_size = 100
    all_matched = []
    chunks = [device_phone_contacts[i:i + chunk_size] for i in range(0, len(device_phone_contacts), chunk_size)]

    synced_count = 0
    for chunk in chunks:
        hashes = [item["hash"] for item in chunk]
        res = client.post("/v1/contacts/match-phones", json={"phone_hashes": hashes}, headers=headers)
        assert res.status_code == 200, res.text
        matches = res.json()["matches"]
        all_matched.extend(matches)
        synced_count += len(chunk)

    assert synced_count == len(device_phone_contacts)

    # Exactly the 25 registered users must be matched!
    matched_ids = [m["id"] for m in all_matched]
    assert len(matched_ids) == 25
    for uid in registered_uids:
        assert uid in matched_ids

    # Unmatched contacts should be total unique - matched
    unmatched_count = len(device_phone_contacts) - len(all_matched)
    assert unmatched_count == len(device_phone_contacts) - 25

