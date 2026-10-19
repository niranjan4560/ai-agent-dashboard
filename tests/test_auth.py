import jwt

import auth as auth_mod
from tests.conftest import register_and_login


def test_register_login_and_me(client):
    headers = register_and_login(client)
    r = client.get("/api/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


def test_login_is_case_insensitive_on_email(client):
    register_and_login(client)
    r = client.post("/login", json={"email": "ALICE@Example.com", "password": "s3cret-pass"})
    assert r.status_code == 200 and "token" in r.json()


def test_duplicate_email_and_username_are_409(client):
    register_and_login(client)
    r = client.post("/register", json={"username": "bob", "email": "Alice@example.com", "password": "another-pass"})
    assert r.status_code == 409 and r.json()["error"] == "Email already exists"
    r = client.post("/register", json={"username": "alice", "email": "new@example.com", "password": "another-pass"})
    assert r.status_code == 409 and r.json()["error"] == "Username already taken"


def test_register_validation(client):
    cases = [
        {"username": "a", "email": "x@example.com", "password": "longenough"},
        {"username": "okname", "email": "not-an-email", "password": "longenough"},
        {"username": "okname", "email": "x@example.com", "password": "short"},
        {"username": "okname", "email": "x@example.com", "password": "x" * 73},
    ]
    for body in cases:
        r = client.post("/register", json=body)
        assert r.status_code == 422, body
        assert "error" in r.json()


def test_wrong_password_is_401(client):
    register_and_login(client)
    r = client.post("/login", json={"email": "alice@example.com", "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json() == {"error": "Invalid credentials"}


def test_password_is_hashed(client):
    register_and_login(client)
    from database import SessionLocal
    from models import User
    db = SessionLocal()
    try:
        user = db.query(User).first()
        assert user.password_hash.startswith("$2b$")
        assert "s3cret-pass" not in user.password_hash
    finally:
        db.close()


def test_token_has_expiry_and_expired_token_rejected(client):
    headers = register_and_login(client)
    token = headers["Authorization"].split()[1]
    assert "exp" in jwt.decode(token, options={"verify_signature": False})

    expired = jwt.encode({"user_id": 1, "exp": 1}, auth_mod.SECRET_KEY, algorithm="HS256")
    r = client.get("/api/todos", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_forged_token_rejected(client):
    register_and_login(client)
    forged = jwt.encode({"user_id": 1}, "attacker-controlled-key-of-sufficient-length!", algorithm="HS256")
    r = client.get("/api/todos", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_protected_routes_require_auth(client):
    for method, path in [("get", "/api/todos"), ("post", "/api/todos"), ("get", "/my-chats"),
                         ("get", "/api/me"), ("post", "/api/agent/chat"),
                         ("delete", "/api/todos/clear/done")]:
        kwargs = {"json": {"text": "x", "message": "x"}} if method == "post" else {}
        r = client.request(method.upper(), path, **kwargs)
        assert r.status_code == 401, (method, path, r.status_code)
        assert "error" in r.json()


def test_my_chats_only_returns_own_history(client):
    a = register_and_login(client)
    b = register_and_login(client, "bob", "bob@example.com", "bob-password")
    client.post("/api/agent/chat", headers=a, json={"message": "add alice secret task"})
    # The legacy ?user_id= parameter must not expose other users' chats
    r = client.get("/my-chats?user_id=1", headers=b)
    assert r.status_code == 200 and r.json() == []
    r = client.get("/my-chats", headers=a)
    assert len(r.json()) == 1


def test_legacy_passlib_hash_still_verifies():
    # Hash produced by passlib's bcrypt handler (format used before this change)
    import bcrypt
    legacy = bcrypt.hashpw(b"old-password", bcrypt.gensalt(rounds=12)).decode()
    assert auth_mod.verify_password("old-password", legacy)
    assert not auth_mod.verify_password("nope", legacy)
    assert not auth_mod.verify_password("x", "not-a-hash")
