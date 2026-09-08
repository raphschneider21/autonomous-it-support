from src.engine.disagreement import reconcile_assessments


def test_no_disagreement_when_agents_agree():
    diag = {"agent": "DiagnosticAgent", "root_cause": "infrastructure/vpn", "evidence": "Service unreachable"}
    sec = {"agent": "SecurityAgent", "root_cause": "infrastructure/vpn", "evidence": "No auth anomalies"}
    result = reconcile_assessments(diag, sec)
    assert result["disagreement"] is False
    assert result["decision"] == "infrastructure/vpn"


def test_disagreement_detected_between_agents():
    diag = {"agent": "DiagnosticAgent", "root_cause": "infrastructure/erp_down", "evidence": "Server ping OK, service responding"}
    sec = {"agent": "SecurityAgent", "root_cause": "security/credential_harvesting", "evidence": "Anomalous login prompts detected"}
    result = reconcile_assessments(diag, sec)
    assert result["disagreement"] is True
    assert result["decision"] == "security/credential_harvesting"


def test_disagreement_reports_both_hypotheses():
    diag = {"agent": "DiagnosticAgent", "root_cause": "infrastructure", "evidence": "telnet ok"}
    sec = {"agent": "SecurityAgent", "root_cause": "security", "evidence": "phishing prompt"}
    result = reconcile_assessments(diag, sec)
    hypotheses = result["competing_hypotheses"]
    assert any(h["agent"] == "DiagnosticAgent" and h["hypothesis"] == "infrastructure" for h in hypotheses)
    assert any(h["agent"] == "SecurityAgent" and h["hypothesis"] == "security" for h in hypotheses)


def test_security_wins_on_disagreement():
    # Security-critical interpretation is the conservative default.
    diag = {"agent": "DiagnosticAgent", "root_cause": "infrastructure", "evidence": "all green"}
    sec = {"agent": "SecurityAgent", "root_cause": "security/credential_harvesting", "evidence": "fake auth page"}
    result = reconcile_assessments(diag, sec)
    assert result["decision"].startswith("security")


def test_missing_assessment_no_disagreement():
    result = reconcile_assessments(None, None)
    assert result["disagreement"] is False
    assert result["decision"] is None


def test_partial_assessment_no_disagreement():
    diag = {"agent": "DiagnosticAgent", "root_cause": "infrastructure", "evidence": "x"}
    result = reconcile_assessments(diag, None)
    assert result["disagreement"] is False
    assert result["detail"].startswith("Insufficient agent output")