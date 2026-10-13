"""Comments, attachments, remote links and issue links."""
import pytest

from jirav2 import client as client_module
from jirav2 import operations

ConnectorError = client_module.ConnectorError
ISSUE = '/rest/api/3/issue'


@pytest.mark.op('add_comment')
def test_add_comment_wraps_text_as_adf(fake, run):
    fake.on('POST', ISSUE + '/SEC-1/comment', {'id': '10'}, status=201)
    assert run('add_comment', issue_key='SEC-1', comment='hello')['id'] == '10'
    body = fake.only().json
    assert body['body']['content'][0]['content'][0]['text'] == 'hello'
    assert 'properties' not in body


@pytest.mark.op('add_comment')
def test_add_comment_internal_sets_the_jsm_property(fake, run):
    fake.on('POST', ISSUE + '/SEC-1/comment', {'id': '11'}, status=201)
    run('add_comment', issue_key='SEC-1', comment='agents only', internal=True)
    assert fake.only().json['properties'] == [{'key': 'sd.public.comment', 'value': {'internal': True}}]


@pytest.mark.op('add_comment')
def test_add_comment_requires_text(fake, run):
    with pytest.raises(ConnectorError, match='comment'):
        run('add_comment', issue_key='SEC-1', comment='')


@pytest.mark.op('get_comments')
def test_get_comments_passes_paging_and_order(fake, run):
    fake.on('GET', ISSUE + '/SEC-1/comment', {'comments': [], 'total': 0})
    run('get_comments', issue_key='SEC-1', startAt=5, maxResults=10, orderBy='-created')
    assert fake.only().params == {'startAt': 5, 'maxResults': 10, 'orderBy': '-created'}


@pytest.mark.op('get_comments')
def test_get_comments_include_text(fake, run):
    from jirav2.adf import to_adf
    fake.on('GET', ISSUE + '/SEC-1/comment', {'comments': [{'id': '1', 'body': to_adf('one')},
                                                           {'id': '2', 'body': to_adf('two')}]})
    out = run('get_comments', issue_key='SEC-1', include_text=True)
    assert [c['body_text'] for c in out['comments']] == ['one', 'two']


@pytest.mark.op('update_comment')
def test_update_comment(fake, run):
    fake.on('PUT', ISSUE + '/SEC-1/comment/10', {'id': '10'})
    run('update_comment', issue_key='SEC-1', comment_id='10', comment='edited')
    assert fake.only().json['body']['content'][0]['content'][0]['text'] == 'edited'


@pytest.mark.op('update_comment')
def test_update_comment_requires_the_id(fake, run):
    with pytest.raises(ConnectorError, match='comment_id'):
        run('update_comment', issue_key='SEC-1', comment='x')


@pytest.mark.op('delete_comment')
def test_delete_comment(fake, run):
    fake.on('DELETE', ISSUE + '/SEC-1/comment/10', None, status=204)
    out = run('delete_comment', issue_key='SEC-1', comment_id='10')
    assert out == {'status': 'Success', 'issue_key': 'SEC-1', 'comment_id': '10'}


@pytest.mark.op('submit_file')
def test_submit_file_uploads_with_the_no_check_header(fake, run, monkeypatch, tmp_path):
    local = tmp_path / 'evidence.txt'
    local.write_bytes(b'abc')
    monkeypatch.setattr(operations, '_get_file_data', lambda kind, value: ('evidence.txt', str(local)))
    fake.on('POST', ISSUE + '/SEC-1/attachments', [{'id': '5', 'filename': 'evidence.txt'}])
    out = run('submit_file', issue_key='SEC-1', path='Attachment ID', value='abc')
    call = fake.only()
    assert call.headers['X-Atlassian-Token'] == 'no-check'
    assert call.files == {'file': ('evidence.txt', b'abc')}
    assert 'Content-Type' not in call.headers
    assert out[0]['filename'] == 'evidence.txt'


