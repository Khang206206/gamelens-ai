from datetime import UTC, datetime

from app.repositories.collaborative_snapshot import (
    _eligible_users_subquery,
    _interaction_rows_query,
    _saved_game_preferences_query,
)
from sqlalchemy.dialects import postgresql


def test_source_queries_join_eligibility_without_per_user_bind_expansion() -> None:
    eligible_users = _eligible_users_subquery(
        cutoff=datetime(2026, 8, 24, tzinfo=UTC),
        personalization_consent_version="stage-4-v1",
        contribution_consent_version="stage-5-contribution-v1",
    )

    queries = (
        _saved_game_preferences_query(eligible_users),
        _interaction_rows_query(eligible_users),
    )
    for query in queries:
        compiled = query.compile(dialect=postgresql.dialect())
        sql = str(compiled)

        assert "eligible_collaborative_users" in sql
        assert "collaborative_contribution_consents" in sql
        assert " IN (" not in sql
        assert "POSTCOMPILE" not in sql
        assert len(compiled.params) < 20
