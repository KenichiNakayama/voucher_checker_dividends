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


def test_rule_based_extractor_handles_realistic_document():
    sample_page = (
        "Board Resolution Regarding Dividend Distribution\n"
        "Acme Holdings K.K.\n"
        "Address: 1-10-2 Marunouchi, Chiyoda-ku, Tokyo 100-0005, Japan\n"
        "Corporate Number: 9012-34-567890\n"
        "At the meeting of the Board of Directors held on 2025-03-30, the Company resolved to distribute dividends.\n"
        "Total Amount of Dividends: JPY 36,000,000 (JPY 18 per share x 2,000,000 shares)\n"
    )
    parsed = models.ParsedDocument(pages=[sample_page], tokens=[], metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.title.value == "Board Resolution Regarding Dividend Distribution"
    assert extracted.company_name.value == "Acme Holdings K.K."
    assert extracted.resolution_date.value == "2025-03-30"
    assert extracted.dividend_amount.value == "36,000,000"
