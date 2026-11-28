"""Operations for the Microsoft Office 365 endpoints feed (v2, 2.0.0).

Changes from the 1.0.0 stock connector:
- urlparse/parse_qs were used without being imported (a 400 fallback path
  raised NameError); fixed.
- build_urls_dict used a mutable default argument; fixed.
- A region with no matching feed version raised IndexError; now a ConnectorError.
- verify_ssl defaulted to False in fetch_indicator but True in the config; now True.
- New generic execute_api_request, restricted to the public feed's /version and
  /endpoints paths. The feed is anonymous, so no auth is attached.
"""
import datetime
import uuid
from urllib.parse import parse_qs, urlparse

import requests

from connectors.core.connector import ConnectorError, get_logger

from . import constant

logger = get_logger('microsoft-office-365-feed-v2')


def _verify(config):
    return bool(config.get('verify_ssl', True))


def _split_services(value):
    if not value:
        return ['All']
    if isinstance(value, str):
        return [s.strip() for s in value.split(',') if s.strip()]
    return [str(s).strip() for s in value if str(s).strip()]


def build_feed_url(kind, region, services, client_request_id, path_kind):
    """kind: 'version' or 'endpoints'. Returns the full feed URL."""
    base = constant.FEED_BASE
    if 'All' in services:
        return '{0}/{1}/{2}?ClientRequestId={3}'.format(base, kind, region, client_request_id)
    return '{0}/{1}/{2}?ServiceAreas={3}&ClientRequestId={4}'.format(
        base, kind, region, ','.join(services), client_request_id)


def _region_only_url(url):
    parsed = urlparse(url)
    cid = parse_qs(parsed.query).get('ClientRequestId', [str(uuid.uuid4())])[0]
    return '{0}://{1}{2}?ClientRequestId={3}'.format(parsed.scheme, parsed.netloc, parsed.path, cid)


def _get(url, verify):
    try:
        resp = requests.get(url=url, verify=verify, timeout=constant.REQUEST_TIMEOUT)
    except requests.exceptions.SSLError:
        raise ConnectorError('An SSL error occurred.')
    except requests.exceptions.ConnectionError:
        raise ConnectorError('A connection error occurred.')
    except requests.exceptions.Timeout:
        raise ConnectorError('The request timed out.')
    except requests.exceptions.RequestException as err:
        raise ConnectorError('Request failed: {0}'.format(err))
    return resp


def fetch_feed(url, verify):
    """GET a feed URL. A 400 for a service-area filter with no indicators is
    retried region-only (stock behaviour). Returns the parsed JSON body."""
    resp = _get(url, verify)
    if resp.status_code == 400 and 'ServiceAreas=' in url:
        resp = _get(_region_only_url(url), verify)
    if resp.status_code != 200:
        raise ConnectorError('Office 365 feed returned HTTP {0}'.format(resp.status_code))
    try:
        return resp.json()
    except ValueError:
        raise ConnectorError('Office 365 feed returned a non-JSON body')


def get_versions(region, verify):
    url = build_feed_url('version', region, ['All'], str(uuid.uuid4()), 'version')
    data = fetch_feed(url, verify)
    if isinstance(data, dict):
        # /version/<region> returns one object for one instance; a list only when unscoped.
        return [data] if 'latest' in data else []
    return [v for v in data if isinstance(v, dict)] if isinstance(data, list) else []


def _version_ts(latest):
    return int(datetime.datetime.strptime(str(latest), '%Y%m%d%H').timestamp())


def _pull_ts(last_pull_time):
    """Accept an epoch number, a numeric string, or the ISO form stock used."""
    if isinstance(last_pull_time, (int, float)):
        return float(last_pull_time)
    text = str(last_pull_time).strip()
    try:
        return float(text)
    except ValueError:
        return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').timestamp()


def fetch_indicator(config, params, **kwargs):
    region = config.get('regions') or 'Worldwide'
    if region not in constant.REGIONS:
        raise ConnectorError('Unknown region: {0}'.format(region))
    verify = _verify(config)
    services = _split_services(config.get('services'))

    kind_key = str(params.get('indicator_type', 'both')).lower()
    if kind_key not in constant.INDICATOR_TYPES:
        raise ConnectorError('indicator_type must be IPs, URLs or Both')
    limit = params.get('limit')
    limit = int(limit) if limit not in (None, '', 0) else -1

    versions = get_versions(region, verify)
    match = [v for v in versions if v.get('instance') == region]
    if not match:
        raise ConnectorError('No feed version published for region {0}'.format(region))
    latest = match[0].get('latest')

    last_pull = params.get('last_pull_time')
    if last_pull not in (None, '', 0, '0'):
        try:
            since = _pull_ts(last_pull)
        except ValueError:
            raise ConnectorError('last_pull_time must be an epoch timestamp or ISO 8601 UTC')
        if _version_ts(latest) <= since:
            return {'result': 'Indicators are up to date', 'up_to_date': True, 'region': region,
                    'lastUpdated': latest}

    url = build_feed_url('endpoints', region, services, str(uuid.uuid4()), 'endpoints')
    entries = fetch_feed(url, verify)
    if not isinstance(entries, list):
        entries = []
    entries = [e for e in entries if isinstance(e, dict) and ('ips' in e or 'urls' in e)]

    indicators = []
    for entry in entries:
        if kind_key in ('ips', 'both'):
            indicators.extend(_expand(entry, 'IP', 'ips'))
        if kind_key in ('urls', 'both'):
            indicators.extend(_expand(entry, 'URL', 'urls'))
    indicators = _dedupe(indicators)
    if limit > 0:
        indicators = indicators[:limit]

    return {'region': region, 'lastUpdated': latest, 'feedURL': url,
            'indicators': indicators, 'count': len(indicators), 'up_to_date': False}


def _expand(entry, type_, key):
    meta = {k: v for k, v in entry.items() if k not in ('ips', 'urls')}
    out = []
    for value in entry.get(key) or []:
        row = {'value': value, 'type': type_}
        row.update(meta)
        out.append(row)
    return out


def _dedupe(rows):
    seen = set()
    result = []
    for row in rows:
        if row['value'] in seen:
            continue
        seen.add(row['value'])
        result.append(row)
    return result


def execute_api_request(config, params, **kwargs):
    endpoint = str(params.get('endpoint') or '').strip()
    if not endpoint.startswith(constant.ALLOWED_PATH_PREFIXES) or '..' in endpoint:
        raise ConnectorError('endpoint must start with /version/ or /endpoints/ and contain no ..')
    query = params.get('query') or {}
    if not isinstance(query, dict):
        raise ConnectorError('query must be a JSON object')
    query = {str(k): str(v) for k, v in query.items()}
    query.setdefault('ClientRequestId', str(uuid.uuid4()))
    try:
        resp = requests.get(constant.FEED_BASE + endpoint, params=query,
                            verify=_verify(config), timeout=constant.REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as err:
        raise ConnectorError('Request failed: {0}'.format(err))
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return {'status_code': resp.status_code, 'body': body}


def check_health_ex(config):
    region = config.get('regions') or 'Worldwide'
    versions = get_versions(region, _verify(config))
    return any(v.get('instance') == region for v in versions)


operations = {
    'fetch_indicator': fetch_indicator,
    'execute_api_request': execute_api_request,
}
