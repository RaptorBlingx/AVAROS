from skill.clients.mdsp import MdspClient


def test_environment_configures_scoped_tls_ca(monkeypatch):
    monkeypatch.setenv("MDSP_BASE_URL", "https://mdsp.example.test")
    monkeypatch.setenv("MDSP_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("MDSP_TLS_CA_PATH", "/run/secrets/mdsp-ca.crt")

    client = MdspClient.from_environment()

    assert client._tls_ca_path == "/run/secrets/mdsp-ca.crt"


def test_finding_preserves_rule_identity_for_conversational_interpretation():
    finding = MdspClient._finding(
        {
            "id": "finding-1",
            "ruleId": "metric-source-recent-continuity",
            "ruleVersion": 1,
            "title": {"en": "Recent gaps", "tr": "Yakın boşluklar"},
            "summary": {"en": "Summary", "tr": "Özet"},
            "evaluationWindow": {
                "start": "2026-08-18T10:00:00Z",
                "end": "2026-09-17T10:00:00Z",
            },
        }
    )

    assert finding.rule_id == "metric-source-recent-continuity"
    assert finding.rule_version == 1
