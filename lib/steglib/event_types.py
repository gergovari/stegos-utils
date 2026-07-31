from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class StegEvent:
    """Base class for all structured events."""
    event_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != 'event_type'}

@dataclass
class ActionFailedEvent(StegEvent):
    event_type: str = "action_failed"
    action: Any = None
    error: Any = None
    package: Any = None

@dataclass
class AllReposUpToDateEvent(StegEvent):
    event_type: str = "all_repos_up_to_date"

@dataclass
class BackendErrorEvent(StegEvent):
    event_type: str = "backend_error"
    error: Any = None
    package: Any = None

@dataclass
class BackendErrorDetailsEvent(StegEvent):
    event_type: str = "backend_error_details"
    details: Any = None
    package: Any = None

@dataclass
class BackendLoadingCacheEvent(StegEvent):
    event_type: str = "backend_loading_cache"
    package: Any = None

@dataclass
class BackendLogLineEvent(StegEvent):
    event_type: str = "backend_log_line"
    line: Any = None
    package: Any = None

@dataclass
class BackendLogStderrEvent(StegEvent):
    event_type: str = "backend_log_stderr"
    output: Any = None
    package: Any = None

@dataclass
class BackendLogStdoutEvent(StegEvent):
    event_type: str = "backend_log_stdout"
    output: Any = None
    package: Any = None

@dataclass
class CachingImagesEvent(StegEvent):
    event_type: str = "caching_images"
    package: Any = None

@dataclass
class CascadeReconfigureFailedEvent(StegEvent):
    event_type: str = "cascade_reconfigure_failed"
    error: Any = None
    instance_id: Any = None

@dataclass
class CascadeReconfiguringEvent(StegEvent):
    event_type: str = "cascade_reconfiguring"
    instance_id: Any = None

@dataclass
class CascadeRemovingIntegrationsEvent(StegEvent):
    event_type: str = "cascade_removing_integrations"
    instance_id: Any = None

@dataclass
class CheckingUpdatesEvent(StegEvent):
    event_type: str = "checking_updates"
    repo: Any = None

@dataclass
class CheckingUpgradesEvent(StegEvent):
    event_type: str = "checking_upgrades"
    instance_id: Any = None

@dataclass
class CircularDependencyEvent(StegEvent):
    event_type: str = "circular_dependency"
    package: Any = None

@dataclass
class CleanAbortedEvent(StegEvent):
    event_type: str = "clean_aborted"

@dataclass
class CleanedDirectoriesEvent(StegEvent):
    event_type: str = "cleaned_directories"
    count: Any = None

@dataclass
class CommandFailedEvent(StegEvent):
    event_type: str = "command_failed"
    command: Any = None

@dataclass
class CommandFailedMsgEvent(StegEvent):
    event_type: str = "command_failed_msg"
    command: Any = None

@dataclass
class DependentReconfiguredEvent(StegEvent):
    event_type: str = "dependent_reconfigured"
    instance_id: Any = None

@dataclass
class DependentRestartedEvent(StegEvent):
    event_type: str = "dependent_restarted"
    instance_id: Any = None

@dataclass
class DependentsFoundEvent(StegEvent):
    event_type: str = "dependents_found"
    dependents: Any = None
    provider: Any = None

@dataclass
class DirectoryDeleteFailedEvent(StegEvent):
    event_type: str = "directory_delete_failed"
    error: Any = None
    path: Any = None

@dataclass
class DirectoryDeletedEvent(StegEvent):
    event_type: str = "directory_deleted"
    path: Any = None

@dataclass
class DockerdStartingBackendEvent(StegEvent):
    event_type: str = "dockerd_starting_backend"

@dataclass
class GroupNotFoundEvent(StegEvent):
    event_type: str = "group_not_found"
    group: Any = None

@dataclass
class GroupUpgradedEvent(StegEvent):
    event_type: str = "group_upgraded"
    group: Any = None
    instances: Any = None

@dataclass
class InjectorNoTargetServicesEvent(StegEvent):
    event_type: str = "injector_no_target_services"
    available: Any = None
    targets: Any = None

@dataclass
class InstalledPackagesHeaderEvent(StegEvent):
    event_type: str = "installed_packages_header"
    group: Any = None

@dataclass
class InstancePurgedEvent(StegEvent):
    event_type: str = "instance_purged"
    instance_id: Any = None

@dataclass
class InstanceUninstalledEvent(StegEvent):
    event_type: str = "instance_uninstalled"
    instance_id: Any = None

@dataclass
class InstanceUpToDateEvent(StegEvent):
    event_type: str = "instance_up_to_date"
    instance_id: Any = None

@dataclass
class InstanceUpgradedEvent(StegEvent):
    event_type: str = "instance_upgraded"
    instance_id: Any = None

@dataclass
class IntegrationDisabledMissingProvidersEvent(StegEvent):
    event_type: str = "integration_disabled_missing_providers"
    capability: Any = None
    package: Any = None

