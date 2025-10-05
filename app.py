"""Streamlit entry point for the voucher checker application."""
from __future__ import annotations

from typing import Dict, List, Optional

try:
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - allows running unit tests without Streamlit
    st = None  # type: ignore

from voucher_logic import models
from voucher_logic.controller import analyze_voucher
from voucher_logic.highlight import HighlightRenderer
from voucher_logic.pdf_ingestor import PdfIngestor
from voucher_logic.persistence import InMemoryAnalysisStore
from voucher_logic.settings import PROVIDER_ENV_VARS, get_provider_key
from voucher_logic.ui import build_validation_rows, format_extracted_fields
from voucher_logic.validators import VoucherValidator


def get_session_store() -> InMemoryAnalysisStore:
    if st is None:
        return InMemoryAnalysisStore()
    if "analysis_store" not in st.session_state:
        st.session_state["analysis_store"] = InMemoryAnalysisStore()
    return st.session_state["analysis_store"]


def ensure_streamlit() -> None:
    if st is None:  # pragma: no cover - ensures fail-fast when run without Streamlit
        raise RuntimeError("Streamlit is required to run this application.")


def validate_inputs(uploaded_file, provider: models.ProviderType) -> List[str]:
    errors: List[str] = []
    if uploaded_file is None:
        errors.append("PDFファイルをアップロードしてください。")
    else:
        filename = uploaded_file.name.lower()
        if not filename.endswith(".pdf"):
            errors.append("PDF形式のファイルのみサポートしています。")
    return errors


def render_results(result: models.VoucherAnalysisResult) -> None:
    if st is None:
        return

    if result.errors:
        for error in result.errors:
            st.error(error)
        return

    validation_rows = build_validation_rows(result.validation)
    requirements = result.validation.requirements
    total_checks = len(requirements)
    pass_count = sum(1 for status in requirements.values() if status.status is models.RequirementState.PASS)
    fail_count = sum(1 for status in requirements.values() if status.status is models.RequirementState.FAIL)
    pending_count = total_checks - pass_count - fail_count

    st.markdown("<div class='voucher-card'>", unsafe_allow_html=True)
    st.markdown("<div class='voucher-section-title'>検証サマリー</div>", unsafe_allow_html=True)
    summary_cols = st.columns(3)
    summary_cols[0].metric("チェック数", total_checks)
    summary_cols[1].metric("合格", pass_count)
    summary_cols[2].metric("要確認", fail_count + pending_count)

    if result.warnings:
        chips = "".join(
            f"<span class='voucher-chip warning'>{warning}</span>" for warning in result.warnings
        )
        st.markdown(chips, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='voucher-card'>", unsafe_allow_html=True)
    st.markdown("<div class='voucher-section-title'>検証結果</div>", unsafe_allow_html=True)
    if validation_rows:
        st.dataframe(validation_rows, use_container_width=True)
    else:
        st.info("検証結果はまだありません。")
    st.markdown("</div>", unsafe_allow_html=True)

    extracted_entries = format_extracted_fields(result.extracted)
    st.markdown("<div class='voucher-card'>", unsafe_allow_html=True)
    st.markdown("<div class='voucher-section-title'>抽出情報</div>", unsafe_allow_html=True)
    if extracted_entries:
        st.dataframe(extracted_entries, use_container_width=True)
    else:
        st.info("抽出された情報はありません。")

    if result.highlight_pdf:
        st.download_button(
            label="ハイライト付きPDFをダウンロード",
            data=result.highlight_pdf,
            file_name="voucher_highlight.pdf",
            mime="application/pdf",
            type="secondary",
        )
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    ensure_streamlit()
    st.set_page_config(page_title="Voucher Checker", layout="wide")
    st.markdown(
        """
        <style>
        .voucher-card {
            background: linear-gradient(145deg, rgba(23,28,38,0.95), rgba(16,20,27,0.95));
            border-radius: 18px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.8rem;
            border: 1px solid rgba(255,255,255,0.04);
            box-shadow: 0 24px 48px rgba(0,0,0,0.35);
        }
        .voucher-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.3rem 0.8rem;
            border-radius: 999px;
            background: rgba(148, 189, 255, 0.16);
            color: #9ecbff;
            font-size: 0.85rem;
            margin-right: 0.6rem;
            margin-bottom: 0.4rem;
        }
        .voucher-chip.warning {
            background: rgba(255, 193, 7, 0.16);
            color: #ffda6a;
        }
        .voucher-chip.error {
            background: rgba(255, 82, 82, 0.18);
            color: #ff9a9a;
        }
        .voucher-section-title {
            font-size: 1.05rem;
            font-weight: 600;
            margin-bottom: 0.8rem;
            letter-spacing: 0.03em;
        }
        .css-1xarl3l, .stDataFrame { font-size: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("配当バウチャー検証ダッシュボード")
    st.caption("配当バウチャーから重要項目を抽出し、ビジネス意思決定を支援します。")

    st.sidebar.header("設定")
    provider_label = st.sidebar.selectbox(
        "解析に利用するAPI",
        options=list(models.ProviderType),
        format_func=lambda provider: provider.value.capitalize(),
    )

    provider_key = get_provider_key(provider_label)
    env_var_name = PROVIDER_ENV_VARS.get(provider_label)
    if env_var_name:
        if provider_key:
            st.sidebar.success(f"{env_var_name} を読み込みました。")
        else:
            st.sidebar.info(
                (
                    f"{env_var_name} が未設定のため、ルールベース抽出を利用します。"
                    f"ローカル開発では .envrc に export {env_var_name}=\"...\" を指定し、"
                    "Streamlit Cloud では App settings > Secrets に同名のキーを追加してください。"
                )
            )

    with st.container():
        st.markdown("<div class='voucher-card'>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("バウチャーPDFをアップロード", type=["pdf"])
        analyze_button = st.button("解析を実行する", type="primary")
        st.markdown("</div>", unsafe_allow_html=True)

    if analyze_button:
        errors = validate_inputs(uploaded_file, provider_label)
        if errors:
            for error in errors:
                st.error(error)
            return

        file_bytes = uploaded_file.read()
        store = get_session_store()
        result = analyze_voucher(
            file_bytes,
            provider=provider_label,
            pdf_ingestor=PdfIngestor(),
            validator=VoucherValidator(),
            highlight_renderer=HighlightRenderer(),
            store=store,
            session_key="latest",
        )
        st.session_state["analysis_result"] = result

    if "analysis_result" in st.session_state:
        render_results(st.session_state["analysis_result"])
    else:
        st.info("PDFをアップロードして解析を実行してください。")


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
