import json

from jirav2.adf import adf_to_text, is_adf, to_adf


def test_plain_text_becomes_one_paragraph():
    doc = to_adf('hello')
    assert doc == {'type': 'doc', 'version': 1, 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'hello'}]}]}


def test_blank_line_splits_paragraphs_and_newline_is_a_hard_break():
    doc = to_adf('a\nb\n\nc')
    assert len(doc['content']) == 2
    assert doc['content'][0]['content'] == [
        {'type': 'text', 'text': 'a'}, {'type': 'hardBreak'}, {'type': 'text', 'text': 'b'}]


def test_windows_line_endings_are_normalised():
    assert len(to_adf('a\r\n\r\nb')['content']) == 2


def test_empty_string_still_makes_a_valid_document():
    assert to_adf('')['content'] == [{'type': 'paragraph', 'content': []}]


def test_none_stays_none():
    assert to_adf(None) is None


def test_adf_dict_passes_through_untouched():
    doc = {'type': 'doc', 'version': 1, 'content': []}
    assert to_adf(doc) is doc
    assert is_adf(doc) and not is_adf({'type': 'paragraph'})


def test_adf_json_string_is_parsed():
    doc = {'type': 'doc', 'version': 1, 'content': [{'type': 'paragraph', 'content': []}]}
    assert to_adf(json.dumps(doc)) == doc


def test_json_that_is_not_adf_is_just_text():
    assert to_adf('{"a": 1}')['content'][0]['content'][0]['text'] == '{"a": 1}'


def test_broken_json_that_looks_like_adf_is_text():
    assert to_adf('{"type": "doc" oops')['content'][0]['content'][0]['text'] == '{"type": "doc" oops'


def test_non_string_values_are_stringified():
    assert to_adf(42)['content'][0]['content'][0]['text'] == '42'


def test_round_trip_through_text():
    assert adf_to_text(to_adf('one\ntwo\n\nthree')).strip() == 'one\ntwo\nthree'


def test_adf_to_text_handles_mentions_lists_and_none():
    doc = {'type': 'doc', 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'hi '},
                                          {'type': 'mention', 'attrs': {'text': '@Sam'}}]},
        {'type': 'bulletList', 'content': [
            {'type': 'listItem', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'x'}]}]}]}]}
    assert adf_to_text(doc).split() == ['hi', '@Sam', 'x']
    assert adf_to_text(None) == '' and adf_to_text('raw') == 'raw'
