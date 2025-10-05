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

    if result.warnings:
        for warning in result.warnings:
            st.warning(warning)

    st.subheader("検証結果")
    validation_rows = build_validation_rows(result.validation)
    if validation_rows:
        st.table(validation_rows)
    else:
        st.info("検証結果はまだありません。")

    st.subheader("抽出情報")
    extracted_entries = format_extracted_fields(result.extracted)
    if extracted_entries:
        st.table(extracted_entries)
    else:
        st.info("抽出された情報はありません。")

    if result.highlight_pdf:
        st.download_button(
            label="ハイライト付きPDFをダウンロード",
            data=result.highlight_pdf,
            file_name="voucher_highlight.pdf",
            mime="application/pdf",
        )


def main() -> None:
    ensure_streamlit()
    st.set_page_config(page_title="Voucher Checker", layout="wide")
    st.title("配当バウチャー検証アプリ")

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

    uploaded_file = st.file_uploader("バウチャーPDFをアップロード", type=["pdf"])
    analyze_button = st.button("解析を実行する", type="primary")

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
