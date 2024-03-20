import streamlit as st
import extra_streamlit_components as stx
import requests
from requests import HTTPError


@st.cache_data(show_spinner=False)
def get_events(names):
    events = requests.get("http://0.0.0.0:4000/events", json=list(names))
    events.raise_for_status()
    return events.json()


st.set_page_config(layout="wide")

cookie_manager = stx.CookieManager()

if "session" in st.query_params:
    cookie_manager.set("session", st.query_params["session"])


if not cookie_manager.get("session"):
    spotify_auth_url = requests.get("http://0.0.0.0:4000/login").json()["login_url"]
    st.link_button(label="Authorise with Spotify", url=spotify_auth_url)
    st.stop()

user_info = requests.get("http://0.0.0.0:4000/user/info", headers={"session": cookie_manager.get("session")})
try:
    user_info.raise_for_status()
except HTTPError:
    spotify_auth_url = requests.get("http://0.0.0.0:4000/login").json()["login_url"]
    st.link_button(label="Authorise with Spotify", url=spotify_auth_url)
    st.stop()

st.title(f"Welcome, {user_info.json()['display_name']}")

with st.spinner("Fetching top artists from Spotify..."):
    top_artists = requests.get("http://0.0.0.0:4000/user/top_artists", headers={"session": cookie_manager.get("session")})
    try:
        top_artists.raise_for_status()
    except HTTPError:
        spotify_auth_url = requests.get("http://0.0.0.0:4000/login").json()["login_url"]
        st.link_button(label="Authorise with Spotify", url=spotify_auth_url)
        st.stop()

    st.write("Your top artists:")
    st.table(top_artists.json())

with st.spinner("Searching for events..."):
    events = get_events(set(top_artists.json()))
    st.write(f"{len(events)} event(s) found")
    st.table(events)
