"""Stable City, ST pins for public listing thumbnails.

Core cities are reused. About one listing in eighteen uses the other-region
list so roughly thirty units show nationwide cities on a 540-unit board.
The same unit always gets the same city.
"""

from __future__ import annotations

CORE_CITIES = (
    "Houston, TX",
    "Orlando, FL",
    "Atlanta, GA",
    "Oklahoma City, OK",
    "Las Vegas, NV",
    "Miami, FL",
    "Dallas, TX",
    "Savannah, GA",
    "Tulsa, OK",
    "Reno, NV",
    "Austin, TX",
    "Tampa, FL",
    "Augusta, GA",
    "Norman, OK",
    "Henderson, NV",
    "San Antonio, TX",
    "Jacksonville, FL",
    "Macon, GA",
    "Lawton, OK",
    "North Las Vegas, NV",
    "Fort Worth, TX",
    "Tallahassee, FL",
    "Columbus, GA",
    "Broken Arrow, OK",
    "Carson City, NV",
    "El Paso, TX",
    "Fort Lauderdale, FL",
    "Athens, GA",
    "Edmond, OK",
    "Sparks, NV",
    "Arlington, TX",
    "St. Petersburg, FL",
    "Sandy Springs, GA",
    "Moore, OK",
    "Elko, NV",
    "Corpus Christi, TX",
    "West Palm Beach, FL",
    "Roswell, GA",
    "Enid, OK",
    "Mesquite, NV",
    "Plano, TX",
    "Gainesville, FL",
    "Johns Creek, GA",
    "Midwest City, OK",
    "Boulder City, NV",
    "Lubbock, TX",
    "Ocala, FL",
    "Warner Robins, GA",
    "Stillwater, OK",
    "Pahrump, NV",
    "Laredo, TX",
    "Sarasota, FL",
    "Alpharetta, GA",
    "Muskogee, OK",
    "Fernley, NV",
    "Amarillo, TX",
    "Pensacola, FL",
    "Marietta, GA",
    "Bartlesville, OK",
    "Winnemucca, NV",
    "Lynchburg, VA",
    "Charleston, SC",
    "Birmingham, AL",
    "Nashville, TN",
    "Charlotte, NC",
    "Little Rock, AR",
    "Baton Rouge, LA",
    "Jackson, MS",
    "Louisville, KY",
    "Mobile, AL",
)

OTHER_CITIES = (
    "Phoenix, AZ",
    "Denver, CO",
    "Seattle, WA",
    "Chicago, IL",
    "Boston, MA",
    "Columbus, OH",
    "Indianapolis, IN",
    "Detroit, MI",
    "Milwaukee, WI",
    "Minneapolis, MN",
    "Kansas City, MO",
    "Omaha, NE",
    "Wichita, KS",
    "Salt Lake City, UT",
    "Boise, ID",
    "Portland, OR",
    "San Diego, CA",
    "Sacramento, CA",
    "Philadelphia, PA",
    "Newark, NJ",
    "Baltimore, MD",
    "Buffalo, NY",
    "Hartford, CT",
    "Providence, RI",
    "Manchester, NH",
    "Burlington, VT",
    "Portland, ME",
    "Albuquerque, NM",
    "Cheyenne, WY",
    "Billings, MT",
)

OTHER_EVERY = 18


def city_hash(key: str) -> int:
    h = 2166136261
    for byte in str(key or "").encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def city_for(unit_key: str) -> str:
    """Return City, ST for a listing card. Stable for the same unit id."""
    h = city_hash(unit_key)
    if h % OTHER_EVERY == 0:
        return OTHER_CITIES[h % len(OTHER_CITIES)]
    return CORE_CITIES[(h // OTHER_EVERY) % len(CORE_CITIES)]
