"""Reusable Streamlit components for FreshSense AI."""

from __future__ import annotations

from html import escape

import numpy as np
import streamlit as st

from agent.state import AgentState
from desktop.presenter import result_summary
from tools.explainability import GRADCAM_DISCLAIMER, render_gradcam_overlay
from ui.presentation import result_tone
from utils.config import SAFETY_NOTICE
from utils.feedback import build_feedback_url


def render_nav() -> None:
    st.markdown(
        """
        <nav class="fs-nav" aria-label="Primary navigation">
          <a class="fs-brand" href="#top">FreshSense AI</a>
          <div class="fs-nav-links">
            <a href="#scanner">Scanner</a><a href="#how-it-works">How it works</a>
            <a href="#samples">Samples</a><a href="#technology">Technology</a>
            <a href="https://github.com/yyq8548/FreshSenseAI--app" target="_blank" rel="noreferrer">GitHub</a>
            <a class="fs-nav-cta" href="#scanner">Try scanner</a>
          </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown('<div id="top" class="fs-anchor"></div>', unsafe_allow_html=True)
    copy, media = st.columns([1.12, 0.88], gap="large", vertical_alignment="center")
    with copy:
        st.markdown(
            """
            <section class="fs-hero">
              <div class="fs-eyebrow">VISION + RETRIEVAL + REASONING</div>
              <h1>Fruit freshness, explained by AI.</h1>
              <p class="fs-hero-copy">Photograph one apple, banana, or orange. FreshSense checks whether the photo is supported, classifies visible freshness patterns, retrieves reviewed food guidance, and explains what to do next.</p>
              <div class="fs-hero-actions">
                <a class="fs-primary-link" href="#scanner">Analyze a fruit</a>
                <a class="fs-text-link" href="#how-it-works">See how it works</a>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with media:
        st.markdown('<div class="fs-hero-media">', unsafe_allow_html=True)
        st.image("assets/freshsense-hero-still-life.png", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_empty_result(retrieval_label: str) -> None:
    st.markdown(
        f"""
        <div class="fs-result-empty">
          <div><div class="fs-result-status">READY FOR ONE CLEAR FRUIT PHOTO</div>
            <h3>Your result will appear here.</h3>
            <p>FreshSense withholds a freshness label when the photo is unsupported, unclear, or below the configured confidence checks.</p>
          </div>
          <div><div class="fs-source">Knowledge mode: {escape(retrieval_label)}</div>
            <div class="fs-route" aria-label="Quality, support, prediction, retrieval, and recommendation stages"><span></span><span></span><span></span><span></span><span></span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result(state: AgentState) -> None:
    summary = result_summary(state)
    tone = result_tone(state)
    accepted = state.decision == "accept_prediction"
    status = "Accepted visual result" if accepted else "Result withheld for safety"
    recommendation = state.recommendation or "No recommendation was generated."
    details = summary["details"] or recommendation
    st.markdown(
        f"""
        <div class="fs-result {tone}">
          <div class="fs-result-status">{escape(status.upper())}</div>
          <h3>{escape(summary['title'])}</h3>
          <div class="fs-metrics">
            <div class="fs-metric"><span>Confidence</span><strong>{escape(summary['confidence'])}</strong></div>
            <div class="fs-metric"><span>Visual risk</span><strong>{escape(summary['risk'])}</strong></div>
          </div>
          <p class="fs-result-copy">{escape(details)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if state.reasoning:
        st.markdown(
            f"""
            <div class="fs-advice">
              <div class="fs-advice-item"><span>Shelf-life estimate</span><strong>{escape(state.reasoning.shelf_life_estimate)}</strong></div>
              <div class="fs-advice-item"><span>Storage guidance</span><strong>{escape(state.reasoning.storage_advice)}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    for warning in state.structured_warnings:
        if warning.level == "error":
            st.error(warning.message)
        elif warning.level == "suggestion":
            st.info(warning.message)
        else:
            st.warning(warning.message)
    if tone == "danger":
        st.error(recommendation)
    elif tone == "caution":
        st.warning(recommendation)
    else:
        st.success(recommendation)
    st.caption(SAFETY_NOTICE)
    st.link_button(
        "Report incorrect result",
        build_feedback_url(state),
        use_container_width=True,
        help="Opens a prefilled GitHub issue. FreshSense does not attach your photo.",
    )
    _render_evidence(state)


def _render_evidence(state: AgentState) -> None:
    explanation = state.metadata.get("explainability", {})
    heatmap = explanation.get("heatmap") if explanation else None
    if isinstance(heatmap, np.ndarray):
        with st.expander("Model influence view"):
            st.image(
                render_gradcam_overlay(state.image, heatmap),
                caption=GRADCAM_DISCLAIMER,
                use_container_width=True,
            )

    with st.expander("Retrieved knowledge"):
        if state.retrieval and state.retrieval.documents:
            method = state.metadata.get("retrieval", {}).get("method", "unknown")
            st.caption(f"Retrieval method: {method.replace('_', ' ')}")
            for document in state.retrieval.documents:
                score = document.get("retrieval_score")
                score_text = f" | relevance {score:.3f}" if isinstance(score, (int, float)) else ""
                st.markdown(f"**{document.get('topic', 'Food guidance')}**{score_text}\n\n{document.get('text', '')}")
        else:
            st.write("No fruit-specific knowledge was used for this result.")

    with st.expander("Technical details"):
        if state.quality:
            st.write({
                "brightness": round(state.quality.brightness, 2),
                "edge_strength": round(state.quality.edge_strength, 2),
                "dark": state.quality.is_dark,
                "blurry": state.quality.is_blurry,
                "overexposed": state.quality.is_overexposed,
            })
        if state.scene:
            st.write({
                "foreground_ratio": round(state.scene.foreground_ratio, 4),
                "fruit_too_small": state.scene.fruit_is_too_small,
                "likely_empty_scene": state.scene.likely_empty_scene,
            })
        gate = state.metadata.get("open_set_gate")
        if gate:
            st.write({"supported_input_gate": gate})

    with st.expander("Agent trace"):
        for entry in state.trace:
            st.write(entry)


def render_workflow() -> None:
    st.markdown(
        """
        <div id="how-it-works" class="fs-anchor"></div>
        <section class="fs-section fs-workflow">
          <div><h2>One photo, five accountable decisions.</h2>
            <p class="fs-section-intro">The interface keeps the recommendation simple while preserving the evidence path for technical review.</p></div>
          <div class="fs-workflow-list">
            <div class="fs-workflow-item"><strong>See</strong><div><h3>Inspect the image</h3><p>Check brightness, sharpness, exposure, framing, and foreground size.</p></div></div>
            <div class="fs-workflow-item"><strong>Validate</strong><div><h3>Confirm supported input</h3><p>Check for one supported fruit type before producing a freshness label.</p></div></div>
            <div class="fs-workflow-item"><strong>Predict</strong><div><h3>Classify visible patterns</h3><p>Run DenseNet201 only after model and artifact validation passes.</p></div></div>
            <div class="fs-workflow-item"><strong>Retrieve</strong><div><h3>Ground the guidance</h3><p>Find reviewed storage, shelf-life, spoilage, and safety knowledge.</p></div></div>
            <div class="fs-workflow-item"><strong>Recommend</strong><div><h3>Explain the next action</h3><p>Combine evidence, warnings, and retrieved guidance with a deterministic fallback.</p></div></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_technology() -> None:
    st.markdown(
        """
        <div id="technology" class="fs-anchor"></div>
        <section class="fs-section fs-trust">
          <h2>Designed for transparent AI evaluation.</h2>
          <p class="fs-section-intro">FreshSense is a local-first decision-support system, not a claim that a photo can prove food safety.</p>
          <div class="fs-trust-list">
            <div class="fs-trust-item"><strong>DenseNet201 vision model</strong><span>Six configured classes across apple, banana, and orange.</span></div>
            <div class="fs-trust-item"><strong>Supported-input gate</strong><span>Withholds labels when the image does not clearly match one supported fruit type.</span></div>
            <div class="fs-trust-item"><strong>Local semantic RAG</strong><span>Retrieves reviewed food knowledge on device with a visible keyword fallback.</span></div>
            <div class="fs-trust-item"><strong>Grounded reasoning</strong><span>Uses optional GPT-5 reasoning with reviewed deterministic guidance when unavailable.</span></div>
            <div class="fs-trust-item"><strong>Shared agent pipeline</strong><span>Streamlit, desktop, and REST API surfaces reuse the same analysis behavior.</span></div>
            <div class="fs-trust-item"><strong>Tested handoff assets</strong><span>Includes CI, evaluation, model-card, pilot, API, and Windows release workflows.</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        f"""
        <footer class="fs-footer">
          <div>Built by Yeqiao Yu for practical AI product evaluation.</div>
          <div><a href="https://github.com/yyq8548/FreshSenseAI--app" target="_blank" rel="noreferrer">View source on GitHub</a><br>{escape(SAFETY_NOTICE)}</div>
        </footer>
        """,
        unsafe_allow_html=True,
    )
