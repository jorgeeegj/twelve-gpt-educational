import pandas as pd
from utils.embeddings_utils import get_embedding, cosine_similarity

from settings import (
    GPT_EMBEDDINGS_ENGINE,
    USE_GEMINI,
    GEMINI_EMBEDDING_MODEL,
    GEMINI_API_KEY,
)


class Embeddings:
    def __init__(self):
        self.df_dict = None

    def search(self, query, top_n=3):
        if USE_GEMINI:
            import google.generativeai as genai

            genai.configure(api_key=GEMINI_API_KEY)
            engine = GEMINI_EMBEDDING_MODEL
        else:
            engine = GPT_EMBEDDINGS_ENGINE

        embedding = get_embedding(query, engine=engine, use_gemini=USE_GEMINI)

        df = self.df_dict.copy()
        df["similarities"] = df.user_embedded.apply(
            lambda x: cosine_similarity(x, embedding)
        )
        df = df[df.similarities > 0.7]

        res = df.sort_values("similarities", ascending=False).head(top_n)
        return res

    def compare_strings(self, string1, string2):
        engine = GEMINI_EMBEDDING_MODEL if USE_GEMINI else GPT_EMBEDDINGS_ENGINE
        embedding1 = get_embedding(string1, engine=engine, use_gemini=USE_GEMINI)
        embedding2 = get_embedding(string2, engine=engine, use_gemini=USE_GEMINI)

        return cosine_similarity(embedding1, embedding2)

    def return_embedding(self, query):
        engine = GEMINI_EMBEDDING_MODEL if USE_GEMINI else GPT_EMBEDDINGS_ENGINE
        embedding = get_embedding(query, engine=engine, use_gemini=USE_GEMINI)
        return embedding


class PlayerEmbeddings(Embeddings):
    def __init__(self):
        self.df_dict = PlayerEmbeddings.get_embeddings()

    def get_embeddings():
        files = [
            "Interpretation",
            "Forward",
        ]

        df_embeddings = pd.DataFrame()
        for file in files:
            df_temp = pd.read_parquet(f"data/embeddings/{file}.parquet")
            if "category" not in df_temp:
                df_temp["category"] = None
            if "format" not in df_temp:
                df_temp["format"] = None
            df_temp = df_temp[
                ["user", "assistant", "category", "user_embedded", "format"]
            ]
            df_temp["user_embedded"] = df_temp.user_embedded.apply(eval).to_list()
            df_embeddings = pd.concat([df_embeddings, df_temp], ignore_index=True)

        return df_embeddings


class CountryEmbeddings(Embeddings):
    def __init__(self):
        self.df_dict = CountryEmbeddings.get_embeddings()

    def get_embeddings():
        files = [
            "WVS_qualities",
        ]

        df_embeddings = pd.DataFrame()
        for file in files:
            df_temp = pd.read_parquet(f"data/embeddings/{file}.parquet")
            if "category" not in df_temp:
                df_temp["category"] = None
            if "format" not in df_temp:
                df_temp["format"] = None
            df_temp = df_temp[
                ["user", "assistant", "category", "user_embedded", "format"]
            ]
            df_temp["user_embedded"] = df_temp.user_embedded.apply(eval).to_list()
            df_embeddings = pd.concat([df_embeddings, df_temp], ignore_index=True)

        return df_embeddings


class PersonEmbeddings(Embeddings):
    def __init__(self):
        self.df_dict = PersonEmbeddings.get_embeddings()

    def get_embeddings():
        files = [
            "Forward_bigfive",
        ]

        df_embeddings = pd.DataFrame()
        for file in files:
            df_temp = pd.read_parquet(f"data/embeddings/{file}.parquet")
            if "category" not in df_temp:
                df_temp["category"] = None
            if "format" not in df_temp:
                df_temp["format"] = None
            df_temp = df_temp[
                ["user", "assistant", "category", "user_embedded", "format"]
            ]
            df_temp["user_embedded"] = df_temp.user_embedded.apply(eval).to_list()
            df_embeddings = pd.concat([df_embeddings, df_temp], ignore_index=True)

        return df_embeddings