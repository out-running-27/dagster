from typing import Any

from dagster_graphql.test.utils import execute_dagster_graphql

from .graphql_context_test_suite import GraphQLContextVariant, make_graphql_context_test_suite

INSTANCE_QUERY = """
query InstanceDetailSummaryQuery {
    instance {
        runQueuingSupported
        hasInfo
    }
}
"""

GET_CONCURRENCY_LIMITS_QUERY = """
query InstanceConcurrencyLimitsQuery {
    instance {
        concurrencyLimits {
            concurrencyKey
            limit
            activeRunIds
            numActive
        }
    }
}
"""

SET_CONCURRENCY_LIMITS_MUTATION = """
mutation SetConcurrencyLimit($concurrencyKey: String!, $limit: Int!) {
    setConcurrencyLimit(concurrencyKey: $concurrencyKey, limit: $limit)
}
"""

BaseTestSuite: Any = make_graphql_context_test_suite(
    context_variants=[
        GraphQLContextVariant.sqlite_with_queued_run_coordinator_managed_grpc_env(),
    ]
)


class TestInstanceSettings(BaseTestSuite):
    def test_instance_settings(self, graphql_context):
        results = execute_dagster_graphql(graphql_context, INSTANCE_QUERY)
        assert results.data == {
            "instance": {
                "runQueuingSupported": True,
                "hasInfo": graphql_context.show_instance_config,
            }
        }

    def test_concurrency_limits(self, graphql_context):
        instance = graphql_context.instance

        def _fetch_limits(key: str):
            results = execute_dagster_graphql(
                graphql_context,
                GET_CONCURRENCY_LIMITS_QUERY,
                variables={
                    "concurrencyKey": key,
                },
            )
            assert results.data
            assert "instance" in results.data
            assert "concurrencyLimits" in results.data["instance"]
            return results.data["instance"]["concurrencyLimits"]

        def _set_limits(key: str, limit: int):
            execute_dagster_graphql(
                graphql_context,
                SET_CONCURRENCY_LIMITS_MUTATION,
                variables={
                    "concurrencyKey": key,
                    "limit": limit,
                },
            )

        # default limits are empty
        assert _fetch_limits("foo") == []

        # set a limit
        _set_limits("foo", 10)
        assert _fetch_limits("foo") == [
            {"concurrencyKey": "foo", "limit": 10, "activeRunIds": [], "numActive": 0}
        ]

        # claim a slot
        run_id = "fake_run_id"
        instance.event_log_storage.claim_concurrency_slots({"foo"}, run_id, "fake_step_key")
        assert _fetch_limits("foo") == [
            {"concurrencyKey": "foo", "limit": 10, "activeRunIds": [run_id], "numActive": 1}
        ]

        # set a new limit
        _set_limits("foo", 5)
        assert _fetch_limits("foo") == [
            {"concurrencyKey": "foo", "limit": 5, "activeRunIds": [run_id], "numActive": 1}
        ]

        # free a slot
        instance.event_log_storage.free_concurrency_slots(run_id)
        assert _fetch_limits("foo") == [
            {"concurrencyKey": "foo", "limit": 5, "activeRunIds": [], "numActive": 0}
        ]
