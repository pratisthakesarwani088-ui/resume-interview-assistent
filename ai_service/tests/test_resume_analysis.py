from unittest.mock import patch

from app import gemini
from app.schemas import ResumeAnalysisResponse, SuggestedRole


def _sample_result():
    return ResumeAnalysisResponse(
        ats_score=75,
        strengths=["Clear project descriptions"],
        weaknesses=["No summary section"],
        extracted_skills=["Python", "Django"],
        projects_experience=["Built a REST API"],
        suggested_roles=[SuggestedRole(role="Backend Developer", required_skills=["Python"], missing_skills=["Docker"])],
        improvement_suggestions=["Add a summary"],
    )


def test_resume_analysis_requires_internal_key(client):
    res = client.post("/resume-analysis", json={"prompt": "analyze this resume"})
    assert res.status_code == 401


@patch("app.routers.resume_analysis.gemini.generate_structured", return_value=_sample_result())
def test_resume_analysis_success(mock_generate, client, auth_headers):
    res = client.post("/resume-analysis", json={"prompt": "analyze this resume"}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ats_score"] == 75
    assert data["suggested_roles"][0]["role"] == "Backend Developer"
    mock_generate.assert_called_once()
    assert mock_generate.call_args[0][0] == "analyze this resume"


@patch("app.routers.resume_analysis.gemini.generate_structured", side_effect=gemini.GeminiError("boom"))
def test_resume_analysis_gemini_failure_returns_502(mock_generate, client, auth_headers):
    res = client.post("/resume-analysis", json={"prompt": "analyze this resume"}, headers=auth_headers)
    assert res.status_code == 502
