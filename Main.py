
import streamlit as st
from pathlib import Path
from uuid import uuid4

from complete_graph_build import process_uploaded_file
from Backend.graph_retrieval import get_subjects, retrieve_subject
from answer_generation import generate_study_plan

# PAGE CONFIG
st.set_page_config(
    page_title="Study AI | GraphRAG",
    page_icon="📚",
    layout="wide"
)

UPLOAD_DIR = Path("storage/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# SESSION STATE
if "document_id" not in st.session_state:
    st.session_state.document_id = None

if "subjects" not in st.session_state:
    st.session_state.subjects = []

if "filename" not in st.session_state:
    st.session_state.filename = None

if "study_result" not in st.session_state:
    st.session_state.study_result = None


# CUSTOM CSS
st.markdown("""
<style>
.stApp {
    background: #09090D;
    color: #FFFFFF;
}

.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, p, label {
    color: #FFFFFF !important;
}

.hero {
    background: linear-gradient(120deg, #171126, #25133D);
    border: 1px solid #51317D;
    border-radius: 16px;
    padding: 35px;
    margin-bottom: 30px;
}

.hero-title {
    font-size: 42px;
    font-weight: 800;
    color: #FFFFFF;
}

.hero-subtitle {
    color: #C2B4D9;
    font-size: 16px;
}

.panel {
    background: #15131C;
    border: 1px solid #30283D;
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 20px;
}

.stButton > button {
    background: #793FE0;
    color: white;
    border: none;
    border-radius: 8px;
    min-height: 43px;
    font-weight: 600;
}

.stButton > button:hover {
    background: #925DF0;
    color: white;
}

div[data-baseweb="select"] > div {
    background: #191620;
    border-color: #49365F;
    color: white;
}

.stFileUploader section {
    background: #171321;
    border: 1px dashed #8953D5;
    border-radius: 12px;
}

hr {
    border-color: #30283D;
}

footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)


# HEADER
st.markdown("""
<div class="hero">
    <div class="hero-title">STUDY AI</div>
    <div class="hero-subtitle">
        GRAPHRAG BASED STUDY ASSISTANT SYSTEM
    </div>
    <br>
    Upload your syllabus and generate an intelligent
    study plan based on its knowledge graph.
</div>
""", unsafe_allow_html=True)


# STEP 1: DOCUMENT UPLOAD
st.markdown("## 01. Upload Your Syllabus")

st.markdown('<div class="panel">', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Choose your syllabus",
    type=["pdf", "png", "jpg", "jpeg"],
    max_upload_size=20,
    key="syllabus_upload"
)

if uploaded_file:
    st.write("Selected file:", uploaded_file.name)

    if st.button("Upload and Process Syllabus", use_container_width=True):

        extension = Path(uploaded_file.name).suffix.lower()

        signatures = {
            ".pdf": b"%PDF-",
            ".png": b"\x89PNG\r\n\x1a\n",
            ".jpg": b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff"
        }

        content = uploaded_file.getvalue()

        if not content.startswith(signatures[extension]):
            st.error("Invalid file content.")

        else:
            stored_name = f"{uuid4()}{extension}"
            file_path = UPLOAD_DIR / stored_name

            try:
                with st.spinner(
                    "Processing document and constructing knowledge graph..."
                ):
                    file_path.write_bytes(content)

                    result = process_uploaded_file(file_path)

                    st.session_state.document_id = result["document_id"]
                    st.session_state.filename = uploaded_file.name
                    st.session_state.subjects = get_subjects(
                        result["document_id"]
                    )
                    st.session_state.study_result = None

                if st.session_state.subjects:
                    st.success("Syllabus processed successfully!")
                    st.info(
                        f"Extracted {len(st.session_state.subjects)} subjects | "
                        f"{result['chunks']} chunks | "
                        f"{result['concepts']} concepts"
                    )
                else:
                    st.warning("No subjects were found in this syllabus.")

            except Exception as e:
                st.error(f"Processing failed: {e}")

            finally:
                if file_path.exists():
                    file_path.unlink()

st.markdown('</div>', unsafe_allow_html=True)


# STEP 2: SUBJECT SELECTION
if st.session_state.document_id and st.session_state.subjects:

    st.markdown("## 02. Select Your Subject")

    st.markdown('<div class="panel">', unsafe_allow_html=True)

    st.caption(f"Uploaded document: {st.session_state.filename}")

    selected_subject = st.selectbox(
        "Choose a subject from your syllabus",
        st.session_state.subjects
    )

    if st.button("Generate Study Plan", use_container_width=True):

        try:
            with st.spinner("Retrieving graph data and generating study plan..."):

                data = retrieve_subject(
                    selected_subject,
                    st.session_state.document_id
                )

                if not data:
                    st.error("No graph data found for this subject.")
                else:
                    result = generate_study_plan(data)

                    st.session_state.study_result = result
                    st.session_state.result_subject = selected_subject

        except Exception as e:
            st.error(f"Generation failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)


# STEP 3: DISPLAY RESULTS
if st.session_state.study_result:

    st.markdown("---")
    st.markdown("## 03. Your Study Plan")

    st.markdown(f"### {st.session_state.result_subject}")

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown(st.session_state.study_result)
    st.markdown('</div>', unsafe_allow_html=True)


# FOOTER
st.markdown("---")
st.markdown(
    "<center style='color:#8F849F;'>"
    "STUDY AI | GraphRAG Study Intelligence"
    "</center>",
    unsafe_allow_html=True
)
