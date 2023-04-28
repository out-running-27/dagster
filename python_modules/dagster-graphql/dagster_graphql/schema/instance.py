import sys
from typing import List, Optional, Tuple

import dagster._check as check
import graphene
from dagster._core.instance import DagsterInstance
from dagster._core.launcher.base import RunLauncher
from dagster._core.storage.captured_log_manager import CapturedLogManager
from dagster._daemon.asset_daemon import get_auto_materialize_paused
from dagster._daemon.types import DaemonStatus

from .errors import GraphenePythonError
from .util import ResolveInfo, non_null_list


class GrapheneRunLauncher(graphene.ObjectType):
    name = graphene.NonNull(graphene.String)

    class Meta:
        name = "RunLauncher"

    def __init__(self, run_launcher):
        super().__init__()
        self._run_launcher = check.inst_param(run_launcher, "run_launcher", RunLauncher)

    def resolve_name(self, _graphene_info: ResolveInfo):
        return self._run_launcher.__class__.__name__


class GrapheneDaemonStatus(graphene.ObjectType):
    daemonType = graphene.NonNull(graphene.String)
    id = graphene.NonNull(graphene.ID)
    required = graphene.NonNull(graphene.Boolean)
    healthy = graphene.Boolean()
    lastHeartbeatTime = graphene.Float()
    lastHeartbeatErrors = non_null_list(GraphenePythonError)

    class Meta:
        name = "DaemonStatus"

    def __init__(self, daemon_status):
        check.inst_param(daemon_status, "daemon_status", DaemonStatus)

        super().__init__(
            daemonType=daemon_status.daemon_type,
            required=daemon_status.required,
            healthy=daemon_status.healthy,
            lastHeartbeatTime=daemon_status.last_heartbeat.timestamp
            if daemon_status.last_heartbeat
            else None,
            lastHeartbeatErrors=[
                GraphenePythonError(error) for error in daemon_status.last_heartbeat.errors
            ]
            if daemon_status.last_heartbeat and daemon_status.last_heartbeat.errors
            else [],
        )

    def resolve_id(self, _graphene_info: ResolveInfo):
        return self.daemonType


class GrapheneDaemonHealth(graphene.ObjectType):
    id = graphene.NonNull(graphene.String)
    daemonStatus = graphene.Field(
        graphene.NonNull(GrapheneDaemonStatus), daemon_type=graphene.Argument(graphene.String)
    )
    allDaemonStatuses = non_null_list(GrapheneDaemonStatus)

    class Meta:
        name = "DaemonHealth"

    def __init__(self, instance):
        super().__init__()
        self._instance = check.inst_param(instance, "instance", DagsterInstance)

    def resolve_id(self, _graphene_info: ResolveInfo):
        return "daemonHealth"

    def resolve_daemonStatus(self, _graphene_info: ResolveInfo, daemon_type):
        check.str_param(daemon_type, "daemon_type")
        return GrapheneDaemonStatus(
            self._instance.get_daemon_statuses(daemon_types=[daemon_type])[daemon_type]
        )

    def resolve_allDaemonStatuses(self, _graphene_info: ResolveInfo):
        return [
            GrapheneDaemonStatus(daemon_status)
            for daemon_status in self._instance.get_daemon_statuses().values()
        ]


class GrapheneConcurrencyLimit(graphene.ObjectType):
    id = graphene.NonNull(graphene.String)
    concurrencyKey = graphene.NonNull(graphene.String)
    limit = graphene.NonNull(graphene.Int)
    numActive = graphene.NonNull(graphene.Int)
    activeRunIds = non_null_list(graphene.String)

    class Meta:
        name = "ConcurrencyLimit"

    def __init__(self, instance: DagsterInstance, concurrencyKey: str):
        super().__init__(id=concurrencyKey, concurrencyKey=concurrencyKey)
        self._instance = instance
        self._concurrency_info: Optional[List[Tuple[str, int]]] = None

    def resolve_limit(self, _graphene_info: ResolveInfo):
        if self._concurrency_info is None:
            self._fetch_concurrency_info()
        return sum([_[1] for _ in self._concurrency_info]) if self._concurrency_info else 0

    def resolve_numActive(self, _graphene_info: ResolveInfo):
        if self._concurrency_info is None:
            self._fetch_concurrency_info()
        return (
            sum([_[1] for _ in self._concurrency_info if _[0] is not None])
            if self._concurrency_info
            else 0
        )

    def resolve_activeRunIds(self, _graphene_info: ResolveInfo):
        if self._concurrency_info is None:
            self._fetch_concurrency_info()

        if not self._concurrency_info:
            return []

        return list(set([run_id for run_id, _ in self._concurrency_info if run_id]))

    def _fetch_concurrency_info(self):
        self._concurrency_info = self._instance.event_log_storage.get_concurrency_info(
            self.concurrencyKey
        )


class GrapheneInstance(graphene.ObjectType):
    id = graphene.NonNull(graphene.String)
    info = graphene.Field(graphene.String)
    runLauncher = graphene.Field(GrapheneRunLauncher)
    runQueuingSupported = graphene.NonNull(graphene.Boolean)
    executablePath = graphene.NonNull(graphene.String)
    daemonHealth = graphene.NonNull(GrapheneDaemonHealth)
    hasInfo = graphene.NonNull(graphene.Boolean)
    hasCapturedLogManager = graphene.NonNull(graphene.Boolean)
    autoMaterializePaused = graphene.NonNull(graphene.Boolean)
    concurrencyLimits = non_null_list(GrapheneConcurrencyLimit)

    class Meta:
        name = "Instance"

    def __init__(self, instance):
        super().__init__()
        self._instance = check.inst_param(instance, "instance", DagsterInstance)

    def resolve_id(self, _graphene_info: ResolveInfo):
        return "Instance"

    def resolve_hasInfo(self, graphene_info: ResolveInfo) -> bool:
        return graphene_info.context.show_instance_config

    def resolve_info(self, graphene_info: ResolveInfo):
        return self._instance.info_str() if graphene_info.context.show_instance_config else None

    def resolve_runLauncher(self, _graphene_info: ResolveInfo):
        return (
            GrapheneRunLauncher(self._instance.run_launcher)
            if self._instance.run_launcher
            else None
        )

    def resolve_runQueuingSupported(self, _graphene_info: ResolveInfo):
        from dagster._core.run_coordinator import QueuedRunCoordinator

        return isinstance(self._instance.run_coordinator, QueuedRunCoordinator)

    def resolve_executablePath(self, _graphene_info: ResolveInfo):
        return sys.executable

    def resolve_daemonHealth(self, _graphene_info: ResolveInfo):
        return GrapheneDaemonHealth(instance=self._instance)

    def resolve_hasCapturedLogManager(self, _graphene_info: ResolveInfo):
        return isinstance(self._instance.compute_log_manager, CapturedLogManager)

    def resolve_autoMaterializePaused(self, _graphene_info: ResolveInfo):
        return get_auto_materialize_paused(self._instance)

    def resolve_concurrencyLimits(self, _graphene_info: ResolveInfo):
        return [
            GrapheneConcurrencyLimit(self._instance, key)
            for key in self._instance.event_log_storage.get_concurrency_limited_keys()
        ]