@dataclass
class IntegrationMissingEvent(StegEvent):
    event_type: str = "integration_missing"
    capability: Any = None
    consumer: Any = None
    missing_provider: Any = None

@dataclass
class IntegrationRemovedNoLongerRequiredEvent(StegEvent):
    event_type: str = "integration_removed_no_longer_required"
    capability: Any = None
    package: Any = None

@dataclass
class LogDebugEvent(StegEvent):
    event_type: str = "log_debug"
    message: Any = None

@dataclass
class LogErrorEvent(StegEvent):
    event_type: str = "log_error"
    message: Any = None

@dataclass
class LogExceptionEvent(StegEvent):
    event_type: str = "log_exception"
    message: Any = None

@dataclass
class LogInfoEvent(StegEvent):
    event_type: str = "log_info"
    force: Any = None
    message: Any = None

@dataclass
class LogWarningEvent(StegEvent):
    event_type: str = "log_warning"
    message: Any = None

@dataclass
class LogsCommandFailedEvent(StegEvent):
    event_type: str = "logs_command_failed"
    exit_code: Any = None
    package: Any = None

@dataclass
class MissingComposeFileEvent(StegEvent):
    event_type: str = "missing_compose_file"
    package: Any = None
    path: Any = None

@dataclass
class NetworkPrecreateErrorEvent(StegEvent):
    event_type: str = "network_precreate_error"
    error: Any = None

@dataclass
class NetworkPrecreateFailedEvent(StegEvent):
    event_type: str = "network_precreate_failed"
    error: Any = None
    package: Any = None

@dataclass
class NoDeployerBackendEvent(StegEvent):
    event_type: str = "no_deployer_backend"
    package: Any = None

@dataclass
class NoInstancesUpgradedEvent(StegEvent):
    event_type: str = "no_instances_upgraded"
    group: Any = None

@dataclass
class NoPackagesEvent(StegEvent):
    event_type: str = "no_packages"

@dataclass
class NoPackagesInstalledEvent(StegEvent):
    event_type: str = "no_packages_installed"
    group: Any = None

@dataclass
class NoUnmanagedDirectoriesEvent(StegEvent):
    event_type: str = "no_unmanaged_directories"
    group: Any = None

@dataclass
class PackageInstalledEvent(StegEvent):
    event_type: str = "package_installed"
    instance_id: Any = None
    package: Any = None

@dataclass
class PackageListedEvent(StegEvent):
    event_type: str = "package_listed"
    instance_id: Any = None
    package: Any = None

@dataclass
class ReconfigureFailedEvent(StegEvent):
    event_type: str = "reconfigure_failed"
    instance_id: Any = None
    package: Any = None

@dataclass
class ReconfiguredEvent(StegEvent):
    event_type: str = "reconfigured"
    count: Any = None
    group: Any = None

@dataclass
class RemovingInstanceEvent(StegEvent):
    event_type: str = "removing_instance"
    instance_id: Any = None

@dataclass
class RepoUpToDateEvent(StegEvent):
    event_type: str = "repo_up_to_date"
    repo: Any = None

@dataclass
class RepoUpdatedEvent(StegEvent):
    event_type: str = "repo_updated"
    repo: Any = None

@dataclass
class ReposUpdatedEvent(StegEvent):
    event_type: str = "repos_updated"
    repos: Any = None

@dataclass
class RestartingDependentEvent(StegEvent):
    event_type: str = "restarting_dependent"
    instance_id: Any = None

@dataclass
class SkippingActionEvent(StegEvent):
    event_type: str = "skipping_action"
    action: Any = None
    package: Any = None
    reason: Any = None

@dataclass
class SkippingRepoEvent(StegEvent):
    event_type: str = "skipping_repo"
    repo: Any = None

@dataclass
class StartingPackageEvent(StegEvent):
    event_type: str = "starting_package"
    package: Any = None

@dataclass
class StopFailedEvent(StegEvent):
    event_type: str = "stop_failed"
    instance_id: Any = None

@dataclass
class StoppingInstanceEvent(StegEvent):
    event_type: str = "stopping_instance"
    instance_id: Any = None

@dataclass
class StoppingPackageEvent(StegEvent):
    event_type: str = "stopping_package"
    package: Any = None

@dataclass
class UnknownDeployerEvent(StegEvent):
    event_type: str = "unknown_deployer"
    deployer: Any = None
    package: Any = None

@dataclass
class UnmanagedDirectoriesHeaderEvent(StegEvent):
    event_type: str = "unmanaged_directories_header"

@dataclass
class UnmanagedDirectoryEvent(StegEvent):
    event_type: str = "unmanaged_directory"
    path: Any = None

@dataclass
class UpgradeFailedEvent(StegEvent):
    event_type: str = "upgrade_failed"
    error: Any = None
    instance_id: Any = None
    package: Any = None

@dataclass
class UpgradingAndRestartingEvent(StegEvent):
    event_type: str = "upgrading_and_restarting"
    instance_id: Any = None
