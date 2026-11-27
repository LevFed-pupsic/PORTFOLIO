import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.config import Settings, BASE
from app.main import create_app
from app.schemas import Inquiry
from app.services import create_token, submit


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        database=tmp_path / "test.sqlite3", secret="test-secret", min_form_seconds=0
    )
    with TestClient(create_app(settings)) as client:
        yield client, settings


def payload(settings, **changes):
    data = dict(
        name="Тестовый клиент",
        email="demo@example.com",
        service="portrait",
        message="Хочу обсудить тестовую съёмку",
        consent=True,
        website="",
        token=create_token(settings),
    )
    data.update(changes)
    return data


def count(settings):
    with sqlite3.connect(settings.database) as db:
        return db.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/portfolio",
        "/privacy",
        "/robots.txt",
        "/static/css/style.css",
        "/static/js/main.js",
    ],
)
def test_pages(setup, path):
    client, _ = setup
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_save_and_duplicate(setup):
    client, settings = setup
    data = payload(settings)
    assert client.post("/api/inquiries", json=data).status_code == 201
    assert client.post("/api/inquiries", json=data).status_code == 200
    assert count(settings) == 1
    with sqlite3.connect(settings.database) as db:
        assert db.execute("SELECT name,email,consent FROM inquiries").fetchone() == (
            data["name"],
            data["email"],
            1,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "bad"},
        {"name": "x"},
        {"message": "tiny"},
        {"consent": False},
        {"service": "unknown"},
        {"message": "x" * 2001},
        {"extra": "bad"},
    ],
)
def test_validation(setup, changes):
    client, settings = setup
    assert (
        client.post("/api/inquiries", json=payload(settings, **changes)).status_code
        == 422
    )
    assert count(settings) == 0


def test_bad_json(setup):
    client, _ = setup
    assert (
        client.post(
            "/api/inquiries", content="{", headers={"Content-Type": "application/json"}
        ).status_code
        == 422
    )


def test_wrong_content_type(setup):
    client, _ = setup
    assert client.post("/api/inquiries", data={"name": "X"}).status_code == 415


def test_body_limit(setup):
    client, _ = setup
    assert (
        client.post(
            "/api/inquiries",
            content="x" * 17000,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_spam_and_signature(setup):
    client, settings = setup
    assert (
        client.post(
            "/api/inquiries", json=payload(settings, website="spam")
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/inquiries", json=payload(settings, token="tampered.token.sign")
        ).status_code
        == 403
    )
    assert count(settings) == 0


def test_timing_and_expiry(setup):
    client, settings = setup
    settings.min_form_seconds = 2
    with patch("app.services.time.time", return_value=10000):
        data = payload(settings)
        assert client.post("/api/inquiries", json=data).status_code == 400
    with patch("app.services.time.time", return_value=10003):
        assert client.post("/api/inquiries", json=data).status_code == 201
    with patch("app.services.time.time", return_value=18000):
        assert client.post("/api/inquiries", json=data).status_code == 403


def test_cross_origin(setup):
    client, settings = setup
    assert (
        client.post(
            "/api/inquiries",
            json=payload(settings),
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert count(settings) == 0


def test_rate_limit(setup):
    client, settings = setup
    for i in range(5):
        assert (
            client.post(
                "/api/inquiries",
                json=payload(settings, message=f"Тестовое сообщение номер {i}"),
            ).status_code
            == 201
        )
    response = client.post(
        "/api/inquiries", json=payload(settings, message="Ещё одна новая заявка")
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "600"
    assert count(settings) == 5


def test_sql_injection_is_data(setup):
    client, settings = setup
    malicious = "Robert'); DROP TABLE inquiries;--"
    assert (
        client.post(
            "/api/inquiries", json=payload(settings, name=malicious)
        ).status_code
        == 201
    )
    with sqlite3.connect(settings.database) as db:
        assert db.execute("SELECT name FROM inquiries").fetchone()[0] == malicious


@pytest.mark.parametrize(
    "path",
    [
        "/api/inquiries",
        "/var/inquiries.sqlite3",
        "/static/../var/inquiries.sqlite3",
        "/docs",
        "/openapi.json",
    ],
)
def test_no_public_data(setup, path):
    client, _ = setup
    assert client.get(path).status_code in (404, 405)


def test_database_error(setup):
    client, settings = setup
    with patch(
        "app.main.submit", side_effect=sqlite3.OperationalError("private database path")
    ):
        result = client.post("/api/inquiries", json=payload(settings))
        assert result.status_code == 503
        assert "private database path" not in result.text


def test_concurrent_duplicate(setup):
    _, settings = setup
    data = Inquiry(**payload(settings))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: submit(data, settings, "client"), range(6)))
    assert results.count("created") == 1
    assert count(settings) == 1


def test_local_assets_and_links(setup):
    client, _ = setup
    for route in ["/", "/portfolio", "/privacy"]:
        html = client.get(route).text
        for url in re.findall(r'(?:src|href)="(/[^"#]*)"', html):
            assert client.get(url).status_code == 200, url
    content = json.loads((BASE / "data/content.json").read_text())
    for work in content["works"]:
        assert (BASE / "static/images" / f"{work['image']}.webp").exists()
        assert (BASE / "static/images" / f"{work['image']}-small.webp").exists()


def test_public_https_origin_behind_proxy(setup):
    client, settings = setup
    response = client.post('/api/inquiries', json=payload(settings),
                           headers={'Origin': settings.site_url, 'Host': 'internal:8000'})
    assert response.status_code == 201
    assert count(settings) == 1


@pytest.mark.parametrize('origin', ['https://evil.example', 'null',
    'https://morozov-photography.de2.netrun.io.evil.example',
    'https://morozov-photography.de2.netrun.io/path'])
def test_forwarded_headers_do_not_allow_foreign_origin(setup, origin):
    client, settings = setup
    response = client.post('/api/inquiries', json=payload(settings), headers={
        'Origin': origin, 'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'evil.example',
        'Forwarded': 'host=evil.example;proto=https'})
    assert response.status_code == 403
    assert count(settings) == 0


def test_local_origin_still_works(setup):
    client, settings = setup
    assert client.post('/api/inquiries', json=payload(settings),
                       headers={'Origin': 'http://testserver'}).status_code == 201


def test_configured_canonical_sitemap_and_og(tmp_path):
    import xml.etree.ElementTree as ET
    settings = Settings(database=tmp_path / 'seo.sqlite3', site_url='https://photos.example')
    with TestClient(create_app(settings)) as client:
        for path in ('/', '/portfolio', '/privacy'):
            html = client.get(path, headers={'Host': 'untrusted.example'}).text
            assert f'<link rel="canonical" href="https://photos.example{path}">' in html
            assert 'https://photos.example/static/images/portrait.webp' in html
        response = client.get('/sitemap.xml')
        assert response.headers['content-type'].startswith('application/xml')
        root = ET.fromstring(response.text)
        assert [loc.text for loc in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')] == [
            'https://photos.example/', 'https://photos.example/portfolio', 'https://photos.example/privacy']
        assert 'Sitemap: https://photos.example/sitemap.xml' in client.get('/robots.txt').text


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'https://a.example/path',
    'https://user:pass@a.example', 'https://a.example?x=1', 'https://a.example:bad'])
def test_site_url_rejects_invalid_configuration(url):
    with pytest.raises(ValueError):
        Settings(site_url=url)
