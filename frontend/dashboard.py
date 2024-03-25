import os
from datetime import datetime

import pandas as pd
import streamlit as st

MAX_TOP_ARTISTS = 50
BACKEND_URI = os.environ["BACKEND_URI"]

st.set_page_config(layout="wide")
st.markdown(
        """
        <style>
            .stMultiSelect [data-baseweb="tag"] {
                height: fit-content;
            }
            .stMultiSelect [data-baseweb="tag"] span[title] {
                white-space: normal; max-width: 100%; overflow-wrap: anywhere;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

import extra_streamlit_components as stx
import requests
from requests import HTTPError
from streamlit_searchbox import st_searchbox

from country_selector import country_selector, Geolocation


@st.cache_data(show_spinner=False)
def get_events(names):
    resp = requests.get(f"{BACKEND_URI}/events", json=list(names))
    resp.raise_for_status()
    return resp.json()


def search_for_artist(q):
    resp = requests.get(f"{BACKEND_URI}/artists?q={q}")
    resp.raise_for_status()
    return resp.json()


cookie_manager = stx.CookieManager()


if "spotify_auth" in st.query_params or "session" in st.query_params:
    if "session" in st.query_params:
        cookie_manager.set("session", st.query_params["session"])

    if not cookie_manager.get("session"):
        spotify_auth_url = requests.get(f"{BACKEND_URI}/login").json()["login_url"]
        st.link_button(label="Authorise with Spotify", url=spotify_auth_url)
        st.stop()

    user_info = requests.get(f"{BACKEND_URI}/user/info", headers={"session": cookie_manager.get("session")})
    try:
        user_info.raise_for_status()
    except HTTPError:
        spotify_auth_url = requests.get(f"{BACKEND_URI}/login").json()["login_url"]
        st.link_button(label="Authorise with Spotify", url=spotify_auth_url)
        st.stop()

    st.title(f"Welcome, {user_info.json()['display_name']}")

    with st.spinner("Fetching top artists from Spotify..."):
        top_artists = requests.get(f"{BACKEND_URI}/user/top_artists", headers={"session": cookie_manager.get("session")})
        try:
            top_artists.raise_for_status()
        except HTTPError:
            spotify_auth_url = requests.get(f"{BACKEND_URI}/login").json()["login_url"]
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
    st.session_state.artists = st.session_state.artists[:MAX_TOP_ARTISTS]

    with st.expander("Your top artists"):
        st.table(st.session_state.artists)

    with st.spinner("Searching for events..."):
        events = get_events(set(st.session_state.artists))
        st.write(f"{len(events)} event(s) found")

        events.sort(key=lambda x: (
            st.session_state.artists.index(x["artist"]),
            # x["distance_km"],
            x["date"],
        ))

        col1, col2, col3 = st.columns([4.5, 1, 1])

        selected_geo = country_selector(
            list({
                Geolocation(country=event["country"], country_code=event["country_code"], city=event["city"]) for event in events
            }), col1
        )
        geo_filtered_events = list(filter(
            lambda x: Geolocation(country=x["country"], country_code=x["country_code"], city=x["city"]) in selected_geo,
            events
        ))

        if geo_filtered_events:
            min_date = datetime.strptime(min(geo_filtered_events, key=lambda x: x["date"])["date"], "%Y-%m-%d").date()
            max_date = datetime.strptime(max(geo_filtered_events, key=lambda x: x["date"])["date"], "%Y-%m-%d").date()
            selected_min_date, selected_max_date = col2.date_input(
                "Select date", value=(min_date, max_date), min_value=min_date, max_value=max_date,
            )
            date_filtered_events = filter(
                lambda x: selected_min_date <= datetime.strptime(x["date"], "%Y-%m-%d").date() <= selected_max_date,
                geo_filtered_events
            )

            sort_by = col3.selectbox(
                "Sort by",
                ["Mostly played", "Date"],
            )

            if sort_by == "Mostly played":
                date_filtered_events = sorted(
                    date_filtered_events,
                    key=lambda x: (st.session_state.artists.index(x["artist"]), x["date"]),
                )
            elif sort_by == "Date":
                date_filtered_events = sorted(
                    date_filtered_events,
                    key=lambda x: (x["date"], st.session_state.artists.index(x["artist"])),
                )
            else:
                raise ValueError(f"Unknown sort_by value: {sort_by}")

            df = pd.DataFrame(date_filtered_events)
            df["location"] = df["city"] + ", " + df["country"]

            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
                column_order=["name", "artist", "location", "date", "url"],
                column_config={
                    "name": st.column_config.TextColumn("Event name"),
                    "artist": st.column_config.TextColumn("Artist"),
                    "location": st.column_config.TextColumn("Location"),
                    "date": st.column_config.DateColumn("Date"),
                    "url": st.column_config.LinkColumn("URL", display_text="Link"),
                },
            )
        else:
            st.write("No events match the filters")
else:
    st.write("Add some artists")
