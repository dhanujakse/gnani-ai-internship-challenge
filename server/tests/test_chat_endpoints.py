import pathlib
import tempfile
import pytest

from sarvagyan_server.config import Settings
from sarvagyan_server.db import Database
from sarvagyan_server.main import Services, create_app
from tests.fakes import FakeRecognizer, FakeSynth, FakeTranslator


@pytest.fixture
def chat_app():
    tmp = pathlib.Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, auth_secret="test-secret-value", gnani_api_key="gnani-test-key", data_dir=str(tmp), demo_mode=True)
    db = Database(tmp / "test.db")
    rec, tr, synth = FakeRecognizer(), FakeTranslator(), FakeSynth()
    svc = Services(settings, db=db, recognizer=rec, translator=tr, synthesizer_factory=lambda: synth, voicemail_pace_s=0)
    app = create_app(svc)
    return svc, app, db


def test_username_validation(chat_app):
    svc, app, db = chat_app
    routes = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}

    chk = routes["/v1/users/check-username"](username="alice_123", s=svc)
    assert chk["available"] is True

    chk_bad = routes["/v1/users/check-username"](username="a!", s=svc)
    assert chk_bad["available"] is False


@pytest.mark.asyncio
async def test_user_search_and_chat_flow(chat_app):
    svc, app, db = chat_app
    routes = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}

    u1 = db.create_user("Alice", "alice@test.com", "h1", False, username="alice_123")
    u2 = db.create_user("Bob", "bob@test.com", "h2", False, username="bob_456")
    db.update_user(u2["id"], language="ta-IN")

    # Search
    res = routes["/v1/users/search"](q="bob", user=u1, s=svc)
    assert len(res["users"]) == 1
    assert res["users"][0]["username"] == "bob_456"

    # Direct conversation
    DirectChatIn = [arg for arg in routes["/v1/chat/direct"].__annotations__.values() if hasattr(arg, "model_fields")][0]
    c_res = routes["/v1/chat/direct"](body=DirectChatIn(username="bob_456"), user=u1, s=svc)
    cid = c_res["conversation"]["id"]

    get_messages_fn = next(r.endpoint for r in app.routes if r.path == "/v1/chat/conversations/{cid}/messages" and "GET" in r.methods)
    send_messages_fn = next(r.endpoint for r in app.routes if r.path == "/v1/chat/conversations/{cid}/messages" and "POST" in r.methods)

    # Send message
    SendMessageIn = [arg for arg in send_messages_fn.__annotations__.values() if hasattr(arg, "model_fields")][0]
    await send_messages_fn(cid=cid, body=SendMessageIn(text="Hello Bob! How are you?", language="en-IN"), user=u1, s=svc)

    # Bob retrieves messages -> translated into Tamil!
    msgs_res = await get_messages_fn(cid=cid, user=u2, s=svc)
    assert len(msgs_res["messages"]) == 1
    assert msgs_res["messages"][0]["original_text"] == "Hello Bob! How are you?"
    assert msgs_res["messages"][0]["translated_text"] == "[ta-IN] Hello Bob! How are you?"
    assert msgs_res["messages"][0]["is_translated"] is True

    # Group conversation
    GroupChatIn = [arg for arg in routes["/v1/chat/groups"].__annotations__.values() if hasattr(arg, "model_fields")][0]
    g_res = routes["/v1/chat/groups"](body=GroupChatIn(name="Alpha Team", member_ids=[u2["id"]]), user=u1, s=svc)
    gcid = g_res["conversation"]["id"]

    # List conversations
    list_res = routes["/v1/chat/conversations"](user=u1, s=svc)
    assert len(list_res["conversations"]) == 2
