# Fictional insurance-policy RAG companion

This isolated example demonstrates how FreshSense's prototype patterns transfer
to an expert business workflow: prepare a reviewed knowledge source, retrieve
relevant passages, provide citations, abstain when evidence is missing, expose
a typed API, evaluate expected behavior, and preserve human decision authority.

The policy is fictional and authored for this repository. The example cannot
approve, deny, price, or adjudicate a claim and must not be used for insurance
or legal advice.

Run the evaluation:

```powershell
python scripts\evaluate_insurance_rag.py
```

Run the companion API:

```powershell
uvicorn examples.insurance_rag.app:app --port 8010
```

Then use `POST /ask` with `{"question": "What is the deductible?"}`. The
response contains retrieved fictional policy language, citations, retrieval
method, disclaimer, and a mandatory-human-review flag.
