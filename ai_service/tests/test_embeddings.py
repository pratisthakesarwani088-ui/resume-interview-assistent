from unittest.mock import patch

from app import gemini


def test_embeddings_requires_internal_key(client):
    res = client.post("/embeddings", json={"texts": ["hello"], "task_type": "RETRIEVAL_DOCUMENT"})
    assert res.status_code == 401


@patch("app.routers.embeddings.gemini.embed_texts", return_value=[[0.1, 0.2, 0.3]])
def test_embeddings_success(mock_embed, client, auth_headers):
    res = client.post(
        "/embeddings",
        json={"texts": ["hello world"], "task_type": "RETRIEVAL_DOCUMENT"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json() == {"embeddings": [[0.1, 0.2, 0.3]]}
    mock_embed.assert_called_once_with(["hello world"], "RETRIEVAL_DOCUMENT")


@patch("app.routers.embeddings.gemini.embed_texts", side_effect=gemini.GeminiError("boom"))
def test_embeddings_gemini_failure_returns_502(mock_embed, client, auth_headers):
    res = client.post(
        "/embeddings",
        json={"texts": ["hello"], "task_type": "RETRIEVAL_QUERY"},
        headers=auth_headers,
    )
    assert res.status_code == 502
