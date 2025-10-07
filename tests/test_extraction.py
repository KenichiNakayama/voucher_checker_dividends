from voucher_logic import models
from voucher_logic.extraction import RuleBasedVoucherExtractor


SAMPLE_TEXT = """Dividend Resolution
Company: ACME Holdings
Date: 2024-01-01
Amount: 1,000,000
"""


def test_rule_based_extractor_detects_fields():
    tokens = [
        models.TextSpan(page=1, text="Company: ACME Holdings", bbox=(0.1, 0.65, 0.9, 0.72)),
        models.TextSpan(page=1, text="Date: 2024-01-01", bbox=(0.1, 0.55, 0.9, 0.62)),
        models.TextSpan(page=1, text="Amount: 1,000,000", bbox=(0.1, 0.45, 0.9, 0.52)),
    ]
    parsed = models.ParsedDocument(pages=[SAMPLE_TEXT], tokens=tokens, metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.company_name.value == "ACME Holdings"
    assert extracted.dividend_amount.value == "1,000,000"
    assert any(span.label == "company_name" for span in extracted.source_highlights)


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
    tokens = [
        models.TextSpan(page=1, text="Acme Holdings K.K.", bbox=(0.2, 0.74, 0.82, 0.80)),
        models.TextSpan(
            page=1,
            text="At the meeting of the Board of Directors held on 2025-03-30",
            bbox=(0.1, 0.48, 0.92, 0.56),
        ),
        models.TextSpan(
            page=1,
            text="Total Amount of Dividends: JPY 36,000,000",
            bbox=(0.1, 0.38, 0.92, 0.45),
        ),
    ]
    parsed = models.ParsedDocument(pages=[sample_page], tokens=tokens, metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.title.value == "Board Resolution Regarding Dividend Distribution"
    assert extracted.company_name.value == "Acme Holdings K.K."
    assert extracted.resolution_date.value == "2025-03-30"
    assert extracted.dividend_amount.value == "36,000,000"


def test_rule_based_extractor_handles_japanese_labels_and_dates():
    sample_page = (
        "会社名\n"
        "ＡＢＣ株式会社\n"
        "配当基準日：2024年03月31日\n"
        "配当決議日：2024年04月15日\n"
        "効力発生日：2024年04月30日\n"
        "総配当金額：1,234,567円\n"
    )
    tokens = [
        models.TextSpan(page=1, text="会社名", bbox=(0.1, 0.82, 0.4, 0.88)),
        models.TextSpan(page=1, text="ＡＢＣ株式会社", bbox=(0.1, 0.76, 0.6, 0.82)),
        models.TextSpan(page=1, text="配当基準日：2024年03月31日", bbox=(0.1, 0.65, 0.8, 0.72)),
        models.TextSpan(page=1, text="配当決議日：2024年04月15日", bbox=(0.1, 0.55, 0.8, 0.62)),
        models.TextSpan(page=1, text="効力発生日：2024年04月30日", bbox=(0.1, 0.45, 0.8, 0.52)),
        models.TextSpan(page=1, text="総配当金額：1,234,567円", bbox=(0.1, 0.35, 0.8, 0.42)),
    ]
    parsed = models.ParsedDocument(pages=[sample_page], tokens=tokens, metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.CLAUDE)

    assert extracted.company_name.value == "ABC株式会社"
    assert extracted.resolution_date.value == "2024-04-15"
    assert extracted.dividend_amount.value == "1,234,567"
    assert any(span.label == "resolution_date" for span in extracted.source_highlights)
    assert extracted.resolution_date.value != "2024-03-31"


def test_rule_based_extractor_handles_english_suffix_without_label():
    sample_page = (
        "Dividend Resolution\n"
        "XYZ Holdings Co., Ltd.\n"
        "Address: 1 Infinite Loop\n"
        "Resolution Date: 2024-06-12\n"
        "Total Amount of Dividends: 2,500,000\n"
    )
    tokens = [
        models.TextSpan(page=1, text="XYZ Holdings Co., Ltd.", bbox=(0.1, 0.75, 0.9, 0.82)),
        models.TextSpan(page=1, text="Resolution Date: 2024-06-12", bbox=(0.1, 0.6, 0.9, 0.67)),
        models.TextSpan(page=1, text="Total Amount of Dividends: 2,500,000", bbox=(0.1, 0.5, 0.9, 0.57)),
    ]
    parsed = models.ParsedDocument(pages=[sample_page], tokens=tokens, metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.company_name.value == "XYZ Holdings Co., Ltd."
    assert extracted.resolution_date.value == "2024-06-12"
    assert extracted.dividend_amount.value == "2,500,000"


def test_rule_based_extractor_ignores_sentence_with_verbs_for_company():
    sample_page = (
        "Dividend Resolution\n"
        "At the meeting of the Board of Directors held on 2024-05-01, the Company resolved to distribute dividends.\n"
        "ABC Co., Ltd.\n"
    )
    tokens = [
        models.TextSpan(
            page=1,
            text="At the meeting of the Board of Directors held on 2024-05-01, the Company resolved to distribute dividends.",
            bbox=(0.1, 0.6, 0.9, 0.7),
        ),
        models.TextSpan(page=1, text="ABC Co., Ltd.", bbox=(0.1, 0.5, 0.9, 0.58)),
    ]
    parsed = models.ParsedDocument(pages=[sample_page], tokens=tokens, metadata={})
    extractor = RuleBasedVoucherExtractor()

    extracted = extractor.extract(parsed, provider=models.ProviderType.OPENAI)

    assert extracted.company_name.value == "ABC Co., Ltd."
