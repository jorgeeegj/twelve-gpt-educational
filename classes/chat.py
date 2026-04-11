import json
from itertools import groupby

import streamlit as st

from settings import USE_GEMINI

if USE_GEMINI:
    from settings import GEMINI_API_KEY, GEMINI_CHAT_MODEL, USE_GEMINI
else:
    from openai import OpenAI

    from settings import GPT_BASE, GPT_ENGINE, GPT_KEY, GPT_VERSION

import utils.sentences as sentences
from classes.description import (
    CountryDescription,
    PersonDescription,
    PlayerDescription,
)
from classes.embeddings import CountryEmbeddings, PersonEmbeddings, PlayerEmbeddings
from classes.visual import DistributionPlot, DistributionPlotPersonality, Visual
from utils.gemini import convert_messages_format


class Chat:
    function_names = []

    def __init__(self, chat_state_hash, state="empty"):
        if (
            "chat_state_hash" not in st.session_state
            or chat_state_hash != st.session_state.chat_state_hash
        ):
            st.session_state.chat_state_hash = chat_state_hash
            st.session_state.messages_to_display = []
            st.session_state.chat_state = state

        if isinstance(self, PlayerChat):
            self.name = self.player.name
        elif isinstance(self, PersonChat):
            self.name = self.person.name

        self.messages_to_display = st.session_state.messages_to_display
        self.state = st.session_state.chat_state

        if not USE_GEMINI:
            self.client = OpenAI(
                api_key=GPT_KEY,
                base_url=GPT_BASE,
            )

    def instruction_messages(self):
        return []

    def add_message(self, content, role="assistant", user_only=True, visible=True):
        message = {"role": role, "content": content}
        self.messages_to_display.append(message)

    def handle_input(self, input):
        messages = self.instruction_messages()
        messages = messages + self.messages_to_display.copy()

        get_relevant_info = self.get_relevant_info(input)

        self.messages_to_display.append({"role": "user", "content": input})

        messages.append(
            {
                "role": "user",
                "content": f"Here is the relevant information to answer the users query: {get_relevant_info}\n\n```User: {input}```",
            }
        )

        messages = [message for message in messages if isinstance(message["content"], str)]

        st.expander("Chat transcript", expanded=False).write(messages)

        if USE_GEMINI:
            import google.generativeai as genai

            converted_msgs = convert_messages_format(messages)

            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(
                model_name=GEMINI_CHAT_MODEL,
                system_instruction=converted_msgs["system_instruction"],
            )
            chat = model.start_chat(history=converted_msgs["history"])
            response = chat.send_message(content=converted_msgs["content"])

            answer = response.text
        else:
            response = self.client.chat.completions.create(
                model=GPT_ENGINE,
                messages=messages,
            )
            answer = response.choices[0].message.content

        message = {"role": "assistant", "content": answer}
        self.messages_to_display.append(message)

    def display_content(self, content):
        if isinstance(content, str):
            st.write(content)
        elif isinstance(content, Visual):
            content.show()
        else:
            try:
                content.show()
            except Exception:
                try:
                    st.write(content.get_string())
                except Exception:
                    raise ValueError(f"Message content of type {type(content)} not supported.")

    def display_messages(self):
        for key, group in groupby(self.messages_to_display, lambda x: x["role"]):
            group = list(group)

            if key == "assistant":
                avatar = "data/ressources/img/twelve_chat_logo.svg"
            else:
                try:
                    avatar = st.session_state.user_info["picture"]
                except Exception:
                    avatar = None

            message = st.chat_message(name=key, avatar=avatar)
            with message:
                for message in group:
                    content = message["content"]
                    self.display_content(content)

    def save_state(self):
        st.session_state.messages_to_display = self.messages_to_display
        st.session_state.chat_state = self.state


class PlayerChat(Chat):
    def __init__(self, chat_state_hash, player, players, state="empty"):
        self.embeddings = PlayerEmbeddings()
        self.player = player
        self.players = players
        super().__init__(chat_state_hash, state=state)

    def get_input(self):
        if x := st.chat_input(
            placeholder=f"What else would you like to know about {self.player.name}?"
        ):
            if len(x) > 500:
                st.error(
                    f"Your message is too long ({len(x)} characters). Please keep it under 500 characters."
                )
            self.handle_input(x)

    def instruction_messages(self):
        first_messages = [
            {"role": "system", "content": "You are a UK-based football scout."},
            {
                "role": "user",
                "content": (
                    "After these messages you will be interacting with a user of a football scouting platform. "
                    f"The user has selected the player {self.player.name}, and the conversation will be about them. "
                    "You will receive relevant information to answer a user's questions and then be asked to provide a response. "
                    "All user messages will be prefixed with 'User:' and enclosed with ```. "
                    "When responding to the user, speak directly to them. "
                    "Use the information provided before the query to provide 2 sentence answers."
                    " Do not deviate from this information or provide additional information that is not in the text returned by the functions."
                ),
            },
        ]
        return first_messages

    def get_relevant_info(self, query):
        if query == "":
            query = self.messages_to_display[-1]["content"]

        ret_val = "Here is a description of the player in terms of data: \n\n"
        description = PlayerDescription(self.player)
        ret_val += description.synthesize_text()

        results = self.embeddings.search(query, top_n=5)
        ret_val += (
            "\n\nHere is a description of some relevant information for answering the question:  \n"
        )
        ret_val += "\n".join(results["assistant"].to_list())

        ret_val += "\n\nIf none of this information is relevent to the users's query then use the information below to remind the user about the chat functionality: \n"
        ret_val += "This chat can answer questions about a player's statistics and what they mean for how they play football."
        ret_val += (
            "The user can select the player they are interested in using the menu to the left."
        )

        return ret_val


