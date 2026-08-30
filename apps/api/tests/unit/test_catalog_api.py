from collections.abc import Generator, Iterator
from contextlib import contextmanager
from decimal import Decimal

import pytest
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Game
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@contextmanager
def make_catalog_client(
    test_settings: Settings,
    *,
    seeded: bool,
) -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    if seeded:
        with sessionmaker(bind=engine, expire_on_commit=False)() as session:
            seed_database(session, load_seed_file())

    app = create_app(
        test_settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
    )
    with TestClient(app) as client:
        yield client
    engine.dispose()


@pytest.fixture
def catalog_client(test_settings: Settings) -> Generator[TestClient]:
    with make_catalog_client(test_settings, seeded=True) as client:
        yield client


@pytest.fixture
def empty_catalog_client(test_settings: Settings) -> Generator[TestClient]:
    with make_catalog_client(test_settings, seeded=False) as client:
        yield client


def test_catalog_pagination_and_default_sort(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/v1/games?page=1&page_size=5")

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert body["total"] == 30
    assert body["total_pages"] == 6
    assert len(body["items"]) == 5
    assert body["items"][0]["slug"] == "verdant-vale"


def test_empty_catalog_has_valid_pagination(empty_catalog_client: TestClient) -> None:
    response = empty_catalog_client.get("/api/v1/games")

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "total_pages": 0,
    }


def test_middle_and_final_catalog_pages(catalog_client: TestClient) -> None:
    middle = catalog_client.get("/api/v1/games?page=3&page_size=7").json()
    final = catalog_client.get("/api/v1/games?page=5&page_size=7").json()

    assert len(middle["items"]) == 7
    assert middle["total_pages"] == 5
    assert len(final["items"]) == 2
    assert final["total_pages"] == 5
    assert {item["id"] for item in middle["items"]}.isdisjoint(
        item["id"] for item in final["items"]
    )


def test_catalog_filters_and_unknown_taxonomy(catalog_client: TestClient) -> None:
    filtered = catalog_client.get("/api/v1/games?genre=card-game&tag=deckbuilding&platform=linux")
    unknown = catalog_client.get("/api/v1/games?genre=not-a-real-genre")

    assert filtered.status_code == 200
    assert {item["slug"] for item in filtered.json()["items"]} == {
        "null-protocol",
        "paper-kingdoms",
    }
    assert unknown.status_code == 200
    assert unknown.json()["items"] == []
    assert unknown.json()["total"] == 0
    assert unknown.json()["total_pages"] == 0


