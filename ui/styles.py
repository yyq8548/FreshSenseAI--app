"""Brand tokens and CSS for the Streamlit interface."""

FRESHSENSE_CSS = r"""
<style>
:root {
  --fs-bg: #f6f7f2; --fs-surface: #fff; --fs-soft: #eef3e8;
  --fs-warm: #f7efe5; --fs-text: #172019; --fs-muted: #667068;
  --fs-line: #d9dfd5; --fs-accent: #416b49; --fs-strong: #294d31;
  --fs-shadow: 0 24px 60px rgba(32, 55, 37, .09);
}
html { scroll-behavior: smooth; }
.stApp { background: var(--fs-bg); color: var(--fs-text); }
.stApp, .stApp p, .stApp button, .stApp input { font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif; }
.main .block-container { max-width: 1240px; padding: 0 2rem 5rem; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none; }

.fs-nav { position: sticky; top: 0; z-index: 20; display: flex; align-items: center;
  justify-content: space-between; min-height: 70px; margin: 0 -2rem; padding: 0 2rem;
  background: rgba(246,247,242,.92); border-bottom: 1px solid rgba(217,223,213,.82);
  backdrop-filter: blur(16px); }
.fs-brand { color: var(--fs-text) !important; font-weight: 780; letter-spacing: -.03em; font-size: 1.16rem; }
.fs-nav-links { display: flex; align-items: center; gap: 1.4rem; }
.fs-nav a { color: var(--fs-muted); text-decoration: none; font-size: .91rem; font-weight: 650; }
.fs-nav a:hover { color: var(--fs-strong); }
.fs-nav .fs-nav-cta { color: #fff; background: var(--fs-strong); padding: .64rem .95rem; border-radius: 999px; }

.fs-hero { padding: clamp(4rem,8vw,7.8rem) 0 3.2rem; }
.fs-eyebrow { color: var(--fs-accent); font-size: .78rem; font-weight: 800; letter-spacing: .16em; margin-bottom: 1.15rem; }
.fs-hero h1, .fs-section h2, .fs-result h3, .fs-result-empty h3 {
  font-family: Georgia, "Times New Roman", serif; letter-spacing: -.05em; }
.fs-hero h1 { font-size: clamp(3.4rem,6.8vw,6.8rem); line-height: .94; margin: 0; max-width: 760px; }
.fs-hero-copy { color: var(--fs-muted); font-size: clamp(1.05rem,1.5vw,1.3rem); line-height: 1.62; max-width: 620px; margin: 1.5rem 0 1.8rem; }
.fs-hero-actions { display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap; }
.fs-primary-link { display: inline-block; color: #fff !important; background: var(--fs-strong); text-decoration: none; font-weight: 760; padding: .86rem 1.15rem; border-radius: 999px; }
.fs-text-link { color: var(--fs-strong) !important; font-weight: 760; text-underline-offset: 4px; }
.fs-hero-media img { border-radius: 24px; min-height: 420px; object-fit: cover; box-shadow: var(--fs-shadow); }

.fs-anchor { scroll-margin-top: 92px; }
.fs-section { padding: 5rem 0 2rem; }
.fs-section h2 { font-size: clamp(2.35rem,4vw,4.2rem); line-height: 1.04; margin: 0 0 .8rem; }
.fs-section-intro { color: var(--fs-muted); font-size: 1.08rem; line-height: 1.65; max-width: 700px; margin-bottom: 2rem; }
.fs-scope { display: flex; gap: .65rem; flex-wrap: wrap; margin: .75rem 0 1.5rem; }
.fs-chip { border: 1px solid var(--fs-line); background: var(--fs-surface); border-radius: 999px; padding: .48rem .72rem; font-size: .83rem; font-weight: 690; }
.fs-safety { background: var(--fs-warm); border: 1px solid #ead7bd; border-radius: 16px; padding: 1rem 1.1rem; color: #5e4b34; line-height: 1.52; margin-bottom: 1.35rem; }
.fs-panel-label { color: var(--fs-muted); font-size: .79rem; font-weight: 780; letter-spacing: .08em; text-transform: uppercase; margin-bottom: .75rem; }
.fs-empty { min-height: 290px; display: grid; place-items: center; text-align: center; background: var(--fs-soft); border: 1px dashed #a8b9a6; border-radius: 18px; color: var(--fs-muted); padding: 2rem; }
.fs-empty strong { display: block; color: var(--fs-text); font-size: 1.2rem; margin-bottom: .45rem; }
.fs-source { color: var(--fs-muted); font-size: .86rem; margin: .7rem 0 1rem; overflow-wrap: anywhere; }

.fs-result-empty { min-height: 390px; display: flex; flex-direction: column; justify-content: space-between; background: #172019; color: #f5f7f3; border-radius: 22px; padding: clamp(1.4rem,4vw,2.5rem); }
.fs-result-empty h3 { font-size: 2.35rem; line-height: 1.08; margin: .8rem 0; }
.fs-result-empty p { color: #c5cdc6; line-height: 1.6; max-width: 440px; }
.fs-route { display: grid; grid-template-columns: repeat(5,1fr); gap: .35rem; margin-top: 2rem; }
.fs-route span { height: 5px; background: #5b665d; border-radius: 999px; }
.fs-route span:first-child { background: #a9c4a5; }
.fs-result { border-radius: 22px; padding: clamp(1.3rem,3vw,2.1rem); min-height: 390px; }
.fs-result.success { background: var(--fs-soft); border: 1px solid #cad9c6; }
.fs-result.caution { background: var(--fs-warm); border: 1px solid #ead7bd; }
.fs-result.danger { background: #f7e9e4; border: 1px solid #e5c9c0; }
.fs-result.neutral { background: #f0f1ee; border: 1px solid var(--fs-line); }
.fs-result-status { color: var(--fs-strong); font-weight: 780; font-size: .86rem; }
.fs-result h3 { font-size: clamp(2.5rem,4vw,4.5rem); line-height: .98; margin: 1.1rem 0; }
.fs-metrics { display: flex; gap: 2.2rem; padding: 1rem 0 1.2rem; border-block: 1px solid rgba(65,107,73,.22); }
.fs-metric span, .fs-advice-item span { display: block; color: var(--fs-muted); font-size: .76rem; margin-bottom: .3rem; }
.fs-result-copy { line-height: 1.62; margin: 1.15rem 0 0; white-space: pre-line; }
.fs-advice { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin-top: 1rem; }
.fs-advice-item { border-top: 1px solid var(--fs-line); padding: .9rem 0 0; }

[data-testid="stFileUploader"] { background: var(--fs-bg); border: 1px dashed #a8b9a6; border-radius: 16px; padding: .25rem; }
[data-testid="stFileUploaderDropzone"] { background: transparent; }
.stButton > button, .stDownloadButton > button { border-radius: 999px; min-height: 44px; border: 1px solid var(--fs-accent); font-weight: 740; }
.stButton > button[kind="primary"] { background: var(--fs-strong); border-color: var(--fs-strong); }
.stButton > button:focus-visible, a:focus-visible { outline: 3px solid #91ad8d !important; outline-offset: 3px; }
[data-testid="stExpander"] { background: var(--fs-surface); border: 1px solid var(--fs-line); border-radius: 14px; }

.fs-workflow { display: grid; grid-template-columns: 1.1fr 1fr; gap: 3rem; align-items: start; }
.fs-workflow-list { border-top: 1px solid var(--fs-line); }
.fs-workflow-item { display: grid; grid-template-columns: 76px 1fr; gap: 1rem; padding: 1.25rem 0; border-bottom: 1px solid var(--fs-line); }
.fs-workflow-item strong { color: var(--fs-accent); }
.fs-workflow-item h3 { margin: 0 0 .35rem; font-size: 1.08rem; }
.fs-workflow-item p { margin: 0; color: var(--fs-muted); line-height: 1.55; }
.fs-trust { background: #172019; color: #f3f5f1; border-radius: 28px; padding: clamp(2rem,5vw,4rem); }
.fs-trust h2 { color: #fff; }
.fs-trust p { color: #bdc7bf; }
.fs-trust-list { display: grid; grid-template-columns: repeat(2,1fr); gap: 0 2rem; border-top: 1px solid #3b473d; }
.fs-trust-item { padding: 1.15rem 0; border-bottom: 1px solid #3b473d; }
.fs-trust-item strong { display: block; margin-bottom: .3rem; }
.fs-trust-item span { color: #aeb9b0; line-height: 1.45; }
.fs-footer { margin-top: 6rem; padding: 2rem 0 1rem; border-top: 1px solid var(--fs-line); display: flex; justify-content: space-between; gap: 1.5rem; color: var(--fs-muted); font-size: .88rem; }
.fs-footer a { color: var(--fs-strong); }

@media (max-width: 800px) {
  .main .block-container { padding: 0 1rem 3rem; }
  .fs-nav { margin: 0 -1rem; padding: 0 1rem; }
  .fs-nav-links a:not(.fs-nav-cta) { display: none; }
  .fs-hero { padding-top: 3rem; }
  .fs-hero h1 { font-size: clamp(3.2rem,16vw,5.1rem); }
  .fs-hero-media img { min-height: 280px; }
  .fs-workflow, .fs-trust-list, .fs-advice { grid-template-columns: 1fr; }
  .fs-footer { flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
"""