class WVSChat(Chat):
    def __init__(
        self,
        chat_state_hash,
        country,
        countries,
        description_dict,
        thresholds_dict,
        state="empty",
    ):
        self.embeddings = CountryEmbeddings()
        self.country = country
        self.countries = countries
        self.description_dict = description_dict
        self.thresholds_dict = thresholds_dict
        super().__init__(chat_state_hash, state=state)

    def get_input(self):
        if x := st.chat_input(
            placeholder=f"What else would you like to know about {self.country.name}?"
        ):
            if len(x) > 500:
                st.error(
                    f"Your message is too long ({len(x)} characters). Please keep it under 500 characters."
                )
            self.handle_input(x)

    def instruction_messages(self):
        first_messages = [
            {"role": "system", "content": "You are a researcher."},
            {
                "role": "user",
                "content": (
                    "After these messages you will be interacting with a user of a data analysis platform. "
                    f"The user has selected the country {self.country.name}, and the conversation will be about different core value measured in the World Value Survey study. "
                    "All user messages will be prefixed with 'User:' and enclosed with ```. "
                    "When responding to the user, speak directly to them. "
                    "Use the information provided before the query to provide 2 sentence answers."
                    " Do not deviate from this information or provide additional information that is not in the text returned by the functions."
                ),
            },
        ]
        return first_messages

    def get_relevant_info(self, query):
        if query == "":
            query = self.messages_to_display[-1]["content"]

        ret_val = "Here is a description of the country in terms of data: \n\n"
        description = CountryDescription(self.country, self.description_dict, self.thresholds_dict)
        ret_val += description.synthesize_text()

        results = self.embeddings.search(query, top_n=5)
        ret_val += (
            "\n\nHere is a description of some relevant information for answering the question:  \n"
        )
        ret_val += "\n".join(results["assistant"].to_list())

        ret_val += "\n\nIf none of this information is relevant to the users's query then use the information below to remind the user about the chat functionality: \n"
        ret_val += "This chat can answer questions about a country's core values."
        ret_val += (
            "The user can select the country they are interested in using the menu to the left."
        )

        return ret_val


class PersonChat(Chat):
    def __init__(self, chat_state_hash, person, persons, state="empty"):
        self.embeddings = PersonEmbeddings()
        self.person = person
        self.persons = persons
        super().__init__(chat_state_hash, state=state)

    def instruction_messages(self):
        first_messages = [
            {"role": "system", "content": "You are a recruiter."},
            {
                "role": "user",
                "content": (
                    "After these messages you will be interacting with a user of personality test platform. "
                    f"The user has selected the person {self.person.name}, and the conversation will be about them. "
                    "You will receive relevant information to answer a user's questions and then be asked to provide a response. "
                    "All user messages will be prefixed with 'User:' and enclosed with ```. "
                    "When responding to the user, speak directly to them. "
                    "Use the information provided before the query to provide 2 sentence answers."
                    " Do not deviate from this information or provide additional information that is not in the text returned by the functions."
                ),
            },
        ]
        return first_messages

    def get_relevant_info(self, query):
        if query == "":
            query = self.messages_to_display[-1]["content"]

        ret_val = "Here is a description of the person in terms of data: \n\n"
        description = PersonDescription(self.person)
        ret_val += description.synthesize_text()

        results = self.embeddings.search(query, top_n=5)
        ret_val += (
            "\n\nHere is a description of some relevant information for answering the question:  \n"
        )
        ret_val += "\n".join(results["assistant"].to_list())

        ret_val += "\n\nIf none of this information is relevent to the users's query then use the information below to remind the user about the chat functionality: \n"
        ret_val += "This chat can answer questions about person's statistics and what they mean about their personality."
        ret_val += (
            "The user can select the persons they are interested in using the menu to the left."
        )

        return ret_val

    def get_input(self):
        if x := st.chat_input(
            placeholder=f"What else would you like to know about {self.person.name}?"
        ):
            if len(x) > 500:
                st.error(
                    f"Your message is too long ({len(x)} characters). Please keep it under 500 characters."
                )
            self.handle_input(x)
