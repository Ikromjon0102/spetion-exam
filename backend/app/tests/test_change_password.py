from app.tests.factories import make_teacher


def _login(client, username, password):
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_change_password_success_and_old_password_stops_working(client, db_session):
    make_teacher(db_session, username="pw_test")
    db_session.commit()

    token = _login(client, "pw_test", "secret123")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "secret123", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    old_login = client.post("/api/v1/auth/login", json={"username": "pw_test", "password": "secret123"})
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login", json={"username": "pw_test", "password": "newpass456"})
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client, db_session):
    make_teacher(db_session, username="pw_test2")
    db_session.commit()

    token = _login(client, "pw_test2", "secret123")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "wrong-password", "new_password": "newpass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_change_password_rejects_short_new_password(client, db_session):
    make_teacher(db_session, username="pw_test3")
    db_session.commit()

    token = _login(client, "pw_test3", "secret123")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "secret123", "new_password": "abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
