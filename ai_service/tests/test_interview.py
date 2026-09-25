from unittest.mock import patch

from app import gemini
from app.schemas import AnswerEvaluationResponse, FinalReportResponse, GeneratedQuestionsResponse


def test_all_interview_endpoints_require_internal_key(client):
    assert client.post("/interview/questions", json={"prompt": "x"}).status_code == 401
    assert client.post("/interview/evaluate", json={"prompt": "x"}).status_code == 401
    assert client.post("/interview/report", json={"prompt": "x"}).status_code == 401


@patch(
    "app.routers.interview.gemini.generate_structured",
    return_value=GeneratedQuestionsResponse(questions=[f"Question {i}?" for i in range(12)]),
)
def test_interview_questions_success(mock_generate, client, auth_headers):
    res = client.post("/interview/questions", json={"prompt": "generate questions"}, headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["questions"]) == 12


@patch(
    "app.routers.interview.gemini.generate_structured",
    return_value=AnswerEvaluationResponse(score=8, feedback="Good answer.", ideal_answer="Ideal answer."),
)
def test_interview_evaluate_success(mock_generate, client, auth_headers):
    res = client.post("/interview/evaluate", json={"prompt": "evaluate this"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["score"] == 8


@patch(
    "app.routers.interview.gemini.generate_structured",
    return_value=FinalReportResponse(
        overall_score=80, strengths=["Clarity"], weak_areas=["Depth"], feedback="Solid overall."
    ),
)
def test_interview_report_success(mock_generate, client, auth_headers):
    res = client.post("/interview/report", json={"prompt": "summarize"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["overall_score"] == 80


@patch("app.routers.interview.gemini.generate_structured", side_effect=gemini.GeminiError("boom"))
def test_interview_questions_gemini_failure_returns_502(mock_generate, client, auth_headers):
    res = client.post("/interview/questions", json={"prompt": "x"}, headers=auth_headers)
    assert res.status_code == 502
