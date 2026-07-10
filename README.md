# 🍎 FreshSense AI

> **An Agentic AI system for fruit freshness assessment using Computer
> Vision, GPT-5, and Retrieval-Augmented Generation (RAG).**

![Python](https://img.shields.io/badge/Python-3.11-blue)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-orange)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--5-green)
![RAG](https://img.shields.io/badge/RAG-Enabled-success)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![CI](https://img.shields.io/badge/GitHub_Actions-Passing-brightgreen)

------------------------------------------------------------------------

# 🚀 Overview

FreshSense AI is a production-style AI agent that combines **Computer
Vision, GPT‑5, and Retrieval-Augmented Generation (RAG)** to analyze
fruit freshness and generate grounded storage, shelf-life, and food
safety recommendations.

Unlike a traditional image classification demo, FreshSense demonstrates
a complete AI workflow:

-   🧠 DenseNet201 computer vision
-   🤖 GPT‑5 reasoning
-   📚 Retrieval-Augmented Generation (RAG)
-   🛠 Modular tool-based AI agent
-   📈 Confidence validation
-   🧪 Automated testing with GitHub Actions
-   🔄 Rule-based fallback for reliability

------------------------------------------------------------------------

# 🏗 System Architecture

``` mermaid
flowchart TD
    A[Upload Image]
    B[Image Quality Assessment]
    C[Scene Analysis]
    D[DenseNet201 Vision]
    E[Confidence Validation]
    F[Food Knowledge Retriever]
    G[GPT-5 Reasoning]
    H[Natural Language Recommendation]

    A --> B --> C --> D --> E --> F --> G --> H
```

------------------------------------------------------------------------

# ✨ Features

  Feature             Description
  ------------------- ------------------------------------------------
  🧠 DenseNet201      Fruit freshness classification
  📷 Image Quality    Blur, brightness and exposure detection
  🎯 Confidence       Confidence validation
  🤖 GPT‑5            Natural-language reasoning
  📚 RAG              Food knowledge retrieval
  🔍 Explainable AI   Grounded explanations with retrieved knowledge
  🖼 Sample Images     Built-in testing images
  🧪 Testing          PyTest + GitHub Actions

------------------------------------------------------------------------

# ⚙️ AI Pipeline

1.  Upload a fruit image.
2.  Analyze image quality.
3.  Perform scene analysis.
4.  Predict freshness using DenseNet201.
5.  Validate confidence.
6.  Retrieve relevant food knowledge.
7.  Generate GPT‑5 reasoning.
8.  Produce storage and shelf-life recommendations.

------------------------------------------------------------------------

# 📸 Sample Images

The repository includes ready-to-use testing images.

``` text
sample_images/
├── apples/
├── bananas/
└── oranges/
```

Run the application:

``` bash
streamlit run app.py
```

Then upload any image from the **sample_images** folder to experience
the complete AI workflow immediately.

------------------------------------------------------------------------

# 💡 Example Output

**Prediction**

``` text
Fresh Banana
Confidence: 100%
```

**Retrieved Knowledge**

``` text
banana_storage
banana_overripe
banana_freezing
```

**GPT-5 Reasoning**

``` text
The banana appears fresh with no visible spoilage.
Store at room temperature until ripe, then refrigerate.
```

**Recommendation**

``` text
Shelf Life:
1–3 days at room temperature.

Storage:
Refrigerate after ripening.
```

------------------------------------------------------------------------

# 📁 Project Structure

``` text
FreshSense-AI/
├── agent/
├── tools/
├── utils/
├── tests/
├── sample_images/
├── data/
├── docs/
├── models/
├── app.py
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

# ▶️ Quick Start

``` bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
streamlit run app.py
```

## Windows desktop application

FreshSense also includes a native Windows interface designed for people who do
not use Python or a terminal. Developers can run it with:

``` powershell
python desktop_app.py
```

Create the self-contained Windows distribution with:

``` powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

The distributable application is written to
`dist/FreshSenseAI/FreshSenseAI.exe`. Ship the entire `FreshSenseAI` directory;
end users do not install Python, TensorFlow, or a virtual environment.

### Private local scan history

The Windows desktop application keeps an optional recent-scan history on the
user's computer. Use **View scan history** to review results, export them to
CSV, or clear them after confirmation.

FreshSense stores only:

- scan date and time;
- the image's base file name, never its full path;
- the displayed result, confidence when accepted, risk, decision, and status.

Photos are not copied or retained. Uncertain results do not store the tentative
class or confidence. History is limited to the 200 newest records and is stored
under `%LOCALAPPDATA%\FreshSense\scan_history.json` on Windows. Developers and
managed installations can override this location with `FRESHSENSE_HISTORY_PATH`.

The history file remains local unless the user explicitly chooses **Export
CSV**. FreshSense does not upload scan history to GitHub, OpenAI, or a cloud
service.

FreshSense now fails closed when the configured model is missing or invalid.
Before starting the app, provide a trained Keras model at
`models/densenet201.h5`, or configure an absolute path:

``` bash
export FRESHSENSE_MODEL_PATH=/absolute/path/to/densenet201.h5
```

The knowledge base defaults to `data/food_knowledge_base.json` and can be
overridden with `FRESHSENSE_KNOWLEDGE_BASE_PATH`. Both assets are validated at
startup. The application will not generate a placeholder prediction when the
model cannot be loaded.

## Configuration-driven fruit support

Supported fruits and model output labels are defined in
`data/fruit_catalog.json`. The catalog is the single source of truth for:

- the exact model-output class order;
- each class's fruit and fresh/rotten state;
- user-facing fruit names;
- fresh shelf-life estimates; and
- fresh storage guidance.

The catalog can be overridden with `FRESHSENSE_FRUIT_CATALOG_PATH`. FreshSense
validates it at startup and fails closed when labels are duplicated, a fruit is
missing either its fresh or rotten class, a class references an unknown fruit,
or the knowledge base has no entry for a configured fruit.

To add a fruit:

1. Train or fine-tune a model containing fresh and rotten outputs for the new
   fruit.
2. Add those labels to the catalog's `classes` list in the exact order returned
   by the model.
3. Add the fruit's display name, shelf life, and storage guidance to `fruits`.
4. Add at least one reviewed entry for the fruit to
   `data/food_knowledge_base.json`.
5. Run `pytest` and rebuild the desktop application.

No inference, retrieval, reasoning, recommendation, or desktop presentation
code needs to be rewritten for the new fruit. A newly trained model is still
required because configuration cannot add visual recognition by itself.

## Unsupported and uncertain photos

FreshSense exposes a dedicated **Unsupported or uncertain photo** result when
the prediction does not pass either of these application-level gates:

- minimum model confidence (`MIN_CONFIDENCE`); or
- minimum separation between the two most likely classes
  (`MIN_PREDICTION_MARGIN`).

For these results, FreshSense withholds the tentative class and does not
generate fruit-specific shelf-life or storage guidance. The desktop and
Streamlit interfaces also state that the current model supports one apple,
banana, or orange fruit type per photo.

These gates reduce ambiguous results but are not a general non-fruit detector.
A photograph outside the training distribution can still receive a high
softmax score. Production-grade out-of-distribution rejection requires a
reviewed negative-image test set and either a dedicated detector or a model
trained with explicit unsupported examples.

## Enable GPT‑5

``` bash
export OPENAI_API_KEY=YOUR_API_KEY
```

If no API key is configured, the application automatically falls back to
the built-in rule-based reasoning engine.

> **Safety notice:** FreshSense provides visual decision support only. It
> cannot establish that food is safe to consume or detect internal spoilage,
> contamination, odor, or texture. When in doubt, do not consume the fruit.

------------------------------------------------------------------------

# 🧪 Testing

``` bash
pytest
```

Every push automatically runs the test suite through GitHub Actions.

------------------------------------------------------------------------

# 🛠 Technology Stack

-   Python 3.11
-   TensorFlow / Keras
-   DenseNet201
-   Streamlit
-   OpenAI GPT‑5
-   Retrieval-Augmented Generation (RAG)
-   PyTest
-   GitHub Actions
-   Pillow
-   NumPy

------------------------------------------------------------------------

# 🗺 Roadmap

-   ✅ Computer Vision
-   ✅ Tool-based AI Agent
-   ✅ GPT‑5 Reasoning
-   ✅ Local RAG
-   ⏳ Embedding-based Semantic RAG
-   ⏳ Vector Database
-   ⏳ Conversation Memory
-   ⏳ REST API
-   ⏳ Cloud Deployment

------------------------------------------------------------------------

# 👨‍💻 Author

**Yeqiao Yu**

------------------------------------------------------------------------

⭐ If you found this project interesting, please consider giving it a
star!
