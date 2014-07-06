import simplejson as json

import logging
import logging.config
from vFense import VFENSE_LOGGING_CONFIG

from vFense.core.api.base import BaseHandler
from vFense.core.api._constants import (
    ApiArguments, AgentApiArguments, ApiValues, TagApiArguments
)
from vFense.core.permissions._constants import Permissions
from vFense.core.permissions.decorators import check_permissions
from vFense.core.operations.decorators import log_operation
from vFense.core.operations._admin_constants import AdminActions
from vFense.core.operations._constants import vFenseObjects
from vFense.core.agent._db_model import AgentKeys
from vFense.core.user._db_model import UserKeys
from vFense.core.user.manager import UserManager
from vFense.core.agent.search.search import RetrieveAgents
from vFense.core.agent.manager import AgentManager
from vFense.core.tag import Tag
from vFense.core.tag.manager import TagManager
from vFense.core.view.manager import ViewManager
from vFense.core.view._db import token_exist_in_current
from vFense.core.queue.uris import get_result_uris
from vFense.result.error_messages import GenericResults
from vFense.result.results import Results

from vFense.plugins.patching.operations.store_operations import (
    StorePatchingOperation
)
from vFense.core.agent.operations.store_agent_operations import (
    StoreAgentOperations
)
from vFense.core.agent.agents import (
    get_supported_os_codes, get_supported_os_strings, get_environments
)

from vFense.core.decorators import (
    authenticated_request, convert_json_to_arguments, results_message
)
from vFense.result._constants import ApiResultKeys
from vFense.result.status_codes import (
    GenericCodes, GenericFailureCodes, AgentCodes, AgentFailureCodes,
    ViewCodes
)

logging.config.fileConfig(VFENSE_LOGGING_CONFIG)
logger = logging.getLogger('rvapi')


class AgentResultURIs(BaseHandler):
    @authenticated_request
    def get(self, agent_id):
        username = self.get_current_user()
        uri = self.request.uri
        method = self.request.method
        try:
            results = get_result_uris(agent_id, username, uri, method)
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            status = (
                GenericResults(
                    username, uri, method
                ).something_broke('uris', 'refresh_response_uris', e)
            )
            logger.exception(e)
            self.write(json.dumps(status, indent=4))


class FetchValidEnvironments(BaseHandler):
    @authenticated_request
    def get(self):
        username = self.get_current_user().encode('utf-8')
        view_name = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            data = get_environments(view_name)
            results = (
                GenericResults(
                    username, uri, method
                ).information_retrieved(data, len(data))
            )
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke('Get OS Codes', 'Agent', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))


class FetchSupportedOperatingSystems(BaseHandler):
    @authenticated_request
    def get(self):
        username = self.get_current_user().encode('utf-8')
        view_name = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            os_code = self.get_argument('os_code', None)
            os_string = self.get_argument('os_string', None)
            if not os_code and not os_string or os_code and not os_string:
                data = get_supported_os_codes()

            elif os_string:
                data = get_supported_os_strings(view_name)

            results = (
                GenericResults(
                    username, uri, method
                ).information_retrieved(data, len(data))
            )
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke('Get OS Codes', 'Agent', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))


