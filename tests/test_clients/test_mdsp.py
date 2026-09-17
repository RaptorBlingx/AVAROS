from skill.clients.mdsp import MdspClient


def test_environment_configures_scoped_tls_ca(monkeypatch):
    monkeypatch.setenv("MDSP_BASE_URL", "https://mdsp.example.test")
    monkeypatch.setenv("MDSP_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("MDSP_TLS_CA_PATH", "/run/secrets/mdsp-ca.crt")

    client = MdspClient.from_environment()

    assert client._tls_ca_path == "/run/secrets/mdsp-ca.crt"
