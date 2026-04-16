# NOTE: Requires embeddings table in db/basic_stats.duckdb (run scripts/build_embeddings.py first).
# Requires Azure credentials in .streamlit/secrets.toml.
# Run manually: python -m pytest tests/test_fuzzy_resolve.py -v

import tomllib
from pathlib import Path

import pytest
from openai import AzureOpenAI

from src.basic_stats.duckdb_manager import DuckDBManager

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client_and_model():
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    with open(secrets_path, "rb") as f:
        secrets = tomllib.load(f)
    client = AzureOpenAI(
        api_key=secrets["GPT_KEY"],
        api_version=secrets["GPT_VERSION"],
        azure_endpoint="https://twelve-courses.openai.azure.com",
    )
    return client, secrets["GPT_EMBEDDINGS_MODEL"]


@pytest.fixture(scope="module")
def duck():
    return DuckDBManager()


def resolve(duck, client, model, name, entity_type):
    return duck.fuzzy_resolve_entity(name, entity_type, client=client, model=model)


# ---------------------------------------------------------------------------
# Player aliases — canonical names are the actual short_name values in the DB
# ---------------------------------------------------------------------------


class TestPlayerResolution:
    def test_salah_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Salah", "player") == "Mohamed Salah"

    def test_haaland_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Haaland", "player") == "E. Haaland"

    def test_de_bruyne_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "De Bruyne", "player") == "K. De Bruyne"

    def test_saka_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Saka", "player") == "B. Saka"

    def test_trent_firstname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Trent", "player") == "T. Alexander-Arnold"

    def test_vardy_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Vardy", "player") == "J. Vardy"

    def test_son_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Son", "player") == "Son Heung-Min"

    def test_martinelli_lastname(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Martinelli", "player") == "Gabriel Martinelli"

    def test_fullname_salah(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Mohamed Salah", "player") == "Mohamed Salah"

    def test_fullname_haaland(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Erling Haaland", "player") == "E. Haaland"

    def test_fullname_de_bruyne(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Kevin De Bruyne", "player") == "K. De Bruyne"

    def test_exact_short_name(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "E. Haaland", "player") == "E. Haaland"


# ---------------------------------------------------------------------------
# Team aliases
# ---------------------------------------------------------------------------


class TestTeamResolution:
    def test_man_city(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Man City", "team") == "Manchester City"

    def test_man_utd(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Man United", "team") == "Manchester United"

    def test_spurs(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Spurs", "team") == "Tottenham Hotspur"

    def test_wolves(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Wolves", "team") == "Wolverhampton Wanderers"

    def test_newcastle(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Newcastle", "team") == "Newcastle United"

    def test_villa(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Villa", "team") == "Aston Villa"

    def test_exact_name(self, duck, client_and_model):
        c, m = client_and_model
        assert resolve(duck, c, m, "Arsenal", "team") == "Arsenal"
