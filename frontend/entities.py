import datetime
from dataclasses import dataclass


@dataclass
class Event:
    name: str
    artist: str
    url: str
    city: str
    country: str
    country_code: str
    date: datetime.date
    # distance_km: float
    id: str
