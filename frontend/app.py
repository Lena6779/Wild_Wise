"""Wild Wise chat app: log in, then ask questions about wild animals."""

import os

import requests
import streamlit as st

# The backend: localhost when run directly, http://backend:8000 in Docker
API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Wild Wise Education Chatbot", page_icon="🦉")
st.title("🦉 Wild Wise")
st.caption("Curious about wild animals? Ask me what they eat, where they live, how they're born, or if they hibernate!")

# Remember the login and chat between reruns
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.messages = []


def auth_headers():
    """The login header for protected API requests."""
    return {"Authorization": f"Bearer {st.session_state.token}"}


def log_in(username, password):
    """Log in, remember the token, reload the page."""
    try:
        response = requests.post(
            f"{API_URL}/auth/token",
            # Login is a form, not JSON
            data={"username": username, "password": password},
            timeout=10,
        )
    except requests.ConnectionError:
        st.error("Can't reach the Wild Wise server. Is the backend running?")
        return
    if response.status_code == 200:
        st.session_state.token = response.json()["access_token"]
        st.session_state.username = username
        st.rerun()
    else:
        st.error("Wrong username and/or password.")


def show_login():
    """Show the Log in and Register tabs."""
    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        # A form only reurns the page when its button is clicked
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                log_in(username, password)

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input("Create a username")
            new_password = st.text_input("Create a password", type="password")
            if st.form_submit_button("Create an account"):
                response = requests.post(
                    f"{API_URL}/auth/register",
                    json={"username": new_username, "password": new_password},
                    timeout=10,
                )
                if response.status_code == 201:
                    log_in(new_username, new_password)
                # 400 code = name take; anything else = too short OR too long (442 code)
                elif response.status_code == 400:
                    st.error("That username is already taken.")
                else:
                    st.error(
                        "Usernames need 3 to 50 characters, and passwords 8 to 72."
                    )


def ask_wild_wise(question):
    """Send a question to API and return its reply."""
    try:
        response = requests.post(
            f"{API_URL}/ask",
            json={
                "question": question,
                "animal_class": st.session_state.get("animal_class")
            },
            headers=auth_headers(),
            timeout=120,
        )
    except requests.RequestException:
        # Erros use the same shape a real reply, so the chat can show them
        return {
            "answer": "Can't reach the Wild Wise server.",
            "confidence": "none",
            "sources": [],
        }

    # The login expired, so go back to login screen
    if response.status_code == 401:
        st.session_state.token = None
        st.rerun()

    if response.status_code != 200:
        return {
            "answer": "Wild Wise can't answer right now, please try again.",
            "confidence": "none",
            "sources": [],
        }
    return response.json()


def show_chat():
    """Show the chat so far and the box for asking a new question."""
    # Streamlit reruns the entire script, so redraw every saved message
    for message in st.session_state.messages:
        avatar = "🦉" if message["role"] == "assistant" else None
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                st.caption(f"Confidence: {message['confidence']}")
                if message["sources"]:
                    with st.expander("Sources"):
                        # One line per animal, even if several chunks come from it
                        unique = {s["animal"]: s["source_url"] for s in message["sources"]}
                        for animal, url in unique.items():
                            st.markdown(f"- **{animal}**: {url}")
                          

    question = st.chat_input("Ask Wild Wise about a wild animal...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.spinner("Wild Wise is thinking..."):
            reply = ask_wild_wise(question)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply["answer"],
                "confidence": reply["confidence"],
                "sources": reply["sources"],
            }
        )
        st.rerun()


def show_sidebar():
    """Show who is logged in, the animal filter, stats, and log out."""
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.username}**")
        if st.button("Log out"):
            # Logging out just forgets the token and clears the chat
            st.session_state.token = None
            st.session_state.username = None
            st.session_state.messages = []
            st.rerun()

        st.divider()
        choice = st.selectbox(
            "Animal Class",
            [
                "All animals",
                "mammal",
                "bird",
                "reptile",
                "amphibian",
                "fish",
                "insect",
                "arachnid",
                "worm",
            ],
        )
        # The API expects None for "no filter"
        st.session_state.animal_class = None if choice == "All animals" else choice

        st.divider()
        try:
            stats = requests.get(f"{API_URL}/stats", timeout=10).json()
            st.metric("Animals", stats["animal_count"])
            with st.expander("See all wild animals"):
                for name in stats["animals"]:
                    st.write(name)
        except requests.RequestException:
            st.warning("Cannot load stats right now.")


# Show the login screen until the user logs in
if st.session_state.token is None:
    show_login()
    st.stop()

show_sidebar()
show_chat()
