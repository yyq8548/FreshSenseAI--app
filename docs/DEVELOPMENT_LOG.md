# FreshSense AI Development Log

This document tracks the evolution of the project from a CNN-based fruit
classifier into an Agentic AI application.

## Change Log

  Date         Milestone
  ------------ ------------------------------------------------ --------
  2025-03-15   Built DenseNet201 fruit freshness classifier
  2025-04-05   Streamlit application created
  2025-04-05   Integrated trained DenseNet201 model
  2025-05-02   Implemented image quality checking
  2025-10-02   Refactored to tool-based AI agent architecture
  2026-05-15   Planner，Rule-based Reasoning，Unit Testing
  2026-06-02   Scene Analysis + Threshold Tuning
  2026-07-01   Added a centralized configuration system for FreshSense AI.

------------------------------------------------------------------------

# Session 1 --- Foundation

## Goals

-   Convert the DenseNet201 notebook into a runnable application.
-   Build a basic AI agent around the vision model.

## Completed

-   Built a Streamlit web interface.
-   Added image upload capability.
-   Integrated the trained DenseNet201 model.
-   Implemented image quality checking (brightness and blur).
-   Added confidence-based decision logic.
-   Added user recommendations based on prediction results.

## Outcome

The project evolved from a Jupyter notebook into an interactive
application.

------------------------------------------------------------------------

# Session 2 --- Architecture Refactor

## Goals

Transform the project into a modular Agent architecture.

## Completed

### New Architecture

    FreshSense Agent
        │
        ├── ImageQualityTool
        ├── DenseNetVisionTool
        ├── ConfidenceTool
        └── RecommendationTool

### Major Changes

-   Introduced AgentState to maintain workflow state.
-   Refactored the system into independent tools.
-   Created FruitScannerAgent as the workflow orchestrator.
-   Added execution trace logging.
-   Separated business logic from the Streamlit UI.
-   Created reusable `agent/`, `tools/`, and `utils/` packages.

## Design Decisions

-   DenseNet201 is treated as a Tool rather than the Agent.
-   Agent controls workflow and autonomous decisions.
-   Modular design allows future tools without changing core logic.

------------------------------------------------------------------------

# Current Capabilities

-   Upload fruit images
-   Image quality assessment
-   DenseNet201 inference
-   Confidence evaluation
-   Autonomous retake decisions
-   Recommendation generation
-   Tool-based architecture

------------------------------------------------------------------------

# Planned Roadmap

## Phase 3

-   GPT-5 reasoning tool
-   Natural language explanations
-   Storage recommendations
-   Shelf-life estimation

## Phase 4

-   Agent planning engine
-   Dynamic workflow selection
-   Tool routing

## Phase 5

-   Conversation memory
-   Retrieval-Augmented Generation (RAG)
-   Food knowledge base

## Phase 6

-   Signed Windows installer and release validation
-   Optional hosted API deployment
-   GitHub Actions CI/CD
-   Unit tests

------------------------------------------------------------------------

# Resume Highlights

By the end of the project, the expected highlights include:

-   Agentic AI
-   Computer Vision
-   DenseNet201
-   Transfer Learning
-   Tool Orchestration
-   Shared Agent State
-   Modular Software Architecture
-   LLM Integration
-   Streamlit Deployment
-   Production-oriented ML Engineering

------------------------------------------------------------------------
