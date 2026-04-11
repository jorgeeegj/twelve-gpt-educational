# Library imports
import argparse
import os

import pandas as pd
import streamlit as st
import tiktoken

from classes.data_point import Player
from classes.data_source import PlayerStats
from utils.page_components import add_common_page_elements
from utils.utils import normalize_text

# def show():
sidebar_container = add_common_page_elements()
page_container = st.sidebar.container()
sidebar_container = st.sidebar.container()

st.divider()

st.write(
    "To make your own page create a page_name.py file and link to it in add_page_selector() in utils/page_components.py"
)
