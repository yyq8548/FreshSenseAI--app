import streamlit as st
from PIL import Image

from agent.fruit_agent import FruitScannerAgent
from desktop.presenter import supported_scope_text
from utils.config import (
    APP_ICON,
    APP_LAYOUT,
    APP_TITLE,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    SAFETY_NOTICE,
)
from utils.startup import StartupValidationError, validate_startup

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
st.title(f"{APP_ICON} {APP_TITLE}")
st.caption("Agentic computer vision assistant for produce quality assessment")
st.info(supported_scope_text())
st.warning(SAFETY_NOTICE)

st.write(
    "Upload a fruit image. The agent checks image quality, uses scene analysis as advisory feedback, "
    "runs DenseNet201 inference, retrieves food knowledge, reasons over the result, and returns a recommendation."
)

try:
    validate_startup(MODEL_PATH, KNOWLEDGE_BASE_PATH, FRUIT_CATALOG_PATH)
    agent = FruitScannerAgent(
        model_path=MODEL_PATH,
        catalog_path=FRUIT_CATALOG_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
    )
    if agent.retriever_tool.semantic_ready:
        st.caption("Knowledge retrieval: local semantic embeddings")
    else:
        st.caption("Knowledge retrieval: keyword fallback")
except (StartupValidationError, RuntimeError):
    st.error(
        "FreshSense is temporarily unavailable because its vision model or runtime "
        "assets could not be loaded. Please contact the service operator."
    )
    st.stop()
uploaded_file = st.file_uploader("Upload fruit image", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Uploaded Image", width="stretch")

    with st.spinner("FreshSense Agent is analyzing..."):
        state = agent.run(image)

    st.subheader("Agent Decision")
    st.write(f"**Decision:** {state.decision}")
    st.write(f"**Status:** {state.status}")

    st.subheader("Scene Analysis")
    if state.scene:
        st.write(f"**Foreground Ratio:** {state.scene.foreground_ratio:.4f}")
        st.write(f"**Fruit Too Small:** {state.scene.fruit_is_too_small}")
        st.write(f"**Likely Empty Scene:** {state.scene.likely_empty_scene}")
        st.write(f"**Advisory Only:** Yes — scene analysis does not block inference.")

    st.subheader("Prediction")
    if state.decision == "uncertain_input":
        st.write("**Result:** Unsupported or uncertain photo")
        st.write("The tentative model class was withheld.")
    elif state.prediction:
        st.write(f"**Class:** {state.prediction.class_name}")
        st.write(f"**Confidence:** {state.prediction.confidence:.2%}")
    else:
        st.write("No prediction was generated because the agent stopped early.")

    st.subheader("Retrieved Knowledge")
    if state.retrieval and state.retrieval.documents:
        st.write(f"**Query:** {state.retrieval.query}")
        st.write(
            f"**Method:** {state.metadata.get('retrieval', {}).get('method', 'unknown')}"
        )
        for doc in state.retrieval.documents:
            score = doc.get("retrieval_score")
            score_text = f" · score {score:.3f}" if isinstance(score, (int, float)) else ""
            st.markdown(
                f"- **{doc.get('id')}** ({doc.get('topic')}{score_text}): {doc.get('text')}"
            )
    else:
        st.write("No knowledge documents retrieved.")

    st.subheader("Reasoning")
    if state.reasoning:
        st.write(f"**Source:** {state.reasoning.source}")
        st.write(f"**Risk Level:** {state.reasoning.risk_level}")
        st.write(f"**Explanation:** {state.reasoning.explanation}")
        st.write(f"**Shelf-life Estimate:** {state.reasoning.shelf_life_estimate}")
        st.write(f"**Storage Advice:** {state.reasoning.storage_advice}")

    st.subheader("Image Quality")
    if state.quality:
        st.write(f"**Brightness:** {state.quality.brightness:.2f}")
        st.write(f"**Edge Strength:** {state.quality.edge_strength:.2f}")
        st.write(f"**Dark:** {state.quality.is_dark}")
        st.write(f"**Blurry:** {state.quality.is_blurry}")
        st.write(f"**Overexposed:** {state.quality.is_overexposed}")

    if state.structured_warnings:
        for warning in state.structured_warnings:
            if warning.level == "error":
                st.error(warning.message)
            elif warning.level == "suggestion":
                st.info(warning.message)
            else:
                st.warning(warning.message)

    st.subheader("Recommendation")
    st.success(state.recommendation)
    st.caption(SAFETY_NOTICE)

    with st.expander("Agent Trace"):
        for step in state.trace:
            st.write(f"- {step}")
else:
    st.info("Upload a fruit photo to start.")
