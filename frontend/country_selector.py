import dataclasses
import os
from typing import Optional, List, Set

import streamlit as st
from opencage.geocoder import OpenCageGeocode
from streamlit_js_eval import get_geolocation

geocoder = OpenCageGeocode(os.environ["OPENCAGE_API_KEY"])

if "_geolocations" in st.session_state:
    st.session_state.geolocations = st.session_state._geolocations


def get_flag_emoji(country_code):
    offset = 127397
    flag_emoji = ''.join(chr(ord(c) + offset) for c in country_code)
    return flag_emoji


@dataclasses.dataclass(eq=True, order=True)
class Geolocation:
    country: str
    country_code: str
    city: Optional[str] = None
    radius_km: Optional[int] = None

    def __hash__(self):
        return hash((self.country.upper(), self.country_code.upper(), self.city.upper() if self.city else None))

    def __post_init__(self):
        self.country_code = self.country_code.upper()


    def format(self):
        if self.city and self.radius_km:
            return self.format_as_region(self.radius_km)

        if self.city:
            return self.format_as_city()

        return self.format_as_country()

    def format_as_city(self):
        if not self.city:
            raise ValueError("City is not set")

        return f"{self.city}, {self.country}"

    def format_as_country(self):
        return f"{get_flag_emoji(self.country_code)} {self.country}"

    def format_as_region(self, radius_km: int):
        if self.city is None:
            raise ValueError("City is not set")

        return f"{self.city} +{radius_km} km"


def unwrap_geolocations(
    selected_geolocations: List[Geolocation],
    available_geolocations: List[Geolocation],
) -> Set[Geolocation]:
    geolocations = []

    for s_geo in selected_geolocations:
        if s_geo.city is None:
            geolocations.extend([
                a_geo for a_geo in available_geolocations
                if a_geo.country == s_geo.country
            ])
        else:
            geolocations.append(s_geo)

    # st.write(set(geolocations))

    return set(geolocations)


@st.cache_data
def reverse_geocode(lat, lon) -> Geolocation:
    location = geocoder.reverse_geocode(lat, lon)[0]
    return Geolocation(
        country=location['components']['country'],
        country_code=location['components']['country_code'],
        city=location['components']['city'],
    )


def get_location() -> Optional[Geolocation]:
    location = get_geolocation()

    if location and location.get("coords", {}).get("latitude"):
        with st.spinner("Getting location"):
            return reverse_geocode(location["coords"]["latitude"], location["coords"]["longitude"])


if "_geolocations" in st.session_state:
    st.session_state.geolocations = st.session_state._geolocations
    st.write(st.session_state.geolocations)


def country_selector(available_geolocations, col):
    cities = sorted(set([
        Geolocation(country=geo.country, country_code=geo.country_code, city=geo.city)
        for geo in available_geolocations
    ]), key=lambda x: x.city)
    countries = [
        Geolocation(country=geo.country, country_code=geo.country_code, city=None)
        for geo in available_geolocations
    ]
    countries = sorted(list(set(countries)), key=lambda x: x.country)
    options = cities + countries

    user_location = get_location() or [None]
    if user_location:
        user_location = [user_location]

    col.multiselect(
        label="Select cities and countries",
        options=options,
        format_func=lambda x: x.format(),
        placeholder="Select cities and countries",
        key="geolocations",
        default=user_location if user_location[0] in options else None,
    )

    return unwrap_geolocations(st.session_state.geolocations, available_geolocations)


# st.write(country_selector(available_geolocations))
