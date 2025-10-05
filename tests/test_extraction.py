from voucher_logic import models
from voucher_logic.extraction import RuleBasedVoucherExtractor


SAMPLE_TEXT = """Dividend Resolution
Company: ACME Holdings
Date: 2024-01-01
Amount: 1,000,000
"""


def test_rule_based_extractor_detects_fields():
    parsed = models.ParsedDocument(pages=[SAMPLE_TEXT], tokens=[], metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.company_name.value == "ACME Holdings"
    assert extracted.dividend_amount.value == "1,000,000"
    assert any(span.label == "company" for span in extracted.source_highlights)


def test_rule_based_extractor_handles_missing_values():
    parsed = models.ParsedDocument(pages=["Dividend Resolution"], tokens=[], metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.CLAUDE)

    assert extracted.company_name.value is None
    assert extracted.title.value == "Dividend Resolution"
