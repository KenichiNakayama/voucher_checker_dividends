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

    extracted_entries = format_extracted_fields(result.extracted)

    summary_tab, detail_tab, document_tab = st.tabs(["サマリー", "抽出結果", "原本プレビュー"])

    with summary_tab:
        st.markdown("<div class='voucher-card compact'>", unsafe_allow_html=True)
        st.markdown("<div class='voucher-section-title'>検証サマリー</div>", unsafe_allow_html=True)
        metric_cols = st.columns(4)
        metric_cols[0].metric("チェック数", total_checks)
        metric_cols[1].metric("合格", pass_count)
        metric_cols[2].metric("要確認", fail_count + pending_count)
        completion_ratio = 0 if total_checks == 0 else pass_count / total_checks
        metric_cols[3].metric("達成率", f"{completion_ratio * 100:.0f}%")

        if result.warnings:
            chips = "".join(
                f"<span class='voucher-chip warning'>{warning}</span>" for warning in result.warnings
            )
            st.markdown(f"<div class='voucher-chip-row'>{chips}</div>", unsafe_allow_html=True)

        if validation_rows:
            st.dataframe(validation_rows, use_container_width=True)
        else:
            st.info("検証結果はまだありません。")
        st.markdown("</div>", unsafe_allow_html=True)

    with detail_tab:
        st.markdown("<div class='voucher-card compact'>", unsafe_allow_html=True)
        st.markdown("<div class='voucher-section-title'>抽出結果</div>", unsafe_allow_html=True)
        if extracted_entries:
            for chunk_start in range(0, len(extracted_entries), 3):
                cols = st.columns(3)
                for col, entry in zip(cols, extracted_entries[chunk_start : chunk_start + 3]):
                    with col:
                        st.markdown(
                            f"<div class='voucher-pill'><span class='label'>{entry['label']}</span>"
                            f"<span class='value'>{entry['value'] or '―'}</span>"
                            f"<span class='confidence'>Conf. {entry['confidence']}</span></div>",
                            unsafe_allow_html=True,
                        )
        else:
            st.info("抽出された情報はありません。")
        st.markdown("</div>", unsafe_allow_html=True)

    with document_tab:
        st.markdown("<div class='voucher-card compact'>", unsafe_allow_html=True)
        st.markdown("<div class='voucher-section-title'>原本ダウンロード</div>", unsafe_allow_html=True)
        if result.highlight_pdf:
            st.download_button(
                label="ハイライト付きPDFをダウンロード",
                data=result.highlight_pdf,
                file_name="voucher_highlight.pdf",
                mime="application/pdf",
                type="primary",
            )
        else:
            st.info("ハイライト対象がないため原本をそのまま返却しています。")

        with st.expander("解析テキストビュー", expanded=False):
            for page_number, page in enumerate(result.parsed_document.pages, start=1):
                st.markdown(f"<div class='voucher-page-label'>Page {page_number}</div>", unsafe_allow_html=True)
                st.code(page or "", language="text")
        st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    ensure_streamlit()
    st.set_page_config(page_title="Voucher Checker", layout="wide")
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 2.5rem;
            max-width: 1200px;
        }
        .voucher-card {
            background: rgba(19, 25, 36, 0.9);
            border-radius: 18px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.8rem;
            border: 1px solid rgba(255,255,255,0.06);
            box-shadow: 0 28px 60px rgba(12, 18, 28, 0.45);
            backdrop-filter: blur(18px);
        }
        .voucher-card.compact {
            padding: 1.4rem 1.6rem;
        }
        .voucher-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.85rem;
            border-radius: 999px;
            background: rgba(95, 165, 255, 0.16);
            color: #a8d4ff;
            font-size: 0.8rem;
            margin-right: 0.6rem;
            margin-bottom: 0.4rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .voucher-chip.warning {
            background: rgba(255, 193, 7, 0.18);
            color: #ffd666;
        }
        .voucher-chip-row {
            display: flex;
            flex-wrap: wrap;
            margin-top: 0.8rem;
            margin-bottom: 0.6rem;
        }
        .voucher-section-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            letter-spacing: 0.04em;
        }
        .voucher-pill {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 0.9rem 1rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .voucher-pill .label {
            display: block;
            font-size: 0.75rem;
            letter-spacing: 0.06em;
            color: rgba(255,255,255,0.55);
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .voucher-pill .value {
            display: block;
            font-size: 1.1rem;
            font-weight: 600;
            color: #f5f7fb;
        }
        .voucher-pill .confidence {
            display: block;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.45);
            margin-top: 0.25rem;
        }
        .voucher-page-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            color: rgba(255,255,255,0.45);
            margin-top: 1rem;
            margin-bottom: 0.3rem;
            letter-spacing: 0.08em;
        }
        .stTabs [role="tab"] {
            background: rgba(15,20,30,0.7);
            border-radius: 12px 12px 0 0;
            padding: 0.7rem 1.2rem;
            border: none;
            color: rgba(255,255,255,0.6);
        }
        .stTabs [role="tab"][aria-selected="true"] {
            background: rgba(47, 128, 237, 0.18);
            color: #e2efff;
            border-bottom: 2px solid rgba(47, 128, 237, 0.65);
        }
        .stTabs [role="tab"]:focus {
            outline: none;
            box-shadow: none;
        }
        div[data-testid="stMetricDelta"] {
            font-size: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("配当バウチャーAIアシスタント")
    st.caption("配当決議書から重要項目を抽出し、証票確認をサポートします。")

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

    st.sidebar.markdown("---")
    st.sidebar.metric("最新の合格数", st.session_state.get("analysis_result", models.VoucherAnalysisResult()).validation.overall_status.value.upper())

    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    with st.container():
        st.markdown("<div class='voucher-card'>", unsafe_allow_html=True)
        upload_key = f"voucher_upload_{st.session_state['uploader_key']}"
        uploaded_file = st.file_uploader("バウチャーPDFをアップロード", type=["pdf"], key=upload_key)
        action_cols = st.columns([1, 1, 6])
        analyze_button = action_cols[0].button("解析を実行する", type="primary")
        refresh_button = action_cols[1].button("リフレッシュ", type="secondary")
        action_cols[2].write("")
        st.markdown("</div>", unsafe_allow_html=True)

    if refresh_button:
        if "analysis_result" in st.session_state:
            st.session_state.pop("analysis_result", None)
        if "analysis_store" in st.session_state:
            store = st.session_state["analysis_store"]
            store.clear()
        st.session_state["uploader_key"] += 1
        st.experimental_rerun()

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