@pytest.mark.parametrize(
    ("filter_name", "slug"),
    [
        ("genre", "strategy"),
        ("tag", "deckbuilding"),
        ("platform", "linux"),
    ],
)
def test_each_catalog_filter_independently(
    catalog_client: TestClient,
    filter_name: str,
    slug: str,
) -> None:
    response = catalog_client.get(
        "/api/v1/games",
        params={filter_name: slug, "page_size": 100},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    taxonomy_key = f"{filter_name}s"
    assert all(slug in {value["slug"] for value in item[taxonomy_key]} for item in items)


@pytest.mark.parametrize(
    ("query", "expected_total"),
    [
        ("vErDaNt", 1),
        ("%", 0),
        ("_", 0),
        ("\\", 0),
    ],
)
def test_catalog_search_is_case_insensitive_and_treats_wildcards_as_literals(
    catalog_client: TestClient,
    query: str,
    expected_total: int,
) -> None:
    response = catalog_client.get("/api/v1/games", params={"q": query})

    assert response.status_code == 200
    assert response.json()["total"] == expected_total


@pytest.mark.parametrize(
    ("sort", "expected_first_slug"),
    [
        ("popularity", "verdant-vale"),
        ("rating", "archive-of-echoes"),
        ("release_date", "archive-of-echoes"),
        ("title", "abyssal-signal"),
    ],
)
def test_catalog_sort_contracts(
    catalog_client: TestClient,
    sort: str,
    expected_first_slug: str,
) -> None:
    response = catalog_client.get("/api/v1/games", params={"sort": sort})

    assert response.status_code == 200
    assert response.json()["items"][0]["slug"] == expected_first_slug


def test_catalog_sort_ties_are_broken_by_id_and_null_ratings_are_last(
    catalog_client: TestClient,
) -> None:
    with catalog_client.app.state.session_factory.begin() as session:
        first = Game(
            title="Tie Alpha",
            slug="tie-alpha",
            description="Tie-break fixture",
            average_rating=None,
            rating_count=0,
            popularity_score=Decimal("999"),
        )
        second = Game(
            title="Tie Beta",
            slug="tie-beta",
            description="Tie-break fixture",
            average_rating=None,
            rating_count=0,
            popularity_score=Decimal("999"),
        )
        session.add_all([first, second])
        session.flush()
        expected_ids = [first.id, second.id]

    popularity = catalog_client.get(
        "/api/v1/games",
        params={"sort": "popularity", "page_size": 2},
    ).json()
    rating = catalog_client.get(
        "/api/v1/games",
        params={"sort": "rating", "page_size": 100},
    ).json()

    assert [item["id"] for item in popularity["items"]] == expected_ids
    assert [item["id"] for item in rating["items"][-2:]] == expected_ids


def test_out_of_range_page_is_empty_but_keeps_total(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/v1/games?page=99&page_size=20")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 30
    assert response.json()["total_pages"] == 2


def test_game_detail_and_not_found_contract(catalog_client: TestClient) -> None:
    catalog = catalog_client.get("/api/v1/games?sort=title").json()
    game_id = catalog["items"][0]["id"]

    found = catalog_client.get(f"/api/v1/games/{game_id}")
    missing = catalog_client.get("/api/v1/games/999999")

    assert found.status_code == 200
    assert found.json()["description"]
    assert found.json()["genres"]
    assert found.json()["platforms"]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "game_not_found"


@pytest.mark.parametrize("taxonomy", ["genres", "tags", "platforms"])
def test_taxonomy_endpoints_are_sorted_and_unique(
    catalog_client: TestClient,
    taxonomy: str,
) -> None:
    response = catalog_client.get(f"/api/v1/metadata/{taxonomy}")

    assert response.status_code == 200
    values = response.json()
    names = [value["name"] for value in values]
    slugs = [value["slug"] for value in values]
    assert values
    assert names == sorted(names, key=str.casefold)
    assert len(slugs) == len(set(slugs))


def test_model_status_is_honest(catalog_client: TestClient) -> None:
    response = catalog_client.get("/api/v1/models/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "not_configured",
        "active_model": None,
        "capabilities": {
            "recommend": False,
            "explanations": False,
        },
        "components": {
            "content": {"status": "not_configured", "reason": None},
            "collaborative": {
                "status": "not_configured",
                "reason": "not_configured",
                "source_kind": None,
            },
        },
    }


@pytest.mark.parametrize(
    "query",
    [
        "page=0",
        "page_size=0",
        "page_size=101",
        "page=1000001",
        "sort=unknown",
        "genre=Invalid Slug",
        "genre=-leading",
        "tag=double--hyphen",
        "platform=trailing-",
    ],
)
def test_invalid_catalog_parameters_use_error_envelope(
    catalog_client: TestClient,
    query: str,
) -> None:
    response = catalog_client.get(f"/api/v1/games?{query}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("game_id", ["0", "2147483648"])
def test_invalid_game_ids_use_error_envelope(
    catalog_client: TestClient,
    game_id: str,
) -> None:
    response = catalog_client.get(f"/api/v1/games/{game_id}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_openapi_contains_stage_1_routes(catalog_client: TestClient) -> None:
    schema = catalog_client.get("/openapi.json").json()
    paths = schema["paths"]

    assert {
        "/health",
        "/api/v1/games",
        "/api/v1/games/{game_id}",
        "/api/v1/metadata/genres",
        "/api/v1/metadata/tags",
        "/api/v1/metadata/platforms",
        "/api/v1/models/status",
    } <= set(paths)

    error_ref = "#/components/schemas/ErrorResponse"
    health_ref = "#/components/schemas/HealthResponse"
    assert (
        paths["/api/v1/games"]["get"]["responses"]["422"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == error_ref
    )
    assert (
        paths["/api/v1/games"]["get"]["responses"]["503"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == error_ref
    )
    assert (
        paths["/api/v1/games/{game_id}"]["get"]["responses"]["404"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == error_ref
    )
    assert (
        paths["/health"]["get"]["responses"]["503"]["content"]["application/json"]["schema"]["$ref"]
        == health_ref
    )
    for path in paths.values():
        for operation in path.values():
            if "500" in operation["responses"]:
                assert (
                    operation["responses"]["500"]["content"]["application/json"]["schema"]["$ref"]
                    == error_ref
                )
