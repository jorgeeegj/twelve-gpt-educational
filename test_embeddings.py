import openai
import streamlit as st

# Get settings from streamlit secrets
GPT_EMBEDDINGS_ENGINE = st.secrets.get("GPT_EMBEDDINGS_ENGINE")
GPT3_BASE = st.secrets.get("GPT_BASE")
GPT3_VERSION = st.secrets.get("GPT_VERSION")
GPT_EMBEDDINGS_KEY = st.secrets.get("GPT_EMBEDDINGS_KEY")
USE_GEMINI = st.secrets.get("USE_GEMINI", False)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_EMBEDDING_MODEL = st.secrets.get("GEMINI_EMBEDDING_MODEL", "")

# Text to embed
text = "Hi, how are you doing today? I hope you're having a great day! This is a test of the embedding function. Let's see how it works."

# Clean the text
text = text.replace("\n", " ")

# Generate embedding
if USE_GEMINI:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    result = genai.embed_content(
        model=GEMINI_EMBEDDING_MODEL, content=text, task_type="retrieval_document"
    )
    embedding = result["embedding"]
else:
    openai.api_type = "azure"
    openai.api_base = GPT3_BASE
    openai.api_version = GPT3_VERSION
    openai.api_key = GPT_EMBEDDINGS_KEY
    result = openai.Embedding.create(input=[text], engine=GPT_EMBEDDINGS_ENGINE)
    embedding = result["data"][0]["embedding"]

# Print results
print(f"Text: {text}")
print(f"Embedding dimension: {len(embedding)}")
print(f"First 10 values: {embedding[:10]}")
