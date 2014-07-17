import logging
import logging.config
from datetime import datetime
import simplejson as json

from vFense.core.api.base import BaseHandler
from vFense import VFENSE_LOGGING_CONFIG

#from vFense.scheduler.jobManager import schedule_once
from vFense.plugins.patching.scheduler.manager import (
    AgentAppsJobManager, TagAppsJobManager
)
from vFense.plugins.patching.operations._constants import InstallKeys
from vFense.plugins.patching.operations import Install

from vFense.plugins.patching.search.search_by_tagid import (
    RetrieveAppsByTagId
)

from vFense.plugins.patching.search.search_by_agentid import (
    RetrieveAppsByAgentId
)

from vFense.plugins.patching.search.search_by_appid import (
    RetrieveAgentsByAppId
)

from vFense.plugins.patching.search.search import (
    RetrieveApps
)

from vFense.core.agent._db_model import AgentKeys
from vFense.plugins.patching._db_model import AppsKey
from vFense.core._constants import CommonKeys
from vFense.core.permissions._constants import Permissions
from vFense.core.permissions.decorators import check_permissions
from vFense.core.results import Results, ApiResultKeys

from vFense.plugins.patching._db import update_app_data_by_app_id
from vFense.plugins.patching.operations.store_operations import StorePatchingOperation
from vFense.plugins.patching.patching import toggle_hidden_status
from vFense.core.decorators import (
    authenticated_request, convert_json_to_arguments, results_message
)

from vFense.core.user import UserKeys
from vFense.core.user.manager import UserManager
from vFense.core.api._constants import (
    ApiArguments, Outputs, ContentTypes
)
from vFense.core._constants import DefaultQueryValues, SortValues
from vFense.plugins.patching.api._constants import (
    AppApiArguments, AppFilterValues
)
from vFense.plugins.patching._constants import (
    AppStatuses, CommonSeverityKeys
)

from vFense.utils.output import tableify
from vFense.utils.output import csvify

logging.config.fileConfig(VFENSE_LOGGING_CONFIG)
logger = logging.getLogger('rvapi')


