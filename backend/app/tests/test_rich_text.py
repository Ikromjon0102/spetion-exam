"""Rich-text question content: sanitized at the API boundary, marker-gated so
old plain-text questions are never reinterpreted as HTML."""

from app.core import rich_text
from app.core.rich_text import RICH_PREFIX
from app.tests.factories import make_admin, make_class, make_exam, make_subject


def test_plain_text_is_never_touched():
    assert rich_text.sanitize("Savol <b>qalin</b> teg haqida") == "Savol <b>qalin</b> teg haqida"
    assert rich_text.sanitize("x < 3 && y > 2") == "x < 3 && y > 2"


def test_rich_text_keeps_allowed_formatting_and_formula_spans():
    src = RICH_PREFIX + '<p>x<sup>2</sup> <strong>qalin</strong> <span data-type="inline-math" data-latex="\frac{a}{b}"></span></p>'
    out = rich_text.sanitize(src)
    assert out.startswith(RICH_PREFIX)
    assert "<sup>2</sup>" in out and "<strong>qalin</strong>" in out
    assert 'data-latex="\frac{a}{b}"' in out


def test_rich_text_strips_scripts_handlers_styles_and_links():
    src = (
        RICH_PREFIX
        + '<p onclick="steal()">hi<script>alert(1)</script><img src=x onerror=alert(2)>'
        + '<a href="javascript:alert(3)">link</a><span style="color:red" data-type="evil">t</span></p>'
    )
    out = rich_text.sanitize(src)
    for bad in ("script", "onclick", "onerror", "<img", "javascript:", "<a ", "style=", "evil", "alert"):
        assert bad not in out, (bad, out)
    assert "hi" in out and "link" in out and "t" in out


def test_empty_rich_content_collapses_to_empty_string():
    assert rich_text.sanitize(RICH_PREFIX + "<p></p>") == ""
    assert rich_text.sanitize(RICH_PREFIX) == ""


def test_plain_text_view_keeps_formulas_for_the_ai_grader():
    src = RICH_PREFIX + '<p>Hisoblang: <span data-type="inline-math" data-latex="x^2+1"></span></p><p>Javob?</p>'
    assert rich_text.to_plain_text(src) == "Hisoblang: x^2+1 Javob?"
    assert rich_text.to_plain_text("oddiy <matn>") == "oddiy <matn>"


def _admin_headers(client, db_session):
    make_admin(db_session, username="rich_admin")
    db_session.commit()
    token = client.post("/api/v1/auth/login", json={"username": "rich_admin", "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_sanitizes_rich_prompt_and_options_on_create_and_update(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()
    headers = _admin_headers(client, db_session)

    created = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions",
        headers=headers,
        json={
            "prompt_text": RICH_PREFIX + "<p>x<sup>2</sup><script>alert(1)</script></p>",
            "options": [
                {"option_text": RICH_PREFIX + 'a<img src=x onerror="z()">', "is_correct": True},
                {"option_text": "plain <b>text</b>", "is_correct": False},
            ],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert "<sup>2</sup>" in body["prompt_text"] and "script" not in body["prompt_text"]
    assert "onerror" not in body["options"][0]["option_text"]
    assert body["options"][1]["option_text"] == "plain <b>text</b>"  # plain stays literal

    updated = client.put(
        f"/api/v1/admin/exams/{exam.id}/questions/{body['id']}",
        headers=headers,
        json={"prompt_text": RICH_PREFIX + '<p onmouseover="x()">yangi</p>'},
    )
    assert updated.status_code == 200
    assert "onmouseover" not in updated.json()["prompt_text"] and "yangi" in updated.json()["prompt_text"]

    option_id = body["options"][0]["id"]
    opt = client.put(
        f"/api/v1/admin/exams/{exam.id}/questions/{body['id']}/options/{option_id}",
        headers=headers,
        json={"option_text": RICH_PREFIX + "<strong>ok</strong><script>1</script>"},
    )
    assert opt.status_code == 200 and "script" not in opt.json()["option_text"]


def test_overlong_text_is_rejected(client, db_session):
    klass = make_class(db_session)
    subject = make_subject(db_session)
    exam = make_exam(db_session, klass, subject)
    db_session.commit()
    headers = _admin_headers(client, db_session)
    resp = client.post(
        f"/api/v1/admin/exams/{exam.id}/questions",
        headers=headers,
        json={"prompt_text": "x" * 20_001, "options": []},
    )
    assert resp.status_code == 422