@pytest.mark.op('submit_file')
def test_get_file_data_resolves_an_attachment_id(monkeypatch):
    import integrations.crudhub as crudhub
    import connectors.cyops_utilities.builtins as builtins
    seen = []
    monkeypatch.setattr(crudhub, 'make_request', lambda iri, method: seen.append(iri) or
                        {'file': {'@id': '/api/3/files/9', 'filename': 'a.txt'}})
    monkeypatch.setattr(builtins, 'download_file_from_cyops',
                        lambda iri: {'filename': 'ignored', 'cyops_file_path': 'x/a.txt'})
    assert operations._get_file_data('Attachment ID', '42') == ('a.txt', '/tmp/x/a.txt')
    assert seen == ['/api/3/attachments/42']


@pytest.mark.op('submit_file')
def test_get_file_data_resolves_a_file_iri(monkeypatch):
    import connectors.cyops_utilities.builtins as builtins
    monkeypatch.setattr(builtins, 'download_file_from_cyops',
                        lambda iri: {'filename': 'b.bin', 'cyops_file_path': 'y/b.bin'})
    assert operations._get_file_data('File IRI', '/api/3/files/1') == ('b.bin', '/tmp/y/b.bin')


@pytest.mark.op('submit_file')
def test_get_file_data_failure_is_a_connector_error(monkeypatch):
    import connectors.cyops_utilities.builtins as builtins

    def boom(iri):
        raise RuntimeError('gone')
    monkeypatch.setattr(builtins, 'download_file_from_cyops', boom)
    with pytest.raises(ConnectorError, match='Could not load the FortiSOAR file'):
        operations._get_file_data('File IRI', '/api/3/files/1')


@pytest.mark.op('add_remote_link')
def test_add_remote_link(fake, run):
    fake.on('POST', ISSUE + '/SEC-1/remotelink', {'id': 1, 'self': 'x'}, status=201)
    run('add_remote_link', issue_key='SEC-1', url='https://soar.example.com/alerts/1', title='FortiSOAR alert')
    assert fake.only().json == {'object': {'url': 'https://soar.example.com/alerts/1', 'title': 'FortiSOAR alert'}}


@pytest.mark.op('add_remote_link')
@pytest.mark.parametrize('missing', ['url', 'title'])
def test_add_remote_link_requires_url_and_title(fake, run, missing):
    params = {'issue_key': 'SEC-1', 'url': 'u', 'title': 't'}
    del params[missing]
    with pytest.raises(ConnectorError, match=missing):
        run('add_remote_link', **params)


@pytest.mark.op('link_issues')
def test_link_issues(fake, run):
    fake.on('POST', '/rest/api/3/issueLink', None, status=201)
    out = run('link_issues', link_type='Blocks', inward_issue='SEC-1', outward_issue='SEC-2')
    assert fake.only().json == {'type': {'name': 'Blocks'}, 'inwardIssue': {'key': 'SEC-1'},
                                'outwardIssue': {'key': 'SEC-2'}}
    assert out['status'] == 'Success'


@pytest.mark.op('link_issues')
def test_link_issues_with_comment(fake, run):
    fake.on('POST', '/rest/api/3/issueLink', None, status=201)
    run('link_issues', link_type='Relates', inward_issue='SEC-1', outward_issue='SEC-2', comment='see also')
    assert fake.only().json['comment']['body']['type'] == 'doc'


@pytest.mark.op('link_issues')
def test_link_issues_requires_both_ends(fake, run):
    with pytest.raises(ConnectorError, match='outward_issue'):
        run('link_issues', link_type='Blocks', inward_issue='SEC-1')


@pytest.mark.op('list_link_types')
def test_list_link_types(fake, run):
    fake.on('GET', '/rest/api/3/issueLinkType', {'issueLinkTypes': [{'name': 'Blocks'}]})
    assert run('list_link_types')['issueLinkTypes'] == [{'name': 'Blocks'}]
