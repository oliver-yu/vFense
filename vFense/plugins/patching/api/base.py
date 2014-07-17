import logging
import logging.config
import simplejson as json

from vFense import VFENSE_LOGGING_CONFIG
from vFense.core.api.base import BaseHandler
from vFense.core.decorators import results_message
from vFense.core.api._constants import (
    ApiArguments
)
from vFense.plugins.patching.api._constants import (
    AppApiArguments, AppFilterValues
)
from vFense.core._constants import DefaultQueryValues, SortValues
from vFense.plugins.patching._constants import (
    AppStatuses, CommonSeverityKeys
)
from vFense.core.operations._constants import AgentOperations
from vFense.core.results import Results, ApiResultKeys
from vFense.plugins.patching._db_model import AppsKey
from vFense.core._constants import CommonKeys
from vFense.core.permissions._constants import Permissions
from vFense.core.permissions.decorators import check_permissions
from vFense.plugins.patching.scheduler.manager import (
    AgentAppsJobManager, TagAppsJobManager
)

logging.config.fileConfig(VFENSE_LOGGING_CONFIG)
logger = logging.getLogger('rvapi')

class AppsBaseHandler(BaseHandler):

    def get_and_set_search_arguments(self):
        self.query = (
            self.get_argument(ApiArguments.QUERY, None)
        )
        self.count = (
            int(
                self.get_argument(
                    ApiArguments.COUNT, DefaultQueryValues.COUNT
                )
            )
        )
        self.offset = (
            int(
                self.get_argument(
                    ApiArguments.OFFSET, DefaultQueryValues.OFFSET
                )
            )
        )
        self.sort = (
            self.get_argument(
                ApiArguments.SORT, SortValues.ASC
            )
        )
        self.sort_by = self.get_argument(ApiArguments.SORT_BY, AppsKey.Name)
        self.status = (
            self.get_argument(
                AppApiArguments.STATUS, AppStatuses.AVAILABLE
            )
        )
        self.severity = self.get_argument(AppApiArguments.SEVERITY, None)
        self.vuln = self.get_argument(AppApiArguments.VULN, None)
        self.hidden = self.get_argument(AppApiArguments.HIDDEN, 'false')
        self.output = self.get_argument(AppApiArguments.OUTPUT, 'json')

        if self.hidden == 'false':
            self.hidden = CommonKeys.NO
        else:
            self.hidden = CommonKeys.YES

    def app_search_results(self, search, active_user):
        if (not self.query and not self.severity and not self.vuln
                and self.status):
            results = self.by_status(search)

        elif (not self.query and not self.vuln and self.status
              and self.severity):
            results = self.by_status_and_sev(search)

        elif (not self.query and not self.severity and self.status
              and self.vuln):
            results = self.by_status_and_vuln(search)

        elif (not self.query and not self.status and not self.vuln
              and self.severity):
            results = self.by_severity(search)

        elif not self.vuln and self.severity and self.status and self.query:
            results = self.by_status_and_name_and_sev(search)

        elif self.vuln and self.severity and self.status and self.query:
            results = (
                self.by_status_and_self.name_and_self.sev_and_self.vuln(
                    search
                )
            )

        elif (not self.vuln and not self.severity and self.status
              and self.query):
            results = self.by_status_and_name(search)

        elif not self.severity and self.status and self.query and self.vuln:
            results = self.by_status_and_name_and_vuln(search)

        elif (self.severity and self.query and not self.status
              and not self.vuln):
            results = self.by_sev_and_name(search)

        elif (not self.vuln and not self.severity and not self.status
              and self.query):
            results = self.by_name(search)

        else:
            data = {
                ApiResultKeys.MESSAGE: (
                    'Incorrect arguments while searching for applications'
                )
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).incorrect_arguments(**data)
            )

        return results


    @results_message
    def by_name(self, search):
        results = search.by_name(self.name)
        return results

    @results_message
    def by_status(self, search):
        results = search.by_status(self.status)
        return results

    @results_message
    def by_status_and_sev(self, search):
        results = search.by_status_and_sev(self.status, self.sev)
        return results

    @results_message
    def by_sev_and_name(self, search):
        results = search.by_sev_and_name(self.sev, self.name)
        return results

    @results_message
    def by_status_and_vuln(self, search):
        results = search.by_status_and_vuln(self.status)
        return results

    @results_message
    def by_severity(self, search):
        results = search.by_severity(self.sev)
        return results

    @results_message
    def by_status_and_name_and_sev(self, search):
        results = search.by_status_and_name_and_sev(
            self.status, self.name, self.sev
        )
        return results

    @results_message
    def by_status_and_name_and_sev_and_vuln(self, search):
        results = (
            search.by_status_and_name_and_sev_and_vuln(
                self.status, self.name, self.sev
            )
        )
        return results

    @results_message
    def by_status_and_name(self, search):
        results = search.by_status_and_name(self.status, self.name)
        return results

    @results_message
    def by_status_and_name_and_vuln(self, search):
        results = search.by_status_and_name_and_vuln(self.status, self.name)
        return results

    def get_and_set_install_arguments(self):
        self.run_date = self.arguments.get('run_date', None)
        self.job_name = self.arguments.get('job_name', None)
        self.restart = self.arguments.get('restart', 'none')
        self.cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
        self.net_throttle = self.arguments.get('net_throttle', 0)
        self.time_zone = self.arguments.get('time_zone', None)


    @results_message
    @check_permissions(Permissions.INSTALL)
    def get_install_results(self, operation, install, active_user,
                            job, oper=AgentOperations.INSTALL_OS_APPS):
        return self.get_install_or_uninstall_results(
            operation, install, active_user, job, oper
        )

    @results_message
    @check_permissions(Permissions.INSTALL)
    def get_uninstall_results(self, operation, install, active_user,
                              job, oper=AgentOperations.UNINSTALL):
        return self.get_install_or_uninstall_results(
            operation, install, active_user, job, oper
        )

    def install_or_uninstall(self, operation, install,
                             oper=AgentOperations.INSTALL_OS_APPS):

        results = {}

        if oper == AgentOperations.INSTALL_OS_APPS:
            results = operation.install_os_apps(install)

        elif oper == AgentOperations.INSTALL_CUSTOM_APPS:
            results = operation.install_custom_apps(install)

        elif oper == AgentOperations.INSTALL_SUPPORTED_APPS:
            results = operation.install_supported_apps(install)

        elif oper == AgentOperations.INSTALL_AGENT_UPDATE:
            results = operation.install_supported_apps(install)

        elif oper == AgentOperations.UNINSTALL:
            results = operation.uninstall_apps(install)

        return results


    def schedule_install_or_uninstall(self, job, install,
                                      oper=AgentOperations.INSTALL_OS_APPS):

        results = job.once(
            install, self.run_date, self.job_name, self.time_zone, oper
        )
        return results


    def get_install_or_uninstall_results(self, operation, install,
                                         active_user, job, oper):

        if not self.run_date and not self.job_name:
            results = self.install_or_uninstall(operation, install, oper)

        elif self.run_date and self.job_name:
            if not isinstance(self.run_date, float):
                run_date = float(self.run_date)

            results = (
                self.schedule_install_or_uninstall(
                    job, install, run_date, self.job_name,
                    self.time_zone, oper
                )
            )

        else:
            data = {
                ApiResultKeys.MESSAGE: 'Invalid arguments passed'
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).incorrect_arguments(**data)
            )

        return results