class AgentsHandler(BaseHandler):
    @authenticated_request
    @check_permissions(Permissions.READ)
    def get(self):
        active_user = self.get_current_user()
        uri = self.request.uri
        method = self.request.method
        user = UserManager(active_user)
        active_view = user.get_attribute(UserKeys.CurrentView)
        try:
            count = int(self.get_argument('count', 30))
            offset = int(self.get_argument('offset', 0))
            query = self.get_argument('query', None)
            fkey = self.get_argument('filter_key', None)
            fval = self.get_argument('filter_val', None)
            ip = self.get_argument('ip', None)
            mac = self.get_argument('mac', None)
            sort = self.get_argument('sort', 'asc')
            sort_by = self.get_argument('sort_by', AgentKeys.ComputerName)

            search = (
                RetrieveAgents(active_view, count, offset, sort, sort_by)
            )
            if not ip and not mac and not query and not fkey and not fval:
                results = self.get_all_agents(search)

            elif query and not ip and not mac and not fkey and not fval:
                results = self.get_all_agents_by_name(search, query)

            elif ip and not mac and not query and not fkey and not fval:
                results = self.get_all_agents_by_ip(search, ip)

            elif mac and not ip and not query and not fkey and not fval:
                results = self.get_all_agents_by_mac(search, mac)

            elif fkey and fval and not ip and not mac and not query:
                results = self.get_all_agents_by_key_val(search, fkey, fval)

            elif query and fkey and fval and not mac and not ip:
                results = (
                    self.get_all_agents_by_key_val_and_query(
                        search, fkey, fval, query
                    )
                )

            elif ip and fkey and fval and not mac and not query:
                results = (
                    self.get_all_agents_by_ip_and_filter(
                        search, ip, fkey, fval
                    )
                )

            elif mac and fkey and fval and not ip and not query:
                results = (
                    self.get_all_agents_by_mac_and_filter(
                        search, mac, fkey, fval
                    )
                )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    active_user, uri, method
                ).something_broke('Agents Api', 'agent', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    def get_all_agents(self, search):
        results = search.all()
        return results

    @results_message
    def get_all_agents_by_name(self, search, name):
        results = search.by_name(name)
        return results

    @results_message
    def get_all_agents_by_ip(self, search, ip):
        results = search.by_ip(ip)
        return results

    @results_message
    def get_all_agents_by_mac(self, search, mac):
        results = search.by_mac(mac)
        return results

    @results_message
    def get_all_agents_by_key_val(self, search, key, val):
        results = search.by_key_and_val(key, val)
        return results

    @results_message
    def get_all_agents_by_key_val_and_query(self, search, key, val, query):
        results = search.by_key_and_val(key, val, query)
        return results

    @results_message
    def get_all_agents_by_ip_and_filter(self, search, ip, key, val):
        results = search.by_ip_and_filter(ip, key, val)
        return results

    @results_message
    def get_all_agents_by_mac_and_filter(self, search, mac, key, val):
        results = search.by_mac_and_filter(mac, key, val)
        return results

    @authenticated_request
    @convert_json_to_arguments
    def put(self):
        username = self.get_current_user()
        uri = self.request.uri
        http_method = self.request.method
        user = UserManager(username)
        active_view = user.get_attribute(UserKeys.CurrentView)
        try:
            agent_ids = self.arguments.get(ApiArguments.AGENT_IDS)
            views = self.arguments.get(ApiArguments.VIEWS)
            action = self.arguments.get(ApiArguments.ACTION, ApiValues.ADD)
            token = self.arguments.get(AgentApiArguments.TOKEN, None)
            if not isinstance(agent_ids, list):
                agent_ids = agent_ids.split()

            if not isinstance(views, list):
                views = views.split()

            if action == ApiValues.ADD:
                results = self.add_agents_to_views(agent_ids, views)

            elif action == ApiValues.DELETE:
                results = self.remove_agents_from_views(agent_ids, views)

            elif token:
                operation = (
                    StoreAgentOperations(
                        username, active_view
                    )
                )
                results = self.new_token(operation, agent_ids, token)

            else:
                results = (
                    GenericResults(
                        username, uri, http_method
                    ).incorrect_arguments()
                )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, http_method
                ).something_broke('agent_ids', 'delete agentids', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.ASSIGN_NEW_TOKEN)
    def new_token(self, operation, agents, token):
        for agent in agents:
            manager = AgentManager(agent)
            manager.update_token(True)

        results = operation.new_token(agents, token=token)
        return results


    @results_message
    @check_permissions(Permissions.ADD_AGENTS_TO_VIEW)
    @log_operation(AdminActions.ADD_VIEWS_TO_AGENTS, vFenseObjects.AGENT)
    def add_agents_to_views(self, agents, views):
        end_results = {}
        views_added = []
        views_unchanged = []
        for view in views:
            manager = ViewManager(view)
            results = manager.add_to_agents(agents)
            if (results[ApiResultKeys.VFENSE_STATUS_CODE]
                    == ViewCodes.AgentsAddedToView):
                views_added.append(view)
            else:
                views_unchanged.append(view)

        end_results[ApiResultKeys.UNCHANGED_IDS] = views_unchanged
        end_results[ApiResultKeys.UPDATED_IDS] = views_added

        if views_added and views_unchanged:
            msg = (
                'Agents: {0} added to views: {1}, Unchanged views: {2}'
                .format(
                    ', '.join(agents),
                    ', '.join(views_added),
                    views_unchanged
                )
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericFailureCodes.FailedToUpdateAllObjects
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToAddViewsToAgents
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif views_added and not views_unchanged:
            msg = (
                'Agents: {0} added to views: {1}'
                .format(', '.join(agents), ', '.join(views_added))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsUpdated
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentCodes.UsersDeleted
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif views_unchanged and not views_added:
            msg = (
                'Agents: {0} failed to add to views: {1}'
                .format(', '.join(agents), ', '.join(views_unchanged))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsUnchanged
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToAddViewsToAgent
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        return end_results

    @results_message
    @check_permissions(Permissions.REMOVE_AGENTS_FROM_VIEW)
    @log_operation(AdminActions.REMOVE_VIEWS_FROM_AGENTS, vFenseObjects.AGENT)
    def remove_agents_from_views(self, agents, views):
        end_results = {}
        views_removed = []
        views_unchanged = []
        for view in views:
            manager = ViewManager(view)
            results = manager.remove_agents(agents)
            if (results[ApiResultKeys.VFENSE_STATUS_CODE]
                    == ViewCodes.AgentsRemovedFromView):
                views_removed.append(view)
            else:
                views_unchanged.append(view)

        end_results[ApiResultKeys.UNCHANGED_IDS] = views_unchanged
        end_results[ApiResultKeys.UPDATED_IDS] = views_removed

        if views_removed and views_unchanged:
            msg = (
                'Agents: {0} removed from views: {1}, Unchanged views: {2}'
                .format(
                    ', '.join(agents),
                    ', '.join(views_removed),
                    views_unchanged
                )
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericFailureCodes.FailedToUpdateAllObjects
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToRemoveViewsFromAgents
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif views_removed and not views_unchanged:
            msg = (
                'Agents: {0} removed from views: {1}'
                .format(', '.join(agents), ', '.join(views_removed))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsUpdated
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentCodes.ViewsRemovedFromAgents
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif views_unchanged and not views_removed:
            msg = (
                'Agents: {0} failed to add to views: {1}'
                .format(', '.join(agents), ', '.join(views_unchanged))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsUnchanged
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToAddViewsToAgent
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        return end_results

    @authenticated_request
    @convert_json_to_arguments
    def delete(self):
        username = self.get_current_user()
        view_name = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent_ids = self.arguments.get('agent_ids')
            if not isinstance(agent_ids, list):
                agent_ids = agent_ids.split()
            agentids_deleted =[]
            agentids_not_deleted =[]
            for agent_id in agent_ids:
                agent = AgentManager(agent_id, view_name=view_name)
                results = agent.delete_agent(uri, method)
                if results['http_status'] == 200:
                    delete_oper = (
                        StorePatchingOperation(
                            username, view_name
                        )
                    )
                    delete_oper.uninstall_agent(agent_id)
                    agentids_deleted.append(agent_id)
                else:
                    agentids_not_deleted.append(agent_id)
            results['data'] = {
                'agentids_deleted': agentids_deleted,
                'agentids_not_deleted': agentids_not_deleted
            }
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke('agent_ids', 'delete agentids', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.DELETE_AGENT)
    @log_operation(AdminActions.REMOVE_AGENTS, vFenseObjects.AGENT)
    def delete_agents(self, agents):
        end_results = {}
        agents_deleted = []
        agents_unchanged = []
        for agent_id in agents:
            manager = AgentManager(agent_id)
            results = manager.remove()
            if (results[ApiResultKeys.VFENSE_STATUS_CODE]
                    == AgentCodes.AgentDeleted):
                agents_deleted.append(agent_id)
            else:
                agents_unchanged.append(agent_id)

        end_results[ApiResultKeys.UNCHANGED_IDS] = agents_unchanged
        end_results[ApiResultKeys.DELETED_IDS] = agents_deleted

        if agents_deleted and agents_unchanged:
            msg = (
                'Agents: {0} deleted and these agents didnt: {1}'
                .format(
                    ', '.join(agents_deleted),
                    ', '.join(agents_unchanged),
                )
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericFailureCodes.FailedToDeleteAllObjects
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToDeleteAgents
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif agents_deleted and not agents_unchanged:
            msg = (
                'Agents: {0} deleted.'.format(', '.join(agents))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsDeleted
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentCodes.AgentsDeleted
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        elif agents_unchanged and not agents_deleted:
            msg = (
                'Agents: {0} failed to delete: {1}'
                .format(', '.join(agents), ', '.join(agents_unchanged))
            )
            end_results[ApiResultKeys.GENERIC_STATUS_CODE] = (
                GenericCodes.ObjectsUnchanged
            )
            end_results[ApiResultKeys.VFENSE_STATUS_CODE] = (
                AgentFailureCodes.FailedToDeleteAgents
            )
            end_results[ApiResultKeys.MESSAGE] = msg

        return end_results


class AgentHandler(BaseHandler):
    @authenticated_request
    @check_permissions(Permissions.READ)
    def get(self, agent_id):
        username = self.get_current_user()
        active_view = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            search = (
                RetrieveAgents(active_view)
            )
            results = self.get_agent_by_id(search, agent_id)
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke(agent_id, 'get agent_info', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    def get_agent_by_id(self, search, agent_id):
        results = search.by_id(agent_id)
        if results[ApiResultKeys.COUNT] > 0:
            results[ApiResultKeys.DATA] = results[ApiResultKeys.DATA].pop()
        return results

    @authenticated_request
    @convert_json_to_arguments
    @check_permissions(Permissions.ADMINISTRATOR)
    def put(self, agent_id):
        username = self.get_current_user()
        uri = self.request.uri
        method = self.request.method
        try:
            action = (
                self.arguments.get(ApiArguments.ACTION, None)
            )
            displayname = (
                self.arguments.get(AgentApiArguments.DISPLAY_NAME, None)
            )
            prod_level = (
                self.arguments.get(AgentApiArguments.ENVIRONMENT, None)
            )
            views = (
                self.arguments.get(AgentApiArguments.VIEWS, None)
            )
            manager = AgentManager(agent_id)

            if displayname and not prod_level and not views and not action:
                results = self.edit_display_name(manager, displayname)

            elif prod_level and not displayname and not views and not action:
                results = self.edit_environment(manager, prod_level)

            elif action and views and not prod_level and not displayname:
                if action == ApiValues.ADD:
                    results = self.add_agent_to_views(manager, views)

                elif action == ApiValues.DELETE:
                    results = self.remove_agent_from_views(manager, views)

                else:
                    results = (
                        GenericResults(
                            username, uri, method
                        ).incorrect_arguments()
                    )

            else:
                results = (
                    GenericResults(
                        username, uri, method
                    ).incorrect_arguments()
                )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke(agent_id, 'modify agent', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @log_operation(AdminActions.EDIT_AGENT_DISPLAY_NAME, vFenseObjects.AGENT)
    def edit_display_name(self, manager, display_name):
        results = manager.edit_display_name(display_name)
        return results

    @results_message
    @log_operation(AdminActions.EDIT_AGENT_ENVIRONMENT, vFenseObjects.AGENT)
    def edit_environment(self, manager, environment):
        results = manager.edit_environment(environment)
        return results

    @results_message
    @log_operation(AdminActions.ADD_VIEWS_TO_AGENT, vFenseObjects.AGENT)
    def add_agent_to_views(self, manager, views):
        results = manager.add_to_views(views)
        return results

    @results_message
    @log_operation(AdminActions.REMOVE_VIEWS_FROM_AGENT, vFenseObjects.AGENT)
    def remove_agent_from_views(self, manager, views):
        results = manager.remove_from_views(views)
        return results

    @authenticated_request
    def delete(self, agent_id):
        username = self.get_current_user()
        view_name = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            agent = AgentManager(agent_id)
            delete_oper = StorePatchingOperation(username, view_name)
            delete_oper.uninstall_agent(agent_id)
            results = self.remove_agent(agent)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke(agent_id, 'delete agent', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.DELETE_AGENT)
    @log_operation(AdminActions.REMOVE_AGENT, vFenseObjects.AGENT)
    def remove_agent(self, manager):
        results = manager.remove()
        return results

    @authenticated_request
    @convert_json_to_arguments
    def post(self, agent_id):
        username = self.get_current_user()
        view_name = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        http_method = self.request.method
        try:
            reboot = self.arguments.get(AgentApiArguments.REBOOT, None)
            shutdown = self.arguments.get(AgentApiArguments.SHUTDOWN, None)
            token = self.arguments.get(AgentApiArguments.TOKEN, None)
            apps_refresh = (
                self.arguments.get(AgentApiArguments.APPS_REFRESH, None)
            )
            operation = (
                StoreAgentOperations(
                    username, view_name
                )
            )
            if reboot:
                results = self.reboot(operation, [agent_id])

            elif shutdown:
                results = self.shutdown(operation, [agent_id])

            elif token:
                if token_exist_in_current(token):
                    results = self.new_token(operation, [agent_id], token)
                else:
                    msg = 'Invalid token {0}'.format(token)
                    result = Results(username, uri, http_method)
                    results = result.invalid_token(
                        **{
                            ApiResultKeys.INVALID_ID: token,
                            ApiResultKeys.MESSAGE: msg,
                        }
                    )


            elif apps_refresh:
                operation = (
                    StorePatchingOperation(
                        username, view_name
                    )
                )
                results = self.apps_refresh(operation, [agent_id])

            else:
                results = (
                    GenericResults(
                        username, uri, http_method
                    ).incorrect_arguments()
                )

            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, http_method
                ).something_broke(agent_id, '', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @check_permissions(Permissions.REBOOT)
    @results_message
    def reboot(self, operation, agent_ids):
        results = operation.reboot(agent_ids)

        return results

    @check_permissions(Permissions.SHUTDOWN)
    @results_message
    def shutdown(self, operation, agent_ids):
        results = operation.shutdown(agent_ids)
        return results

    @check_permissions(Permissions.ASSIGN_NEW_TOKEN)
    @results_message
    def new_token(self, operation, agent_ids, token):
        results = operation.new_token(agent_ids, token=token)
        return results

    @results_message
    def apps_refresh(self, operation, agent_ids):
        results = operation.apps_refresh(agent_ids)
        return results


class AgentTagHandler(BaseHandler):
    @authenticated_request
    @check_permissions(Permissions.READ)
    def get(self, agent_id):
        username = self.get_current_user()
        active_view = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            name = self.get_argument(ApiArguments.QUERY, None)
            search = (
                RetrieveAgents(active_view)
            )
            if name:
                results = self.search_tags_by_name(search, name)
            else:
                results = self.get_tags_by_agent_id(search, agent_id)
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke(agent_id, 'get agent_info', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    def get_tags_by_agent_id(self, search, agent_id):
        results = search.by_agent_id(agent_id)
        return results

    @results_message
    def search_tags_by_name(self, search, name):
        results = search.by_name(name)
        return results

    @authenticated_request
    def put(self, agent_id):
        username = self.get_current_user()
        active_view = (
            UserManager(username).get_attribute(UserKeys.CurrentView)
        )
        uri = self.request.uri
        method = self.request.method
        try:
            tag_ids = self.get_argument(TagApiArguments.TAG_IDS)
            tag_name = self.get_argument(TagApiArguments.TAG_NAME, None)
            action = self.get_argument(ApiArguments.ACTION, ApiValues.ADD)
            manager = (
                AgentManager(agent_id)
            )
            if action == ApiValues.ADD:
                if not tag_name:
                    results = self.add_tags(manager, tag_ids)
                else:
                    results = self.create_tag(tag_name, agent_id, active_view)
            else:
                results = self.remove_tags(manager, tag_ids)
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

        except Exception as e:
            results = (
                GenericResults(
                    username, uri, method
                ).something_broke(agent_id, 'get agent_info', e)
            )
            logger.exception(e)
            self.set_status(results['http_status'])
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(results, indent=4))

    @results_message
    @check_permissions(Permissions.ADD_AGENTS_TO_TAG)
    def add_tags(self, manager, tag_ids):
        results = manager.add_to_tags(tag_ids)
        return results

    @results_message
    @check_permissions(Permissions.REMOVE_AGENTS_FROM_TAG)
    def remove_tags(self, manager, tag_ids):
        results = manager.remove_from_tags(tag_ids)
        return results

    @results_message
    @check_permissions(Permissions.CREATE_TAG)
    def create_tag(self, tag_name, agent_id, active_view):
        tag = Tag(tag_name, active_view, agents=[agent_id])
        manager = TagManager()
        results = manager.create(tag)
        return results
