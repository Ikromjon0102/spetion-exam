from app.tests.factories import make_class, make_student


def test_list_classes(client, db_session):
    klass = make_class(db_session)
    db_session.commit()

    resp = client.get("/api/v1/auth/classes")
    assert resp.status_code == 200
    assert any(c["id"] == klass.id for c in resp.json())


def test_student_login_success_and_me(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="student1")
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"username": "student1", "password": "secret123", "class_id": klass.id}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "student1"
    assert me.json()["role"] == "student"


def test_student_login_with_wrong_class_is_rejected(client, db_session):
    klass = make_class(db_session)
    other_class = make_class(db_session)
    make_student(db_session, klass, username="student1")
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"username": "student1", "password": "secret123", "class_id": other_class.id}
    )
    assert resp.status_code == 401


def test_login_wrong_password_is_rejected(client, db_session):
    klass = make_class(db_session)
    make_student(db_session, klass, username="student1")
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login", json={"username": "student1", "password": "wrong-pw", "class_id": klass.id}
    )
    assert resp.status_code == 401


def test_protected_endpoint_without_token_is_rejected(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
