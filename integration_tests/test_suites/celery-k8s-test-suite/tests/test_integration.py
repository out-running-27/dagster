import datetime
import os
import time
import uuid
from typing import Any, Mapping

import boto3
import pytest
from dagster import DagsterEventType
from dagster._core.storage.dagster_run import DagsterRunStatus
from dagster._core.storage.tags import DOCKER_IMAGE_TAG
from dagster._utils.merger import deep_merge_dicts, merge_dicts
from dagster._utils.yaml_utils import merge_yamls
from dagster_k8s.test import wait_for_job_and_get_raw_logs
from dagster_k8s_test_infra.integration_utils import (
    can_terminate_run_over_graphql,
    image_pull_policy,
    launch_run_over_graphql,
    terminate_run_over_graphql,
)
from dagster_test.test_project import cleanup_memoized_results, get_test_project_environments_path
from dagster_test.test_project.test_jobs.repo import define_memoization_job

IS_BUILDKITE = os.getenv("BUILDKITE") is not None


def get_celery_engine_config(
    dagster_docker_image: str, job_namespace: str, include_dagster_job_env: bool = False
) -> Mapping[str, Any]:
    return {
        "execution": {
            "config": merge_dicts(
                (
                    {
                        "job_image": dagster_docker_image,
                    }
                    if dagster_docker_image
                    else {}
                ),
                {
                    "job_namespace": job_namespace,
                    "image_pull_policy": image_pull_policy(),
                },
                ({"env_config_maps": ["dagster-pipeline-env"]} if include_dagster_job_env else {}),
            )
        },
    }


