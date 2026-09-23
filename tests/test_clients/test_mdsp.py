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


def test_finding_parses_next_review_and_abstention_without_inventing_fields():
    base = {
        "id": "finding-1",
        "title": {"en": "Recent gaps", "tr": "Yakın boşluklar"},
        "summary": {"en": "Summary", "tr": "Özet"},
        "evaluationWindow": {"start": "2026-08-18T10:00:00Z", "end": "2026-09-17T10:00:00Z"},
    }
    reviewed = MdspClient._finding({**base, "nextReview": {
        "code": "metric-source-recent-continuity-review",
        "version": 1,
        "instruction": {"en": "Inspect the gap.", "tr": "Boşluğu inceleyin."},
        "rationale": {"en": "A gap was observed.", "tr": "Bir boşluk gözlendi."},
        "evidenceKeys": ["longestGap"],
        "policyStatus": "PROVISIONAL",
        "assessmentRunId": "run-1",
        "reviewLink": None,
    }})
    assert reviewed.next_review is not None
    assert reviewed.next_review.instruction.tr == "Boşluğu inceleyin."
    assert reviewed.next_review.evidence_keys == ("longestGap",)
    assert reviewed.next_review.review_link is None

    abstained = MdspClient._finding({**base, "nextReview": None,
        "nextReviewAbstention": {"en": "Insufficient evidence.", "tr": "Kanıt yetersiz."}})
    assert abstained.next_review is None
    assert abstained.next_review_abstention is not None
    assert abstained.next_review_abstention.tr == "Kanıt yetersiz."
