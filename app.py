"""Step 8: web page for the health insurance policy assistant.

Run:    streamlit run app.py
Needs:  pip install streamlit
Uses:   answer.py (search + Gemini), data/chroma (the index), .env (the API key)
"""
import os
import re

import streamlit as st

import answer as engine

st.set_page_config(page_title="Health Insurance Policy Assistant", layout="centered")

CHOICES = {
    "Compare both insurers": None,
    "Niva Bupa - ReAssure 3.0": "Niva Bupa",
    "Go Digit - Digit Supreme Care": "Go Digit",
    "IRDAI - regulator's rules": "IRDAI",
}

EXAMPLES = [
    ("Is cataract surgery covered in the first year?", "Compare both insurers"),
    ("Is there a room rent limit?", "Go Digit - Digit Supreme Care"),
    ("What is the moratorium period for health insurance claims?", "IRDAI - regulator's rules"),
    ("Does this policy cover my local hospital?", "Compare both insurers"),
]

DISCLAIMER = "This is information from the documents, not insurance or legal advice. Please confirm with your insurer."
REFUSAL = "i could not find this in the policy documents"


def load_api_key():
    """Key comes from the .env file locally, or from Streamlit secrets when deployed."""
    engine.load_env_file()
    if not os.environ.get("GEMINI_API_KEY"):
        try:
            os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
        except Exception:
            pass


def cited_numbers(text):
    """'... [1, 3] ... [2]' -> [1, 2, 3]"""
    numbers = set()
    for group in re.findall(r"\[([\d,\s]+)\]", text):
        numbers.update(int(n) for n in re.findall(r"\d+", group))
    return sorted(numbers)


def split_disclaimer(reply):
    """The model ends every answer with the disclaimer; show it once, as a caption."""
    body = reply.split("This is information from the documents")[0].strip()
    return body


@st.cache_data(show_spinner=False, ttl=3600)
def ask(question, insurer):
    hits = engine.retrieve(question, insurer)
    reply = engine.ask_llm(engine.build_prompt(question, hits)).strip()
    sources = [
        {"n": n, "insurer": meta["insurer"], "document": meta["document"],
         "pages": engine.page_label(meta), "text": doc}
        for n, (doc, meta) in enumerate(hits, start=1)
    ]
    return reply, sources


def use_example(question, choice):
    st.session_state["question"] = question
    st.session_state["source"] = choice
    st.session_state["auto_run"] = True

@st.cache_resource(show_spinner="Setting up the search index (first start only, about a minute)...")
def ensure_index():
    """On a fresh server there is no data/chroma folder yet, so build it from data/chunks.jsonl."""
    if not os.path.exists("data/chroma"):
        import build_index
        build_index.main()
    return True

# ---------- page ----------
load_api_key()
ensure_index()
st.session_state.setdefault("question", "")
st.session_state.setdefault("source", "Compare both insurers")

with st.sidebar:
    st.header("About")
    st.write(
        "Answers plain-language questions about health insurance policies, "
        "using only the policy documents, and shows the page each answer comes from."
    )
    st.subheader("Documents used")
    st.markdown(
        "- Niva Bupa ReAssure 3.0: policy wording and customer information sheet\n"
        "- Go Digit Digit Supreme Care: policy wording and customer information sheet\n"
        "- IRDAI Master Circular on Health Insurance Business (29 May 2024)"
    )
    st.subheader("Good to know")
    st.markdown(
        "- It cannot see your own Policy Schedule, so plan-specific numbers "
        "(room rent limit, some waiting periods) are not available.\n"
        "- It does not know premiums or other insurers.\n"
        "- Page numbers are the PDF page numbers.\n"
        "- If the documents do not answer a question, it says so instead of guessing."
    )
    st.caption("Tested on 30 questions: 26 answered correctly.")

st.title("Health Insurance Policy Assistant")
st.write("Ask a question about waiting periods, exclusions, or claim rules. "
         "Answers come from the policy documents, with the page shown.")

st.selectbox("Which documents should I search?", list(CHOICES.keys()), key="source")
st.text_input("Your question", key="question", placeholder="For example: Is cataract surgery covered in the first year?")

asked = st.button("Ask", type="primary")
auto = st.session_state.pop("auto_run", False)

st.caption("Try an example:")
cols = st.columns(2)
for i, (q, choice) in enumerate(EXAMPLES):
    cols[i % 2].button(q, key=f"ex{i}", on_click=use_example, args=(q, choice), use_container_width=True)

question = st.session_state["question"].strip()
if (asked or auto) and question:
    insurer = CHOICES[st.session_state["source"]]
    try:
        with st.spinner("Reading the policy documents..."):
            reply, sources = ask(question, insurer)
    except (Exception, SystemExit):
        st.error("The AI service is busy or not responding right now. Please try again in a minute.")
    else:
        body = split_disclaimer(reply)
        if body.lower().startswith(REFUSAL):
            st.warning(body)
            st.caption("Try rephrasing, or choose a different set of documents above.")
        else:
            st.markdown("### Answer")
            st.markdown(body.replace("$", "\\$"))
            cited = cited_numbers(body)
            shown = [s for s in sources if s["n"] in cited]
            if shown:
                st.markdown("### Where this comes from")
                for s in shown:
                    with st.expander(f"[{s['n']}] {s['insurer']} - {s['document']} - page {s['pages']}"):
                        st.markdown(s["text"].replace("$", "\\$"))
        st.caption(DISCLAIMER)
elif asked and not question:
    st.info("Please type a question first.")