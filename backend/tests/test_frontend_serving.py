"""Tests for static frontend serving and the dual API mount.

Pins the deployment contract that broke in production ({"detail":"Not Found"}
at /): the committed SPA must be served by FastAPI at / and on client-side
routes, the production bundle's hard-coded ``/api`` base URL must reach the
real routers, and unknown API paths must stay machine-readable 404s instead of
returning HTML.
"""

import re

from app.main import app


def test_root_serves_index_html(test_client):
    """/ must boot the SPA instead of returning {"detail":"Not Found"}."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in response.text

    # Whatever JS bundle index.html references must actually be served.
    match = re.search(r'src="(/assets/[^"]+\.js)"', response.text)
    assert match, "index.html must reference a built JS bundle"
    assert test_client.get(match.group(1)).status_code == 200


def test_unknown_spa_route_serves_index_html(test_client):
    """Client-side routes fall back to index.html so React can route them."""
    response = test_client.get("/some/client-side/route")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_unknown_api_path_returns_json_404(test_client):
    """Misspelled API calls must not receive the SPA fallback as HTML."""
    response = test_client.get("/api/definitely-not-a-real-endpoint")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_prefixed_routes_reach_real_routers(test_client):
    """The committed bundle hard-codes API_BASE_URL='/api' (api/client.js)."""
    response = test_client.get("/api/auth/me")
    # 401/403 with a JSON body proves the real auth router served the request,
    # not the frontend catch-all.
    assert response.status_code in (401, 403)
    assert response.headers["content-type"].startswith("application/json")


def test_bare_api_routes_still_mounted(test_client):
    """Bare paths keep working: the test suite and Vite dev proxy use them."""
    response = test_client.get("/auth/me")
    assert response.status_code in (401, 403)
    assert response.headers["content-type"].startswith("application/json")


def test_favicon_served(test_client):
    response = test_client.get("/favicon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["content-type"]


def test_catch_all_registered_after_all_routers():
    """Ordering guard: the SPA fallback must never shadow a real API route."""
    route_list = app.router.routes
    catch_all_indexes = [
        i
        for i, route in enumerate(route_list)
        if getattr(route, "path", "") == "/{full_path:path}"
    ]
    assert catch_all_indexes, "SPA catch-all route is missing"
    catch_all_index = catch_all_indexes[0]

    # Included feature routers appear as wrapper objects without a `path`
    # attribute on recent FastAPI versions; identify them structurally so the
    # check survives internals changes.
    router_include_indexes = [
        i
        for i, route in enumerate(route_list)
        if not hasattr(route, "path") and hasattr(route, "original_router")
    ]
    assert router_include_indexes, "No feature routers included in the app"
    assert max(router_include_indexes) < catch_all_index, (
        "The SPA catch-all must be registered after all API routers so it "
        "can never shadow them"
    )