def test_execute_on_celery_k8s_default(
    dagster_docker_image,
    dagster_instance,
    helm_namespace,
    dagit_url,
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="demo_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id,
        namespace=helm_namespace,
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

    updated_run = dagster_instance.get_run_by_id(run_id)
    assert updated_run.tags[DOCKER_IMAGE_TAG] == dagster_docker_image


def test_execute_on_celery_k8s_job_api(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="demo_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id,
        namespace=helm_namespace,
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

    updated_run = dagster_instance.get_run_by_id(run_id)
    assert updated_run.tags[DOCKER_IMAGE_TAG] == dagster_docker_image


def test_execute_on_celery_k8s_job_api_with_legacy_configmap_set(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    # Originally, jobs needed to include "dagster-pipeline-env" to pick up needed config when
    # using the helm chart - it's no longer needed, but verify that nothing breaks if it's included
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image,
            job_namespace=helm_namespace,
            include_dagster_job_env=True,
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="demo_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

    updated_run = dagster_instance.get_run_by_id(run_id)
    assert updated_run.tags[DOCKER_IMAGE_TAG] == dagster_docker_image


def test_execute_on_celery_k8s_image_from_origin(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    # Like the previous test, but the image is found from the job origin
    # rather than the executor config
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(dagster_docker_image=None, job_namespace=helm_namespace),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="demo_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

    updated_run = dagster_instance.get_run_by_id(run_id)
    assert updated_run.tags[DOCKER_IMAGE_TAG] == dagster_docker_image


def test_execute_subset_on_celery_k8s(dagster_docker_image, helm_namespace, dagit_url):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env_subset.yaml"),
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url,
        run_config=run_config,
        job_name="demo_job_celery_k8s",
        solid_selection=["count_letters"],
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"


def test_execute_on_celery_k8s_retry_job(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    run_config = merge_dicts(
        merge_yamls([os.path.join(get_test_project_environments_path(), "env_s3.yaml")]),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="retry_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

    stats = dagster_instance.get_run_stats(run_id)
    assert stats.steps_succeeded == 1

    assert DagsterEventType.STEP_START in [
        event.dagster_event.event_type
        for event in dagster_instance.all_logs(run_id)
        if event.is_dagster_event
    ]

    assert DagsterEventType.STEP_UP_FOR_RETRY in [
        event.dagster_event.event_type
        for event in dagster_instance.all_logs(run_id)
        if event.is_dagster_event
    ]

    assert DagsterEventType.STEP_RESTARTED in [
        event.dagster_event.event_type
        for event in dagster_instance.all_logs(run_id)
        if event.is_dagster_event
    ]

    assert DagsterEventType.STEP_SUCCESS in [
        event.dagster_event.event_type
        for event in dagster_instance.all_logs(run_id)
        if event.is_dagster_event
    ]


def test_execute_on_celery_k8s_with_resource_requirements(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="resources_limit_job_celery_k8s"
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"


def _test_termination(dagit_url, dagster_instance, run_config):
    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="resource_job_celery_k8s"
    )

    # Wait for run to start
    timeout = datetime.timedelta(0, 120)
    start_time = datetime.datetime.now()

    while True:
        assert datetime.datetime.now() < start_time + timeout, "Timed out waiting for can_terminate"
        dagster_run = dagster_instance.get_run_by_id(run_id)
        if can_terminate_run_over_graphql(dagit_url, run_id):
            break
        time.sleep(5)

    # Wait for step to start
    step_start_found = False
    start_time = datetime.datetime.now()
    while datetime.datetime.now() < start_time + timeout:
        event_records = dagster_instance.all_logs(run_id)
        for event_record in event_records:
            if (
                event_record.dagster_event
                and event_record.dagster_event.event_type == DagsterEventType.STEP_START
            ):
                step_start_found = True
                break

        if step_start_found:
            break

        time.sleep(5)
    assert step_start_found

    # Terminate run
    assert can_terminate_run_over_graphql(dagit_url, run_id=run_id)
    terminate_run_over_graphql(dagit_url, run_id=run_id)

    # Check that run is marked as canceled
    dagster_run_status_canceled = False
    start_time = datetime.datetime.now()
    while datetime.datetime.now() < start_time + timeout:
        dagster_run = dagster_instance.get_run_by_id(run_id)
        if dagster_run.status == DagsterRunStatus.CANCELED:
            dagster_run_status_canceled = True
            break
        time.sleep(5)
    assert dagster_run_status_canceled

    # Check that terminate cannot be called again
    assert not can_terminate_run_over_graphql(dagit_url, run_id=run_id)

    # Check for step failure and resource tear down
    expected_events_found = False
    start_time = datetime.datetime.now()
    while datetime.datetime.now() < start_time + timeout:
        step_failures_count = 0
        resource_tear_down_count = 0
        resource_init_count = 0
        termination_request_count = 0
        termination_success_count = 0
        event_records = dagster_instance.all_logs(run_id)
        for event_record in event_records:
            if event_record.dagster_event:
                if event_record.dagster_event.event_type == DagsterEventType.STEP_FAILURE:
                    step_failures_count += 1
                elif event_record.dagster_event.event_type == DagsterEventType.PIPELINE_CANCELING:
                    termination_request_count += 1
                elif event_record.dagster_event.event_type == DagsterEventType.PIPELINE_CANCELED:
                    termination_success_count += 1
            elif event_record.message:
                if "initializing s3_resource_with_context_manager" in event_record.message:
                    resource_init_count += 1
                if "tearing down s3_resource_with_context_manager" in event_record.message:
                    resource_tear_down_count += 1
        if (
            step_failures_count == 1
            and resource_init_count == 1
            and resource_tear_down_count == 1
            and termination_request_count == 1
            and termination_success_count == 1
        ):
            expected_events_found = True
            break
        time.sleep(5)
    assert expected_events_found

    s3 = boto3.resource("s3", region_name="us-west-1", use_ssl=True, endpoint_url=None).meta.client
    bucket = "dagster-scratch-80542c2"
    key = f"resource_termination_test/{run_id}"
    assert s3.get_object(Bucket=bucket, Key=key)


def test_execute_on_celery_k8s_with_termination(
    dagster_docker_image,
    dagster_instance,
    helm_namespace,
    dagit_url,
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    _test_termination(dagit_url, dagster_instance, run_config)


@pytest.fixture(scope="function")
def set_dagster_k8s_dagster_run_namespace_env(helm_namespace):
    old_value = None
    try:
        old_value = os.getenv("DAGSTER_K8S_PIPELINE_RUN_NAMESPACE")
        os.environ["DAGSTER_K8S_PIPELINE_RUN_NAMESPACE"] = helm_namespace
        yield
    finally:
        if old_value is not None:
            os.environ["DAGSTER_K8S_PIPELINE_RUN_NAMESPACE"] = old_value


def test_execute_on_celery_k8s_with_env_var_and_termination(
    dagster_docker_image, dagster_instance, set_dagster_k8s_dagster_run_namespace_env, dagit_url
):
    run_config = merge_dicts(
        merge_yamls(
            [
                os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
            ]
        ),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image,
            job_namespace={"env": "DAGSTER_K8S_PIPELINE_RUN_NAMESPACE"},
        ),
    )

    _test_termination(dagit_url, dagster_instance, run_config)


def test_execute_on_celery_k8s_with_hard_failure(
    dagster_docker_image, dagster_instance, set_dagster_k8s_dagster_run_namespace_env, dagit_url
):
    run_config = merge_dicts(
        merge_dicts(
            merge_yamls(
                [
                    os.path.join(get_test_project_environments_path(), "env_s3.yaml"),
                ]
            ),
            get_celery_engine_config(
                dagster_docker_image=dagster_docker_image,
                job_namespace={"env": "DAGSTER_K8S_PIPELINE_RUN_NAMESPACE"},
            ),
        ),
        {"ops": {"hard_fail_or_0": {"config": {"fail": True}}}},
    )

    run_id = launch_run_over_graphql(
        dagit_url, run_config=run_config, job_name="hard_failer_job_celery_k8s"
    )

    # Check that run is marked as failed
    dagster_run_status_failure = False
    start_time = datetime.datetime.now()
    timeout = datetime.timedelta(0, 120)

    while datetime.datetime.now() < start_time + timeout:
        dagster_run = dagster_instance.get_run_by_id(run_id)
        if dagster_run.status == DagsterRunStatus.FAILURE:
            dagster_run_status_failure = True
            break
        time.sleep(5)
    assert dagster_run_status_failure

    # Check for step failure for hard_fail_or_0.compute
    start_time = datetime.datetime.now()
    step_failure_found = False
    while datetime.datetime.now() < start_time + timeout:
        event_records = dagster_instance.all_logs(run_id)
        for event_record in event_records:
            if event_record.dagster_event:
                if (
                    event_record.dagster_event.event_type == DagsterEventType.STEP_FAILURE
                    and event_record.dagster_event.step_key == "hard_fail_or_0"
                ):
                    step_failure_found = True
                    break
        time.sleep(5)
    assert step_failure_found


def _get_step_events(event_logs):
    return [
        event_log.dagster_event
        for event_log in event_logs
        if event_log.dagster_event is not None and event_log.dagster_event.is_step_event
    ]


def test_memoization_on_celery_k8s(
    dagster_docker_image, dagster_instance, helm_namespace, dagit_url
):
    ephemeral_prefix = str(uuid.uuid4())
    run_config = deep_merge_dicts(
        merge_yamls([os.path.join(get_test_project_environments_path(), "env_s3.yaml")]),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )
    run_config = deep_merge_dicts(
        run_config,
        {"resources": {"io_manager": {"config": {"s3_prefix": ephemeral_prefix}}}},
    )

    try:
        run_ids = []
        for _ in range(2):
            run_id = launch_run_over_graphql(
                dagit_url,
                run_config=run_config,
                job_name="memoization_job_celery_k8s",
            )

            result = wait_for_job_and_get_raw_logs(
                job_name="dagster-run-%s" % run_id, namespace=helm_namespace
            )

            assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"

            run_ids.append(run_id)

        unmemoized_run_id = run_ids[0]
        step_events = _get_step_events(dagster_instance.all_logs(unmemoized_run_id))
        assert len(step_events) == 4

        memoized_run_id = run_ids[1]
        step_events = _get_step_events(dagster_instance.all_logs(memoized_run_id))
        assert len(step_events) == 0

    finally:
        cleanup_memoized_results(
            define_memoization_job("celery_k8s")(), dagster_instance, run_config
        )


@pytest.mark.integration
def test_volume_mounts(dagster_docker_image, dagster_instance, helm_namespace, dagit_url):
    run_config = deep_merge_dicts(
        merge_yamls([os.path.join(get_test_project_environments_path(), "env_s3.yaml")]),
        get_celery_engine_config(
            dagster_docker_image=dagster_docker_image, job_namespace=helm_namespace
        ),
    )

    run_id = launch_run_over_graphql(
        dagit_url,
        run_config=run_config,
        job_name="volume_mount_job_celery_k8s",
    )

    result = wait_for_job_and_get_raw_logs(
        job_name="dagster-run-%s" % run_id, namespace=helm_namespace
    )

    assert "PIPELINE_SUCCESS" in result, f"no match, result: {result}"
