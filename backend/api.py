import asyncio
import os
from typing import Annotated, List

import spotipy
from fastapi.security import OAuth2AuthorizationCodeBearer
import httpx
from pydantic import BaseModel
from fastapi import HTTPException, FastAPI, Header
from uuid import UUID, uuid4

from fastapi_sessions.backends.implementations import InMemoryBackend
from spotipy import SpotifyClientCredentials
from starlette.responses import RedirectResponse, Response
from starlette.status import HTTP_401_UNAUTHORIZED

from events import get_events_by_name
from entities import Event


class SessionData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


backend = InMemoryBackend[UUID, SessionData]()


app = FastAPI()

# Your Spotify application credentials
CLIENT_ID = os.environ["SPOTIPY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIPY_CLIENT_SECRET"]
REDIRECT_URI = os.environ["SPOTIPY_REDIRECT_URI"]
FRONTEND_URI = os.environ["FRONTEND_URI"]
SCOPE = "user-top-read"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&scope={SCOPE}&redirect_uri={REDIRECT_URI}",
    tokenUrl=TOKEN_URL,
)


@app.get("/events")
async def find_events(names: List[str]) -> List[Event]:
    events = []

    results = await asyncio.gather(*[get_events_by_name(name) for name in names])
    for result in results:
        events.extend(result)

    return events


@app.get("/artists")
async def find_artist(q: str) -> List[str]:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

    return [item["name"] for item in sp.search(q=f"artist:{q}", type="artist")["artists"]["items"]]


@app.get("/user/top_artists")
async def top_artists(session: Annotated[str, Header()]):
    session_data = await backend.read(UUID(session))
    if session_data is None:
        print("session data not found")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="no token")

    token = session_data.access_token

    sp = spotipy.Spotify(auth=token)

    top_artists = []
    offset = 0

    while True:
        response = sp.current_user_top_artists(time_range="long_term", limit=50, offset=offset)
        top_artists.extend([artist["name"] for artist in response["items"]])
        if response["next"] is None:
            break

        offset += 50

    return top_artists


@app.get("/login")
async def login():
    return {"login_url": f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&scope={SCOPE}&redirect_uri={REDIRECT_URI}"}


@app.get("/user/info")
async def user_info(session: Annotated[str, Header()]):
    session_data = await backend.read(UUID(session))
    if session_data is None:
        print("session data not found")
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="no token")

    token = session_data.access_token

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("https://api.spotify.com/v1/me", headers=headers)
        if response.status_code != 200:
            print(response.text)
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=response.text)
        return response.json()


@app.get("/callback")
async def callback(code: str, resp: Response):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        response = response.json()
        session_data = SessionData(
            access_token=response["access_token"],
            refresh_token=response["refresh_token"],
            expires_in=response["expires_in"],
        )

        session = uuid4()
        await backend.create(session, session_data)

        return RedirectResponse(
            url=f"{FRONTEND_URI}/?session={session}",
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4000)


