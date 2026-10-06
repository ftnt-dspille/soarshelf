from connectors.core.connector import get_logger, ConnectorError

from .constants import (
    PENTEST_STATES,
    DATE_FIELDS,
    ORDER_BY_FIELDS,
    SORT_DIRECTIONS
)
from .graphQL import (
    PENTEST_BASE_FIELDS,
    ATTACK_PATHS_FIELDS,
    WEAKNESSES_FIELDS,
    PENTESTS_QUERY,
    ATTACK_PATHS_QUERY,
    WEAKNESSES_QUERY
)
from .horizon_api_auth import HorizonAPI

logger = get_logger('horizon-ai')


def build_page_input(params):
    """
    Build the PageInput object from provided parameters
    """

    def safe_int(value, default):
        """
        Safely convert a value to an integer, falling back to a default if conversion fails.
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # Safely enforce integers for page_num and page_size
    page_input = {
        "page_num": safe_int(params.get('page_num'), 1),
        "page_size": safe_int(params.get('page_size'), 50)
    }

    # Add ordering if specified
    if params.get('order_by'):
        # Convert human-readable field name to API field name
        order_by = params['order_by']
        if order_by in ORDER_BY_FIELDS:
            order_by = ORDER_BY_FIELDS[order_by]
        page_input["order_by"] = order_by

        # Convert human-readable sort direction to API value
        sort_order = params.get('sort_order', 'Ascending')
        if sort_order in SORT_DIRECTIONS:
            sort_order = SORT_DIRECTIONS[sort_order]
        page_input["sort_order"] = sort_order

    # Add text search if specified
    if params.get('text_search'):
        page_input["text_search"] = params['text_search']

    # Add filters if specified
    filters = []

    # Handle date range filters
    if params.get('date_from') or params.get('date_to'):
        # Convert human-readable date field to API field name
        date_field = params.get('date_field', 'Launch Date')
        field_name = DATE_FIELDS.get(date_field, 'launched_at')

        if params.get('date_from'):
            filters.append({
                "field_name": field_name,
                "greater_than": params['date_from']
            })
        if params.get('date_to'):
            filters.append({
                "field_name": field_name,
                "less_than": params['date_to']
            })

    # Handle state filter
    if params.get('state'):
        state_value = params['state']
        # Convert human-readable state to API value if needed
        if state_value in PENTEST_STATES:
            state_value = PENTEST_STATES[state_value]

        filters.append({
            "field_name": "state",
            "values": state_value
        })

    # Handle client name filter
    if params.get('client_name'):
        filters.append({
            "field_name": "client_name",
            "values": params['client_name']
        })

    # Add the filters if any were created
    if filters:
        page_input["filter_by_inputs"] = filters

    return page_input


def get_pentests(config, params):
    try:
        horizon = HorizonAPI(config)

        # Determine which fields to include based on parameters
        fields = [PENTEST_BASE_FIELDS]

        if params.get('include_attack_paths'):
            fields.append(ATTACK_PATHS_FIELDS)

        if params.get('include_weaknesses'):
            fields.append(WEAKNESSES_FIELDS)

        # Construct the full query with all required fields
        query = PENTESTS_QUERY % '\n'.join(fields)

        variables = {
            "page_input": build_page_input(params)
        }

        return horizon.make_request(query, variables)
    except Exception as e:
        logger.error(f"Error getting pentests: {str(e)}")
        raise ConnectorError(str(e))


def get_attack_paths(config, params):
    try:
        horizon = HorizonAPI(config)
        op_id = params.get('op_id')
        if not op_id:
            raise ConnectorError("op_id is required")

        variables = {
            "input": {"op_id": op_id},
            "page_input": build_page_input(params)
        }

        return horizon.make_request(ATTACK_PATHS_QUERY, variables)
    except Exception as e:
        logger.error(f"Error getting attack paths: {str(e)}")
        raise ConnectorError(str(e))


def get_weaknesses(config, params):
    try:
        horizon = HorizonAPI(config)
        op_id = params.get('op_id')
        if not op_id:
            raise ConnectorError("op_id is required")

        variables = {
            "input": {"op_id": op_id},
            "page_input": build_page_input(params)
        }

        return horizon.make_request(WEAKNESSES_QUERY, variables)
    except Exception as e:
        logger.error(f"Error getting weaknesses: {str(e)}")
        raise ConnectorError(str(e))


def health_check(config):
    try:
        horizon = HorizonAPI(config)
        return horizon.check_health()
    except Exception as err:
        logger.error(f"Health check error: {str(err)}")
        raise ConnectorError(str(err))


operations = {
    'get_pentests': get_pentests,
    'get_attack_paths': get_attack_paths,
    'get_weaknesses': get_weaknesses,
    'check_health': health_check
}
