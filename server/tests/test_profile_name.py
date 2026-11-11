def test_display_name_edit_propagates_and_is_secured(env) -> None:
    ta, ua = env.guest("Original Alice")
    tb, ub = env.guest("Bob")
    env.client.patch("/v1/me", json={"username": "alice_one"}, headers=env.auth(ta))
    env.client.patch("/v1/me", json={"username": "bob_one"}, headers=env.auth(tb))
    env.client.post("/v1/contacts", json={"username": "alice_one"}, headers=env.auth(tb))

    # Create a chat conversation and send a message BEFORE Alice renames
    conv = env.client.post("/v1/chat/direct", json={"username": "alice_one"}, headers=env.auth(tb)).json()["conversation"]
    env.client.post(f"/v1/chat/conversations/{conv['id']}/messages", json={"text": "Hello Bob"}, headers=env.auth(ta))

    # Validation checks: blank or >60 chars must return 422
    assert env.client.patch("/v1/me", json={"display_name": "   "}, headers=env.auth(ta)).status_code == 422
    assert env.client.patch("/v1/me", json={"display_name": "X" * 61}, headers=env.auth(ta)).status_code == 422

    # Unauthenticated edit fails
    assert env.client.patch("/v1/me", json={"display_name": "Hacker"}).status_code == 401

    # Alice updates her own name (with leading/trailing spaces -> trimmed)
    r = env.client.patch("/v1/me", json={"display_name": "  Dr. Alice Renamed  "}, headers=env.auth(ta))
    assert r.status_code == 200
    assert r.json()["display_name"] == "Dr. Alice Renamed"
    assert r.json()["username"] == "alice_one"  # username remains separate

    # Bob tries to pass another user's id; /v1/me only modifies Bob
    r_b = env.client.patch("/v1/me", json={"display_name": "Bob Updated", "id": ua["id"]}, headers=env.auth(tb))
    assert r_b.status_code == 200 and r_b.json()["id"] == ub["id"]
    assert env.client.get("/v1/me", headers=env.auth(ta)).json()["display_name"] == "Dr. Alice Renamed"

    # Updated name shows in contacts, user search, chat list, and even earlier chat messages!
    contacts_b = env.client.get("/v1/contacts", headers=env.auth(tb)).json()["contacts"]
    assert any(c["id"] == ua["id"] and c["name"] == "Dr. Alice Renamed" for c in contacts_b)

    search_b = env.client.get("/v1/users/search?q=alice_one", headers=env.auth(tb)).json()["users"]
    assert search_b[0]["display_name"] == "Dr. Alice Renamed"

    convs_b = env.client.get("/v1/chat/conversations", headers=env.auth(tb)).json()["conversations"]
    assert any(c["id"] == conv["id"] and c["name"] == "Dr. Alice Renamed" for c in convs_b)

    msgs_b = env.client.get(f"/v1/chat/conversations/{conv['id']}/messages", headers=env.auth(tb)).json()["messages"]
    assert msgs_b[0]["sender_name"] == "Dr. Alice Renamed"

