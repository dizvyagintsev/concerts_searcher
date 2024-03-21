import streamlit as st
import extra_streamlit_components as stx
import requests
from requests import HTTPError
from streamlit_searchbox import st_searchbox


@st.cache_data(show_spinner=False)
def get_events(names):
    resp = requests.get("http://0.0.0.0:4000/events", json=list(names))
    resp.raise_for_status()
    return resp.json()


def search_for_artist(q):
    resp = requests.get(f"http://0.0.0.0:4000/artists?q={q}")
    resp.raise_for_status()
    return resp.json()


st.set_page_config(layout="wide")

cookie_manager = stx.CookieManager()


if "spotify_auth" in st.query_params or "session" in st.query_params:
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

        st.session_state.artists = top_artists.json()
else:
    if "artists" not in st.session_state:
        st.session_state.artists = []

new_artist = st_searchbox(search_function=search_for_artist, placeholder="Search for artist on Spotify...")
if new_artist and new_artist not in st.session_state.artists:
    st.session_state.artists.insert(0, new_artist)

if st.session_state.artists:
    st.write("Your top artists:")
    st.table(st.session_state.artists)

    with st.spinner("Searching for events..."):
        events = get_events(set(st.session_state.artists))
        st.write(f"{len(events)} event(s) found")

        events.sort(key=lambda x: (
            st.session_state.artists.index(x["artist"]),
            x["distance_km"],
            x["date"],
        ))

        st.table(events)
else:
    st.write("Add some artists")
