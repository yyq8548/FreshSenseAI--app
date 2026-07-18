"""FreshSense AI Streamlit interface."""

from __future__ import annotations

from io import BytesIO

import streamlit as st
from PIL import Image, UnidentifiedImageError

from agent.fruit_agent import FruitScannerAgent
from ui.components import (
    render_empty_result,
    render_footer,
    render_hero,
    render_nav,
    render_result,
    render_technology,
    render_workflow,
)
from ui.presentation import SampleImage, analysis_signature, discover_sample_images
from ui.styles import FRESHSENSE_CSS
from utils.config import (
    APP_ICON,
    APP_LAYOUT,
    APP_TITLE,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
    PROJECT_ROOT,
    REQUIRE_OPEN_SET_GATE,
    SAFETY_NOTICE,
)
from utils.startup import StartupValidationError, validate_startup


st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
st.markdown(FRESHSENSE_CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_agent() -> FruitScannerAgent:
    """Validate and load expensive runtime assets once per Streamlit process."""
    validate_startup(
        MODEL_PATH,
        KNOWLEDGE_BASE_PATH,
        FRUIT_CATALOG_PATH,
        OPEN_SET_GATE_PATH,
        REQUIRE_OPEN_SET_GATE,
    )
    return FruitScannerAgent(
        model_path=MODEL_PATH,
        catalog_path=FRUIT_CATALOG_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
        open_set_gate_path=OPEN_SET_GATE_PATH,
        require_open_set_gate=REQUIRE_OPEN_SET_GATE,
    )


def _initialize_session() -> None:
    defaults = {
        "source_name": None,
        "image_bytes": None,
        "latest_result": None,
        "latest_signature": None,
        "uploader_version": 0,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _select_sample(sample: SampleImage) -> None:
    st.session_state.source_name = f"{sample.display_name} sample"
    st.session_state.image_bytes = sample.path.read_bytes()
    st.session_state.latest_result = None
    st.session_state.latest_signature = None
    st.session_state.uploader_version += 1


def _current_image() -> tuple[Image.Image | None, str | None, str | None]:
    payload = st.session_state.image_bytes
    source_name = st.session_state.source_name
    if not payload or not source_name:
        return None, None, None
    try:
        image = Image.open(BytesIO(payload)).convert("RGB")
        return image, source_name, analysis_signature(source_name, payload)
    except (UnidentifiedImageError, OSError, ValueError):
        return None, source_name, None


def _sample_button(sample: SampleImage, key: str, label: str) -> None:
    if st.button(label, key=key, use_container_width=True):
        _select_sample(sample)
        st.rerun()


def _render_scanner(agent: FruitScannerAgent | None, startup_error: str | None) -> None:
    samples = discover_sample_images(PROJECT_ROOT / "sample_images", per_fruit=2)
    first_by_fruit: dict[str, SampleImage] = {}
    for sample in samples:
        first_by_fruit.setdefault(sample.fruit_id, sample)

    st.markdown('<div id="scanner" class="fs-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <section class="fs-section">
          <h2>Try the scanner.</h2>
          <p class="fs-section-intro">Choose one clear photo or start with a bundled sample. Uploaded photos are analyzed in memory and are not retained by the Streamlit app.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="fs-scope"><span class="fs-chip">Apple</span><span class="fs-chip">Banana</span><span class="fs-chip">Orange</span><span class="fs-chip">One fruit type per photo</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="fs-safety">{SAFETY_NOTICE}</div>', unsafe_allow_html=True)
    if startup_error:
        st.error(startup_error)

    image_col, result_col = st.columns([1.02, 0.98], gap="large")
    with image_col:
        st.markdown('<div class="fs-panel-label">Photo input</div>', unsafe_allow_html=True)
        current, source_name, _ = _current_image()
        if current is None:
            st.markdown(
                '<div class="fs-empty"><div><strong>Choose a clear fruit photo</strong>Use a close, well-lit image with one supported fruit type.</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.image(current, caption=source_name, use_container_width=True)

        uploaded = st.file_uploader(
            "Upload a fruit photo",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"fruit_upload_{st.session_state.uploader_version}",
            help="Use a close, well-lit photo containing one apple, banana, or orange fruit type.",
        )
        if uploaded is not None:
            payload = uploaded.getvalue()
            new_signature = analysis_signature(uploaded.name, payload)
            old_signature = (
                analysis_signature(st.session_state.source_name, st.session_state.image_bytes)
                if st.session_state.source_name and st.session_state.image_bytes
                else None
            )
            if new_signature != old_signature:
                st.session_state.source_name = uploaded.name
                st.session_state.image_bytes = payload
                st.session_state.latest_result = None
                st.session_state.latest_signature = None
                st.rerun()

        st.caption("Or load a bundled sample")
        sample_columns = st.columns(3)
        for column, fruit_id in zip(sample_columns, ("apple", "banana", "orange")):
            sample = first_by_fruit.get(fruit_id)
            if sample:
                with column:
                    _sample_button(sample, f"scanner_sample_{fruit_id}", sample.display_name)

        current, _, signature = _current_image()
        analyze = st.button(
            "Analyze freshness",
            type="primary",
            use_container_width=True,
            disabled=current is None or agent is None,
        )
        if analyze and current is not None and agent is not None and signature:
            with st.spinner("Checking image quality, support, model evidence, and guidance..."):
                try:
                    st.session_state.latest_result = agent.run(current)
                    st.session_state.latest_signature = signature
                except Exception:
                    st.session_state.latest_result = None
                    st.session_state.latest_signature = None
                    st.error("The analysis could not be completed. Try another clear photo or restart the application.")

    with result_col:
        st.markdown('<div class="fs-panel-label">Analysis</div>', unsafe_allow_html=True)
        _, _, signature = _current_image()
        if st.session_state.latest_result is not None and signature == st.session_state.latest_signature:
            render_result(st.session_state.latest_result)
        else:
            retrieval_label = "local semantic embeddings"
            if agent is not None and not agent.retriever_tool.semantic_ready:
                retrieval_label = "keyword fallback"
            render_empty_result(retrieval_label)


def _render_samples() -> None:
    samples = discover_sample_images(PROJECT_ROOT / "sample_images", per_fruit=2)
    st.markdown('<div id="samples" class="fs-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <section class="fs-section">
          <h2>Start with a known input.</h2>
          <p class="fs-section-intro">These bundled photos help you explore the interaction. They show supported fruit types, not independent accuracy evidence.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    for row_start in range(0, len(samples), 3):
        columns = st.columns(3, gap="medium")
        for column, sample in zip(columns, samples[row_start : row_start + 3]):
            with column:
                st.image(
                    sample.path,
                    caption=f"{sample.display_name} sample",
                    use_container_width=True,
                )
                _sample_button(
                    sample,
                    f"gallery_{sample.fruit_id}_{sample.path.stem}",
                    f"Load {sample.display_name.lower()} sample",
                )


def main() -> None:
    _initialize_session()
    render_nav()
    render_hero()
    agent = None
    startup_error = None
    try:
        agent = load_agent()
    except (StartupValidationError, RuntimeError):
        startup_error = (
            "FreshSense could not load its validated vision model, supported-input gate, "
            "or knowledge assets. Check the local installation before analyzing a photo."
        )
    _render_scanner(agent, startup_error)
    render_workflow()
    _render_samples()
    render_technology()
    render_footer()


if __name__ == "__main__":
    main()
