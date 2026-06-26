from uuid import uuid4

from app.domain.entities import Source, SourceHeader, ValueCandidate
from app.domain.merge.handlers import combine_sources


def _candidate(source: Source) -> ValueCandidate:
    return ValueCandidate(value=None, sources=[source])


def test_different_documents_are_kept_separate() -> None:
    doc1, doc2 = uuid4(), uuid4()
    candidates = [
        _candidate(Source(document_id=doc1, headers=(SourceHeader.BODY,))),
        _candidate(Source(document_id=doc2, headers=(SourceHeader.IN_SPEC,))),
    ]

    result = combine_sources(candidates)

    assert result == [
        Source(document_id=doc1, headers=(SourceHeader.BODY,)),
        Source(document_id=doc2, headers=(SourceHeader.IN_SPEC,)),
    ]


def test_same_document_different_headers_merge_into_one() -> None:
    doc = uuid4()
    candidates = [
        _candidate(Source(document_id=doc, headers=(SourceHeader.BODY,))),
        _candidate(Source(document_id=doc, headers=(SourceHeader.IN_SPEC,))),
    ]

    result = combine_sources(candidates)

    assert result == [
        Source(document_id=doc, headers=(SourceHeader.BODY, SourceHeader.IN_SPEC)),
    ]


def test_duplicate_headers_are_not_repeated() -> None:
    doc = uuid4()
    candidates = [
        _candidate(Source(document_id=doc, headers=(SourceHeader.BODY,))),
        _candidate(Source(document_id=doc, headers=(SourceHeader.BODY,))),
    ]

    result = combine_sources(candidates)

    assert result == [Source(document_id=doc, headers=(SourceHeader.BODY,))]


def test_document_order_is_preserved() -> None:
    doc1, doc2 = uuid4(), uuid4()
    candidates = [
        _candidate(Source(document_id=doc2, headers=(SourceHeader.AFTER_SPEC,))),
        _candidate(Source(document_id=doc1, headers=(SourceHeader.BODY,))),
    ]

    result = combine_sources(candidates)

    assert [s.document_id for s in result] == [doc2, doc1]
