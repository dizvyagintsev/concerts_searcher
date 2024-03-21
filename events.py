import math
import os
from dataclasses import dataclass
import datetime
from typing import List

import dotenv
from asyncio_redis_rate_limit import rate_limit, RateSpec, RateLimitError
from redis.asyncio import Redis as AsyncRedis
import backoff
import asyncio

import httpx

dotenv.load_dotenv(".env")

MAX_PER_PAGE = 200

MAX_PER_SEARCH = 1000

MAX_CONCURRENT_CALLS = 5

LIMIT_EXCEEDED_ERROR_CODES = ("DIS1035", "DIS1024")

SEARCH_RADIUS = 700

TICKETMASTER_API_KEY = os.environ["TICKETMASTER_API_KEY"]
AMSTERDAM_LATLONG = '52.3676,4.9041'

redis = AsyncRedis.from_url('redis://localhost:6379')


@dataclass
class Event:
    name: str
    artist: str
    url: str
    city: str
    country: str
    date: datetime.date
    distance_km: float
    id: str


async def get_events_by_name(name: str) -> List[Event]:
    json_ = await get_page(0, name)

    events = []
    jsons = [json_]

    total_pages = min(int(json_["page"]["totalPages"]), math.ceil(MAX_PER_SEARCH / MAX_PER_PAGE))
    if total_pages == 0:
        return []

    jsons.extend(await asyncio.gather(*[get_page(page, name) for page in range(1, total_pages)]))

    for json_ in jsons:
        if "errors" in json_:
            if json_["errors"][0]["code"] in LIMIT_EXCEEDED_ERROR_CODES:
                print(f"limit exceeded for {name} ({json_})")
                continue
            else:
                print(json_)
                raise Exception

        for event in json_["_embedded"]["events"]:
            try:
                events.append(Event(
                    artist=name,
                    id=event["id"],
                    name=event["name"],
                    url=event["url"],
                    city=event["_embedded"]["venues"][0]["city"]["name"],
                    country=event["_embedded"]["venues"][0]["country"]["name"],
                    distance_km=event["distance"],
                    date=datetime.datetime.strptime(event["dates"]["start"]["localDate"], "%Y-%m-%d").date()
                ))
            except KeyError as e:
                print(e)
                print(event)

    print(f"{len(events)} events found")
    return events


@backoff.on_exception(backoff.constant, RateLimitError, interval=1)
@rate_limit(rate_spec=RateSpec(requests=5, seconds=1), backend=redis)
async def get_page(page: int, name: str):
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        'apikey': TICKETMASTER_API_KEY,
        'size': MAX_PER_PAGE,
        'latlong': AMSTERDAM_LATLONG,
        'radius': SEARCH_RADIUS,
        'unit': 'km',
        'page': page,
        'keyword': name,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        json_ = response.json()

        if "fault" in json_:
            try:
                if json_["fault"]["detail"]["errorcode"] == 'policies.ratelimit.SpikeArrestViolation':
                    raise RateLimitError
            except KeyError:
                print(json_)
                raise Exception

            print(json_)
            raise Exception

        return json_


if __name__ == "__main__":
    print(asyncio.run(get_events_by_name("")))