class AgentIdOsAppsHandler(BaseHandler):
    @authenticated_request
    def get(self, agent_id):
        active_user = self.get_current_user().encode('utf-8')
        query = (
            self.get_argument(ApiArguments.QUERY, None)
        )
        count = (
            int(
                self.get_argument(
                    ApiArguments.COUNT, DefaultQueryValues.COUNT
                )
            )
        )
        offset = (
            int(
                self.get_argument(
                    ApiArguments.OFFSET, DefaultQueryValues.OFFSET
                )
            )
        )
        sort = (
            self.get_argument(
                ApiArguments.SORT, SortValues.ASC
            )
        )
        sort_by = self.get_argument(ApiArguments.SORT_BY, AppsKey.Name)
        status = (
            self.get_argument(
                AppApiArguments.STATUS, AppStatuses.AVAILABLE
            )
        )
        severity = self.get_argument(AppApiArguments.SEVERITY, None)
        vuln = self.get_argument(AppApiArguments.VULN, None)
        hidden = self.get_argument(AppApiArguments.HIDDEN, 'false')
        output = self.get_argument(AppApiArguments.OUTPUT, 'json')
        if hidden == 'false':
            hidden = CommonKeys.NO
        else:
            hidden = CommonKeys.YES
        search = (
            RetrieveAppsByAgentId(
                agent_id, count, offset,
                sort, sort_by, show_hidden=hidden
            )
        )
        if not query and not severity and not vuln and status:
            results = self.by_status(search, status)

        elif not query and not vuln and status and severity:
            results = self.by_status_and_sev(search, status, severity)

        elif not query and not severity and status and vuln:
            results = self.by_status_and_vuln(search, status)

        elif not query and not status and not vuln and severity:
            results = self.by_severity(search, severity)

        elif not vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev(
                    search, status, query, severity
                )
            )

        elif vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev_and_vuln(
                    search, status, query, severity
                )
            )

        elif not vuln and not severity and status and query:
            results = (
                self.by_status_and_name(search, status, query)
            )

        elif not severity and status and query and vuln:
            results = (
                self.by_status_and_name_and_vuln(search, status, query)
            )

        elif severity and query and not status and not vuln:
            results = (
                self.by_sev_and_name(
                    search, severity, query
                )
            )

        elif not vuln and not severity and not status and query:
            results = self.by_name(search, query)

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

        self.set_status(results['http_status'])
        self.modified_output(results, output, 'apps')


    @results_message
    def by_name(self, search, name):
        results = search.by_name(name)
        return results

    @results_message
    def by_status(self, search, status):
        results = search.by_status(status)
        return results

    @results_message
    def by_status_and_sev(self, search, status, sev):
        results = search.by_status_and_sev(status, sev)
        return results

    @results_message
    def by_sev_and_name(self, search, sev, name):
        results = search.by_sev_and_name(sev, name)
        return results

    @results_message
    def by_status_and_vuln(self, search, status):
        results = search.by_status_and_vuln(status)
        return results

    @results_message
    def by_severity(self, search, sev):
        results = search.by_severity(sev)
        return results

    @results_message
    def by_status_and_name_and_sev(self, search, status, name, sev):
        results = search.by_status_and_name_and_sev(status, name, sev)
        return results

    @results_message
    def by_status_and_name_and_sev_and_vuln(self, search, status, name, sev):
        results = (
            search.by_status_and_name_and_sev_and_vuln(status, name, sev)
        )
        return results

    @results_message
    def by_status_and_name(self, search, status, name):
        results = search.by_status_and_name(status, name)
        return results

    @results_message
    def by_status_and_name_and_vuln(self, search, status, name):
        results = search.by_status_and_name_and_vuln(status, name)
        return results


    @authenticated_request
    @convert_json_to_arguments
    def put(self, agent_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        try:
            app_ids = self.arguments.get('app_ids')
            run_date = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            time_zone = self.arguments.get('time_zone', None)
            install = (
                Install(
                    app_ids, [agent_id], user_name=active_user,
                    view_name=active_view, restart=restart,
                    net_throttle=net_throttle, cpu_throttle=cpu_throttle
                )
            )
            if not run_date and not job_name and app_ids:
                operation = (
                    StorePatchingOperation(active_user, active_view)
                )
                results = self.install(operation, install)
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif run_date and job_name and app_ids:
                if not isinstance(run_date, float):
                    run_date = float(run_date)

                results = (
                    self.schedule_install(
                        install, run_date, job_name, time_zone
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            else:
                data = {
                    ApiResultKeys.MESSAGE: (
                        'Invalid arguments passed for agent {0}'
                        .format(agent_id)
                    )
                }
                results = (
                    Results(
                        active_user, self.request.uri, self.request.method
                    ).incorrect_arguments(**data)
                )

        except Exception as e:
            data = {
                ApiResultKeys.MESSAGE: (
                    'Installing applications on agent {0} broke: {1}'
                    .format(agent_id, e)
                )
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).something_broke(**data)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.INSTALL)
    def install(self, operation, install):
        logger.info(install.to_dict())
        results = operation.install_os_apps(install)
        return results

    @results_message
    @check_permissions(Permissions.INSTALL)
    def schedule_install(self, install, run_date, job_name, time_zone):
        sched = self.application.scheduler
        job = AgentAppsJobManager(sched, install.view_name)
        results = job.once(
            install, run_date, job_name, time_zone
        )
        return results


    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.UNINSTALL)
    def delete(self, agent_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        try:
            app_ids = self.arguments.get('app_ids')
            run_date = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            time_zone = self.arguments.get('time_zone', None)
            install = (
                Install(
                    app_ids, [agent_id], user_name=active_user,
                    view_name=active_view, restart=restart,
                    net_throttle=net_throttle, cpu_throttle=cpu_throttle
                )
            )
            if not run_date and not job_name and app_ids:
                operation = (
                    StorePatchingOperation(active_user, active_view)
                )
                results = self.uninstall(operation, install)
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif run_date and job_name and app_ids:
                if not isinstance(run_date, float):
                    run_date = float(run_date)

                results = (
                    self.schedule_uninstall(
                        install, run_date, job_name, time_zone
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            else:
                data = {
                    ApiResultKeys.MESSAGE: (
                        'Invalid arguments passed for agent {0}'
                        .format(agent_id)
                    )
                }
                results = (
                    Results(
                        active_user, self.request.uri, self.request.method
                    ).incorrect_arguments(**data)
                )


        except Exception as e:
            data = {
                ApiResultKeys.MESSAGE: (
                    'Uninstalling applications on agent {0} broke: {1}'
                    .format(agent_id, e)
                )
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).something_broke(**data)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.INSTALL)
    def uninstall(self, operation, install):
        logger.info(install.to_dict())
        results = operation.uninstall_apps(install)
        return results

    @results_message
    @check_permissions(Permissions.INSTALL)
    def schedule_uninstall(self, install, run_date, job_name, time_zone):
        sched = self.application.scheduler
        job = AgentAppsJobManager(sched, install.view_name)
        results = job.once(
            install, run_date, job_name, time_zone
        )
        return results



class TagIdOsAppsHandler(BaseHandler):
    @authenticated_request
    def get(self, tag_id):
        active_user = self.get_current_user().encode('utf-8')
        query = (
            self.get_argument(ApiArguments.QUERY, None)
        )
        count = (
            int(
                self.get_argument(
                    ApiArguments.COUNT, DefaultQueryValues.COUNT
                )
            )
        )
        offset = (
            int(
                self.get_argument(
                    ApiArguments.OFFSET, DefaultQueryValues.OFFSET
                )
            )
        )
        sort = (
            self.get_argument(
                ApiArguments.SORT, SortValues.ASC
            )
        )
        sort_by = self.get_argument(ApiArguments.SORT_BY, AppsKey.Name)
        status = (
            self.get_argument(
                AppApiArguments.STATUS, AppStatuses.AVAILABLE
            )
        )
        severity = self.get_argument(AppApiArguments.SEVERITY, None)
        vuln = self.get_argument(AppApiArguments.VULN, None)
        hidden = self.get_argument(AppApiArguments.HIDDEN, 'false')
        output = self.get_argument(ApiArguments.OUTPUT, 'json')

        if hidden == 'false':
            hidden = CommonKeys.NO
        else:
            hidden = CommonKeys.YES
        search = (
            RetrieveAppsByTagId(
                tag_id, count, offset,
                sort, sort_by, show_hidden=hidden
            )
        )
        if not query and not severity and not vuln and status:
            results = self.by_status(search, status)

        elif not query and not vuln and status and severity:
            results = self.by_status_and_sev(search, status, severity)

        elif not query and not severity and status and vuln:
            results = self.by_status_and_vuln(search, status)

        elif not query and not status and not vuln and severity:
            results = self.by_severity(search, severity)

        elif not vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev(
                    search, query, status, severity
                )
            )

        elif vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev_and_vuln(
                    search, query, status, severity
                )
            )

        elif not vuln and not severity and status and query:
            results = (
                self.by_status_and_name(search, query, status)
            )

        elif not severity and status and query and vuln:
            results = (
                self.by_status_and_name_and_vuln(search, query, status)
            )

        elif severity and query and not status and not vuln:
            results = (
                self.by_sev_and_name(
                    search, query, severity
                )
            )

        elif not vuln and not severity and not status and query:
            results = self.by_name(search, query)

        else:
            data = {
                ApiResultKeys.MESSAGE: (
                    'Incorrect arguments on tag {0}'.format(tag_id)
                )
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).incorrect_arguments(**data)
            )
        self.set_status(results['http_status'])
        self.modified_output(results, output, 'apps')

    @results_message
    def by_name(self, search, name):
        results = search.by_name(name)
        return results

    @results_message
    def by_status(self, search, status):
        results = search.by_status(status)
        return results

    @results_message
    def by_status_and_sev(self, search, status, sev):
        results = search.by_status_and_sev(status, sev)
        return results

    @results_message
    def by_sev_and_name(self, search, sev, name):
        results = search.by_sev_and_name(sev, name)
        return results

    @results_message
    def by_status_and_vuln(self, search, status):
        results = search.by_status_and_vuln(status)
        return results

    @results_message
    def by_severity(self, search, sev):
        results = search.by_severity(sev)
        return results

    @results_message
    def by_status_and_name_and_sev(self, search, status, name, sev):
        results = search.by_status_and_name_and_sev(status, name, sev)
        return results

    @results_message
    def by_status_and_name_and_sev_and_vuln(self, search, status, name, sev):
        results = (
            search.by_status_and_name_and_sev_and_vuln(status, name, sev)
        )
        return results

    @results_message
    def by_status_and_name(self, search, status, name):
        results = search.by_status_and_name(status, name)
        return results

    @results_message
    def by_status_and_name_and_vuln(self, search, status, name):
        results = search.by_status_and_name_and_vuln(status, name)
        return results

    @authenticated_request
    @convert_json_to_arguments
    def put(self, tag_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        try:
            app_ids = self.arguments.get('app_ids')
            run_date = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            time_zone = self.arguments.get('time_zone', None)
            install = (
                Install(
                    app_ids, [], tag_id, user_name=active_user,
                    view_name=active_view, restart=restart,
                    net_throttle=net_throttle, cpu_throttle=cpu_throttle
                )
            )
            if not run_date and not job_name and app_ids:
                operation = (
                    StorePatchingOperation(active_user, active_view)
                )
                results = self.install(operation, install)
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif run_date and job_name and app_ids:
                if not isinstance(run_date, float):
                    run_date = float(run_date)

                results = (
                    self.schedule_install(
                        install, run_date, job_name, time_zone
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            else:
                data = {
                    ApiResultKeys.MESSAGE: (
                        'Invalid arguments passed for tag {0}'
                        .format(tag_id)
                    )
                }
                results = (
                    Results(
                        active_user, self.request.uri, self.request.method
                    ).incorrect_arguments(**data)
                )

        except Exception as e:
            data = {
                ApiResultKeys.MESSAGE: (
                    'Installing applications on tag {0} broke: {1}'
                    .format(tag_id, e)
                )
            }
            results = (
                Results(
                    active_user, self.request.uri, self.request.method
                ).something_broke(**data)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))


    @results_message
    @check_permissions(Permissions.INSTALL)
    def install(self, operation, install):
        logger.info(install.to_dict())
        results = operation.install_os_apps(install)
        return results

    @results_message
    @check_permissions(Permissions.INSTALL)
    def schedule_install(self, install, run_date, job_name, time_zone):
        sched = self.application.scheduler
        job = TagAppsJobManager(sched, install.view_name)
        results = job.once(
            install, run_date, job_name, time_zone
        )
        return results


    @authenticated_request
    @convert_json_to_arguments
    def delete(self, tag_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            app_ids = self.arguments.get('app_ids')
            run_date = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            time_zone = self.arguments.get('time_zone', None)
            install = (
                Install(
                    app_ids, [], tag_id, user_name=active_user,
                    view_name=active_view, restart=restart,
                    net_throttle=net_throttle, cpu_throttle=cpu_throttle
                )
            )
            if not run_date and not job_name and app_ids:
                operation = (
                    StorePatchingOperation(active_user, active_view)
                )
                results = self.install(operation, install)
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif run_date and job_name and app_ids:
                if not isinstance(run_date, float):
                    run_date = float(run_date)

                results = (
                    self.schedule_install(
                        install, run_date, job_name, time_zone
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            else:
                data = {
                    ApiResultKeys.MESSAGE: (
                        'Invalid arguments passed for tag {0}'
                        .format(tag_id)
                    )
                }
                results = (
                    Results(
                        active_user, self.request.uri, self.request.method
                    ).incorrect_arguments(**data)
                )

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(tag_id, 'install_os_apps', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.INSTALL)
    def uninstall(self, operation, install):
        logger.info(install.to_dict())
        results = operation.uninstall_apps(install)
        return results

    @results_message
    @check_permissions(Permissions.INSTALL)
    def schedule_uninstall(self, install, run_date, job_name, time_zone):
        sched = self.application.scheduler
        job = AgentAppsJobManager(sched, install.view_name)
        results = job.once(
            install, run_date, job_name, time_zone
        )
        return results


class AppIdOsAppsHandler(BaseHandler):
    @authenticated_request
    def get(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        output = self.get_argument(ApiArguments.OUTPUT, 'json')
        search = RetrieveApps(active_view)
        results = self.by_id(search, app_id)
        self.set_status(results['http_status'])
        self.modified_output(results, output, 'app')

    @results_message
    def by_id(self, search, app_id):
        results = search.by_id(app_id)
        return results

    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.ADMINISTRATOR)
    def post(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            severity = self.arguments.get('severity').capitalize()
            if severity in CommonSeverityKeys.ValidRvSeverities:
                sev_data = (
                    {
                        AppsKey.RvSeverity: severity
                    }
                )
                update_app_data_by_app_id(
                    app_id, sev_data
                )
                results = (
                    Results(
                        active_user, uri, method
                    ).object_updated(app_id, 'app severity', [sev_data])
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            else:
                results = (
                    PackageResults(
                        active_user, uri, method
                    ).invalid_severity(severity)
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_id, 'update_severity', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.INSTALL)
    def put(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent_ids = self.arguments.get('agent_ids')
            epoch_time = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            if not epoch_time and not job_name and agent_ids:
                operation = (
                    StorePatchingOperation(
                        active_user, active_view
                    )
                )
                results = (
                    operation.install_os_apps(
                        [app_id], cpu_throttle,
                        net_throttle, restart,
                        agentids=agent_ids
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif epoch_time and job_name and agent_ids:
                date_time = datetime.fromtimestamp(int(epoch_time))
                sched = self.application.scheduler
                job = (
                    {
                        'cpu_throttle': cpu_throttle,
                        'net_throttle': net_throttle,
                        'restart': restart,
                        'pkg_type': 'system_apps',
                        'app_ids': [app_id]
                    }
                )
                add_install_job = (
                    schedule_once(
                        sched, active_view, active_user,
                        agent_ids=[agent_ids], operation='install',
                        name=job_name, date=date_time, uri=uri,
                        method=method, job_extra=job
                    )
                )
                result = add_install_job
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(result))

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_id, 'install_os_apps', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.UNINSTALL)
    def delete(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent_ids = self.arguments.get('agent_ids')
            epoch_time = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            if not epoch_time and not job_name and app_id:
                operation = (
                    StorePatchingOperation(
                        active_user, active_view
                    )
                )
                results = (
                    operation.uninstall_apps(
                        [app_id], cpu_throttle,
                        net_throttle, restart,
                        agentids=agent_ids
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif epoch_time and job_name and agent_ids:
                date_time = datetime.fromtimestamp(int(epoch_time))
                sched = self.application.scheduler
                job = (
                    {
                        'restart': restart,
                        'pkg_type': 'system_apps',
                        'app_ids': [app_id]
                    }
                )
                add_uninstall_job = (
                    schedule_once(
                        sched, active_view, active_user,
                        agent_ids=[agent_ids], operation='uninstall',
                        name=job_name, date=date_time, uri=uri,
                        method=method, job_extra=job
                    )
                )
                result = add_uninstall_job
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(result))

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_id, 'install_os_apps', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))


class GetAgentsByAppIdHandler(BaseHandler):
    @authenticated_request
    def get(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        uri = self.request.uri
        http_method = self.request.method
        query = (
            self.get_argument(ApiArguments.QUERY, None)
        )
        count = (
            int(
                self.get_argument(
                    ApiArguments.COUNT, DefaultQueryValues.COUNT
                )
            )
        )
        offset = (
            int(
                self.get_argument(
                    ApiArguments.OFFSET, DefaultQueryValues.OFFSET
                )
            )
        )
        sort = (
            self.get_argument(
                ApiArguments.SORT, SortValues.ASC
            )
        )
        sort_by = (
            self.get_argument(ApiArguments.SORT_BY, AgentKeys.ComputerName)
        )
        status = (
            self.get_argument(
                AppApiArguments.STATUS, AppStatuses.AVAILABLE
            )
        )
        search = (
            RetrieveAgentsByAppId(app_id, count, offset, sort, sort_by)
        )
        output = self.get_argument(ApiArguments.OUTPUT, 'json')

        if status and not query:
            results = self.by_status(search, status)

        elif status and query:
            results = self.by_status_and_name(search, status, query)

        elif query and not status:
            results = self.by_name(search, query)

        else:
            results = (
                Results(
                    active_user, uri, http_method
                ).incorrect_arguments()
            )

        self.set_status(results['http_status'])
        self.modified_output(results, output, 'apps')

    @results_message
    def by_status(self, search, status):
        results = search.by_status(status)
        return results

    @results_message
    def by_name(self, search, name):
        results = search.by_name(name)
        return results

    @results_message
    def by_status_and_name(self, search, status, name):
        results = search.by_status_and_name(status, name)
        return results


    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.INSTALL)
    def put(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent_ids = self.arguments.get('agent_ids')
            epoch_time = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            if not epoch_time and not job_name and agent_ids:
                operation = StorePatchingOperation(active_user, active_view)
                results = (
                    self.install(
                        operation, app_id, agent_ids,
                        cpu_throttle, net_throttle, restart
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif epoch_time and job_name and agent_ids:
                date_time = datetime.fromtimestamp(int(epoch_time))
                sched = self.application.scheduler
                job = (
                    {
                        'cpu_throttle': cpu_throttle,
                        'net_throttle': net_throttle,
                        'restart': restart,
                        'pkg_type': 'system_apps',
                        'app_ids': [app_id]
                    }
                )
                add_install_job = (
                    schedule_once(
                        sched, active_view, active_user,
                        agent_ids=agent_ids, operation='install',
                        name=job_name, date=date_time, uri=uri,
                        method=method, job_extra=job
                    )
                )
                result = add_install_job
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(result))

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_id, 'install_os_apps', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.INSTALL)
    def install(self, operation, app_id, agent_ids,
                cpu_throttle, net_throttle, restart):
        results = (
            operation.install_os_apps(
                [app_id], cpu_throttle, net_throttle,
                restart,agentids=agent_ids
            )
        )
        return results

    @results_message
    @check_permissions(Permissions.INSTALL)
    def schedule_install(self, epoch_time, job_name, app_id, agent_ids,
                         cpu_throttle, net_throttle, restart):
        date_time = datetime.fromtimestamp(int(epoch_time))
        sched = self.application.scheduler
        job = (
            {
                'cpu_throttle': cpu_throttle,
                'net_throttle': net_throttle,
                'restart': restart,
                'pkg_type': 'system_apps',
                'app_ids': [app_id]
            }
        )
        results = (
            schedule_once(
                sched, active_view, active_user, agent_ids=agent_ids,
                operation='install', name=job_name, date=date_time, uri=uri,
                method=method, job_extra=job
            )
        )
        return results



    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.UNINSTALL)
    def delete(self, app_id):
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent_ids = self.arguments.get('agent_ids')
            epoch_time = self.arguments.get('run_date', None)
            job_name = self.arguments.get('job_name', None)
            restart = self.arguments.get('restart', 'none')
            cpu_throttle = self.arguments.get('cpu_throttle', 'normal')
            net_throttle = self.arguments.get('net_throttle', 0)
            if not epoch_time and not job_name and app_id:
                operation = (
                    StorePatchingOperation(
                        active_user, active_view
                    )
                )
                results = (
                    operation.uninstall_apps(
                        [app_id], cpu_throttle,
                        net_throttle, restart,
                        agentids=agent_ids
                    )
                )
                self.set_status(results['http_status'])
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(results, indent=4))

            elif epoch_time and job_name and agent_ids:
                date_time = datetime.fromtimestamp(int(epoch_time))
                sched = self.application.scheduler
                job = (
                    {
                        'restart': restart,
                        'pkg_type': 'system_apps',
                        'app_ids': [app_id]
                    }
                )
                add_uninstall_job = (
                    schedule_once(
                        sched, active_view, active_user,
                        agent_ids=agent_ids, operation='uninstall',
                        name=job_name, date=date_time, uri=uri,
                        method=method, job_extra=job
                    )
                )
                result = add_uninstall_job
                self.set_header('Content-Type', 'application/json')
                self.write(json.dumps(result))

        except Exception as e:
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_id, 'install_os_apps', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))


class OsAppsHandler(BaseHandler):
    @authenticated_request
    def get(self):
        uri = self.request.uri
        http_method = self.request.method
        active_user = self.get_current_user().encode('utf-8')
        active_view = (
            UserManager(active_user).get_attribute(UserKeys.CurrentView)
        )
        query = (
            self.get_argument(ApiArguments.QUERY, None)
        )
        count = (
            int(
                self.get_argument(
                    ApiArguments.COUNT, DefaultQueryValues.COUNT
                )
            )
        )
        offset = (
            int(
                self.get_argument(
                    ApiArguments.OFFSET, DefaultQueryValues.OFFSET
                )
            )
        )
        sort = (
            self.get_argument(
                ApiArguments.SORT, SortValues.ASC
            )
        )
        sort_by = self.get_argument(ApiArguments.SORT_BY, AppsKey.Name)
        status = (
            self.get_argument(
                AppApiArguments.STATUS, AppStatuses.AVAILABLE
            )
        )
        severity = self.get_argument(AppApiArguments.SEVERITY, None)
        vuln = self.get_argument(AppApiArguments.VULN, None)
        hidden = self.get_argument(AppApiArguments.HIDDEN, 'false')
        output = self.get_argument(ApiArguments.OUTPUT, 'json')

        if hidden == 'false':
            hidden = CommonKeys.NO
        else:
            hidden = CommonKeys.YES

        if sort_by == AppFilterValues.SEVERITY:
            sort_by = AppsKey.RvSeverity

        search = (
            RetrieveApps(
                active_view, count, offset,
                sort, sort_by, show_hidden=hidden
            )
        )
        if not query and not severity and not vuln and not status:
            results = self.all(search)

        if not query and not severity and not vuln and status:
            results = self.by_status(search, status)

        elif not query and not vuln and status and severity:
            results = self.by_status_and_sev(search, status, severity)

        elif not query and not severity and status and vuln:
            results = self.by_status_and_vuln(search, status)

        elif not query and not status and not vuln and severity:
            results = self.by_severity(search, severity)

        elif not vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev(
                    search, query, status, severity
                )
            )

        elif vuln and severity and status and query:
            results = (
                self.by_status_and_name_and_sev_and_vuln(
                    search, query, status, severity
                )
            )

        elif not vuln and not severity and status and query:
            results = (
                self.by_status_and_name(search, query, status)
            )

        elif not severity and status and query and vuln:
            results = (
                self.by_status_and_name_and_vuln(search, query, status)
            )

        elif severity and query and not status and not vuln:
            results = (
                self.by_sev_and_name(
                    search, query, severity
                )
            )

        elif not vuln and not severity and not status and query:
            results = self.by_name(search, query)

        else:
            results = (
                Results(
                    active_user, uri, http_method
                ).incorrect_arguments()
            )

        self.set_status(results['http_status'])
        self.modified_output(results, output, 'apps')

    @results_message
    def all(self, search):
        results = search.all()
        return results

    @results_message
    def by_name(self, search, name):
        results = search.by_name(name)
        return results

    @results_message
    def by_status(self, search, status):
        results = search.by_status(status)
        return results

    @results_message
    def by_status_and_sev(self, search, status, sev):
        results = search.by_status_and_sev(status, sev)
        return results

    @results_message
    def by_sev_and_name(self, search, sev, name):
        results = search.by_sev_and_name(sev, name)
        return results

    @results_message
    def by_status_and_vuln(self, search, status):
        results = search.by_status_and_vuln(status)
        return results

    @results_message
    def by_severity(self, search, sev):
        results = search.by_severity(sev)
        return results

    @results_message
    def by_status_and_name_and_sev(self, search, status, name, sev):
        results = search.by_status_and_name_and_sev(status, name, sev)
        return results

    @results_message
    def by_status_and_name_and_sev_and_vuln(self, search, status, name, sev):
        results = (
            search.by_status_and_name_and_sev_and_vuln(status, name, sev)
        )
        return results

    @results_message
    def by_status_and_name(self, search, status, name):
        results = search.by_status_and_name(status, name)
        return results

    @results_message
    def by_status_and_name_and_vuln(self, search, status, name):
        results = search.by_status_and_name_and_vuln(status, name)
        return results

    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.ADMINISTRATOR)
    def put(self):
        active_user = self.get_current_user().encode('utf-8')
        uri = self.request.uri
        method = self.request.method

        try:
            app_ids = self.arguments.get('app_ids')
            toggle = self.arguments.get('hide', 'toggle')
            results = (
                toggle_hidden_status(
                    app_ids, toggle,
                    active_user=active_user, uri=uri, method=method
                )
            )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            logger.exception(e)
            results = (
                Results(
                    active_user, uri, method
                ).something_broke(app_ids, 'toggle hidden on os_apps', e)
            )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))
