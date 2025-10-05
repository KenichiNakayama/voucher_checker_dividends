from voucher_logic.persistence import InMemoryAnalysisStore
from voucher_logic import models


def test_in_memory_store_round_trip():
    store = InMemoryAnalysisStore()
    key = "session-1"
    result = models.VoucherAnalysisResult(
        parsed_document=models.ParsedDocument(pages=[], tokens=[], metadata={}),
        extracted=models.ExtractedVoucherData.empty(),
        validation=models.ValidationReport.empty(),
        highlight_pdf=b"",
    )

    store.save(key, result)
    loaded = store.load(key)

    assert loaded is result
    store.delete(key)
    assert store.load(key) is None


def test_store_clear_removes_all_entries():
    store = InMemoryAnalysisStore()
    store.save("a", models.VoucherAnalysisResult.empty())
    store.save("b", models.VoucherAnalysisResult.empty())

    assert len(store.keys()) == 2
    store.clear()
    assert store.keys() == []
