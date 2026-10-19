from tests.conftest import register_and_login


def test_todo_crud(client, auth):
    r = client.post("/api/todos", headers=auth, json={"text": "  write tests  ", "priority": "high"})
    assert r.status_code == 200
    todo = r.json()
    assert todo["text"] == "write tests" and todo["priority"] == "high" and todo["done"] is False

    r = client.patch(f"/api/todos/{todo['id']}", headers=auth, json={"done": True})
    assert r.json()["done"] is True

    r = client.get("/api/todos", headers=auth)
    assert [t["text"] for t in r.json()] == ["write tests"]

    r = client.delete("/api/todos/clear/done", headers=auth)
    assert r.json() == {"cleared": 1}
    assert client.get("/api/todos", headers=auth).json() == []


def test_todo_validation(client, auth):
    assert client.post("/api/todos", headers=auth, json={"text": "   "}).status_code == 400
    r = client.post("/api/todos", headers=auth, json={"text": "x", "priority": "urgent"})
    assert r.json()["priority"] == "medium"
    r = client.post("/api/todos", headers=auth, json={"text": "y" * 600})
    assert len(r.json()["text"]) == 500
    tid = r.json()["id"]
    assert client.patch(f"/api/todos/{tid}", headers=auth, json={"text": " "}).status_code == 400
    assert client.post("/api/todos", headers=auth, json={}).status_code == 422


def test_users_cannot_touch_each_others_todos(client, auth):
    tid = client.post("/api/todos", headers=auth, json={"text": "alice's"}).json()["id"]
    bob = register_and_login(client, "bob", "bob@example.com", "bob-password")
    assert client.get("/api/todos", headers=bob).json() == []
    assert client.patch(f"/api/todos/{tid}", headers=bob, json={"done": True}).status_code == 404
    assert client.delete(f"/api/todos/{tid}", headers=bob).status_code == 404
    assert client.get("/api/todos", headers=auth).json()[0]["done"] is False


def test_delete_single_todo(client, auth):
    tid = client.post("/api/todos", headers=auth, json={"text": "temp"}).json()["id"]
    assert client.delete(f"/api/todos/{tid}", headers=auth).json() == {"deleted": tid}
    assert client.delete(f"/api/todos/{tid}", headers=auth).status_code == 404
