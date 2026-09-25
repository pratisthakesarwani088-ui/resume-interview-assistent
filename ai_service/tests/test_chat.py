from unittest.mock import patch

from app import gemini


def test_chat_requires_internal_key_when_configured(client):
    res = client.post("/chat", json={"system_instruction": "x", "history": [], "message": "hi"})
    assert res.status_code == 401


def test_chat_rejects_wrong_key(client):
    res = client.post(
        "/chat",
        json={"system_instruction": "x", "history": [], "message": "hi"},
        headers={"X-Internal-Api-Key": "wrong"},
    )
    assert res.status_code == 401


@patch("app.routers.chat.gemini.generate_text", return_value="Hello there!")
def test_chat_success(mock_generate, client, auth_headers):
    res = client.post(
        "/chat",
        json={
            "system_instruction": "You are helpful.",
            "history": [{"role": "user", "content": "hi"}],
            "message": "how are you?",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json() == {"reply": "Hello there!"}
    mock_generate.assert_called_once()
    args = mock_generate.call_args[0]
    assert args[0] == "You are helpful."
    assert args[1] == [{"role": "user", "content": "hi"}]
    assert args[2] == "how are you?"


@patch("app.routers.chat.gemini.generate_text", side_effect=gemini.GeminiError("boom"))
def test_chat_gemini_failure_returns_502(mock_generate, client, auth_headers):
    res = client.post(
        "/chat", json={"system_instruction": "x", "history": [], "message": "hi"}, headers=auth_headers
    )
    assert res.status_code == 502
