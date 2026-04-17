"""Geocoding service for investigative location entities.

Resolves location entity names to lat/lng coordinates using a curated
lookup table with 200+ entries and fuzzy matching via difflib.
No external API calls — fully self-contained for Lambda deployment.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Optional

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.8


class GeocodingService:
    """Resolves location entity names to coordinates."""

    # 200+ curated location-to-coordinate mappings
    CURATED_LOCATIONS: dict[str, tuple[float, float]] = {
        # --- US Cities (top 50 + investigative) ---
        "new york": (40.7128, -74.0060), "new york city": (40.7128, -74.0060), "manhattan": (40.7831, -73.9712),
        "brooklyn": (40.6782, -73.9442), "queens": (40.7282, -73.7949), "bronx": (40.8448, -73.8648),
        "los angeles": (34.0522, -118.2437), "chicago": (41.8781, -87.6298), "houston": (29.7604, -95.3698),
        "phoenix": (33.4484, -112.0740), "philadelphia": (39.9526, -75.1652), "san antonio": (29.4241, -98.4936),
        "san diego": (32.7157, -117.1611), "dallas": (32.7767, -96.7970), "san jose": (37.3382, -121.8863),
        "austin": (30.2672, -97.7431), "jacksonville": (30.3322, -81.6557), "fort worth": (32.7555, -97.3308),
        "columbus": (39.9612, -82.9988), "charlotte": (35.2271, -80.8431), "san francisco": (37.7749, -122.4194),
        "indianapolis": (39.7684, -86.1581), "seattle": (47.6062, -122.3321), "denver": (39.7392, -104.9903),
        "washington": (38.9072, -77.0369), "washington dc": (38.9072, -77.0369), "washington d.c.": (38.9072, -77.0369),
        "nashville": (36.1627, -86.7816), "oklahoma city": (35.4676, -97.5164), "el paso": (31.7619, -106.4850),
        "boston": (42.3601, -71.0589), "portland": (45.5152, -122.6784), "las vegas": (36.1699, -115.1398),
        "memphis": (35.1495, -90.0490), "louisville": (38.2527, -85.7585), "baltimore": (39.2904, -76.6122),
        "milwaukee": (43.0389, -87.9065), "albuquerque": (35.0844, -106.6504), "tucson": (32.2226, -110.9747),
        "fresno": (36.7378, -119.7871), "sacramento": (38.5816, -121.4944), "mesa": (33.4152, -111.8315),
        "kansas city": (39.0997, -94.5786), "atlanta": (33.7490, -84.3880), "omaha": (41.2565, -95.9345),
        "colorado springs": (38.8339, -104.8214), "raleigh": (35.7796, -78.6382), "long beach": (33.7701, -118.1937),
        "virginia beach": (36.8529, -75.9780), "miami": (25.7617, -80.1918), "oakland": (37.8044, -122.2712),
        "minneapolis": (44.9778, -93.2650), "tampa": (27.9506, -82.4572), "tulsa": (36.1540, -95.9928),
        "arlington": (32.7357, -97.1081), "new orleans": (29.9511, -90.0715), "cleveland": (41.4993, -81.6944),
        "detroit": (42.3314, -83.0458), "pittsburgh": (40.4406, -79.9959), "st louis": (38.6270, -90.1994),
        "saint louis": (38.6270, -90.1994), "cincinnati": (39.1031, -84.5120), "orlando": (28.5383, -81.3792),
        "honolulu": (21.3069, -157.8583), "anchorage": (61.2181, -149.9003), "santa fe": (35.6870, -105.9378),
        # --- US States ---
        "florida": (27.6648, -81.5158), "california": (36.7783, -119.4179), "texas": (31.9686, -99.9018),
        "new york state": (42.1657, -74.9481), "ohio": (40.4173, -82.9071), "georgia": (32.1656, -82.9001),
        "virginia": (37.4316, -78.6569), "illinois": (40.6331, -89.3985), "pennsylvania": (41.2033, -77.1945),
        "north carolina": (35.7596, -79.0193), "michigan": (44.3148, -85.6024), "new jersey": (40.0583, -74.4057),
        "maryland": (39.0458, -76.6413), "connecticut": (41.6032, -73.0877), "massachusetts": (42.4072, -71.3824),
        "colorado": (39.5501, -105.7821), "arizona": (34.0489, -111.0937), "tennessee": (35.5175, -86.5804),
        "missouri": (37.9643, -91.8318), "indiana": (40.2672, -86.1349), "wisconsin": (43.7844, -88.7879),
        "minnesota": (46.7296, -94.6859), "louisiana": (30.9843, -91.9623), "kentucky": (37.8393, -84.2700),
        "oregon": (43.8041, -120.5542), "south carolina": (33.8361, -81.1637), "alabama": (32.3182, -86.9023),
        "utah": (39.3210, -111.0937), "nevada": (38.8026, -116.4194), "iowa": (41.8780, -93.0977),
        "mississippi": (32.3547, -89.3985), "arkansas": (35.2010, -91.8318), "kansas": (39.0119, -98.4842),
        "nebraska": (41.4925, -99.9018), "new mexico": (34.5199, -105.8701), "hawaii": (19.8968, -155.5828),
        "alaska": (64.2008, -152.4937), "maine": (45.2538, -69.4455), "montana": (46.8797, -110.3626),
        "delaware": (38.9108, -75.5277), "rhode island": (41.5801, -71.4774), "vermont": (44.5588, -72.5778),
        "wyoming": (43.0760, -107.2903), "west virginia": (38.5976, -80.4549), "idaho": (44.0682, -114.7420),
        "north dakota": (47.5515, -101.0020), "south dakota": (43.9695, -99.9018),
        # --- Palm Beach / Epstein-relevant ---
        "palm beach": (26.7056, -80.0364), "west palm beach": (26.7153, -80.0534),
        "virgin islands": (18.3358, -64.8963), "us virgin islands": (18.3358, -64.8963),
        "st thomas": (18.3358, -64.9307), "saint thomas": (18.3358, -64.9307),
        "st croix": (17.7290, -64.7343), "saint croix": (17.7290, -64.7343),
        "st john": (18.3358, -64.7281), "saint john": (18.3358, -64.7281),
        "little st james island": (18.3000, -64.8256), "little saint james": (18.3000, -64.8256),
        "great st james island": (18.3192, -64.8536), "epstein island": (18.3000, -64.8256),
        "zorro ranch": (35.0200, -105.3100), "stanley new mexico": (35.0200, -105.3100),
        # --- International Capitals & Major Cities ---
        "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522), "berlin": (52.5200, 13.4050),
        "rome": (41.9028, 12.4964), "madrid": (40.4168, -3.7038), "moscow": (55.7558, 37.6173),
        "tokyo": (35.6762, 139.6503), "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
        "hong kong": (22.3193, 114.1694), "singapore": (1.3521, 103.8198), "dubai": (25.2048, 55.2708),
        "abu dhabi": (24.4539, 54.3773), "sydney": (33.8688, 151.2093), "melbourne": (-37.8136, 144.9631),
        "toronto": (43.6532, -79.3832), "vancouver": (49.2827, -123.1207), "montreal": (45.5017, -73.5673),
        "mexico city": (19.4326, -99.1332), "sao paulo": (-23.5505, -46.6333), "rio de janeiro": (-22.9068, -43.1729),
        "buenos aires": (-34.6037, -58.3816), "bogota": (4.7110, -74.0721), "lima": (-12.0464, -77.0428),
        "santiago": (-33.4489, -70.6693), "cairo": (30.0444, 31.2357), "johannesburg": (-26.2041, 28.0473),
        "cape town": (-33.9249, 18.4241), "nairobi": (-1.2921, 36.8219), "lagos": (6.5244, 3.3792),
        "mumbai": (19.0760, 72.8777), "new delhi": (28.6139, 77.2090), "bangkok": (13.7563, 100.5018),
        "jakarta": (-6.2088, 106.8456), "seoul": (37.5665, 126.9780), "taipei": (25.0330, 121.5654),
        "istanbul": (41.0082, 28.9784), "athens": (37.9838, 23.7275), "vienna": (48.2082, 16.3738),
        "zurich": (47.3769, 8.5417), "geneva": (46.2044, 6.1432), "amsterdam": (52.3676, 4.9041),
        "brussels": (50.8503, 4.3517), "lisbon": (38.7223, -9.1393), "dublin": (53.3498, -6.2603),
        "edinburgh": (55.9533, -3.1883), "oslo": (59.9139, 10.7522), "stockholm": (59.3293, 18.0686),
        "copenhagen": (55.6761, 12.5683), "helsinki": (60.1699, 24.9384), "warsaw": (52.2297, 21.0122),
        "prague": (50.0755, 14.4378), "budapest": (47.4979, 19.0402), "bucharest": (44.4268, 26.1025),
        "tel aviv": (32.0853, 34.7818), "jerusalem": (31.7683, 35.2137), "riyadh": (24.7136, 46.6753),
        "doha": (25.2854, 51.5310), "kuwait city": (29.3759, 47.9774), "manama": (26.2285, 50.5860),
        # --- Caribbean & Islands ---
        "bahamas": (25.0343, -77.3963), "nassau": (25.0480, -77.3554), "bermuda": (32.3078, -64.7505),
        "cayman islands": (19.3133, -81.2546), "grand cayman": (19.3222, -81.2409),
        "barbados": (13.1939, -59.5432), "jamaica": (18.1096, -77.2975), "kingston": (18.0179, -76.8099),
        "trinidad": (10.6918, -61.2225), "puerto rico": (18.2208, -66.5901), "san juan": (18.4655, -66.1057),
        "antigua": (17.0608, -61.7964), "st barts": (17.8966, -62.8498), "saint barthelemy": (17.8966, -62.8498),
        "turks and caicos": (21.6940, -71.7979), "aruba": (12.5211, -69.9683), "curacao": (12.1696, -68.9900),
        "dominican republic": (18.7357, -70.1627), "santo domingo": (18.4861, -69.9312),
        "haiti": (18.9712, -72.2852), "cuba": (21.5218, -77.7812), "havana": (23.1136, -82.3666),
        # --- Financial Centers & Offshore ---
        "wall street": (40.7074, -74.0113), "city of london": (51.5155, -0.0922),
        "canary wharf": (51.5054, -0.0235), "swiss alps": (46.8182, 8.2275),
        "liechtenstein": (47.1660, 9.5554), "luxembourg": (49.6117, 6.1300),
        "monaco": (43.7384, 7.4246), "isle of man": (54.2361, -4.5481),
        "jersey": (49.2144, -2.1312), "guernsey": (49.4542, -2.5369),
        "british virgin islands": (18.4207, -64.6400), "tortola": (18.4283, -64.6189),
        "panama": (8.9824, -79.5199), "panama city": (8.9824, -79.5199),
        "belize": (17.1899, -88.4976), "costa rica": (9.7489, -83.7534),
        # --- Airports ---
        "jfk airport": (40.6413, -73.7781), "lax airport": (33.9416, -118.4085),
        "heathrow": (51.4700, -0.4543), "miami international": (25.7959, -80.2870),
        "teterboro airport": (40.8501, -74.0608), "le bourget": (48.9694, 2.4414),
        # --- Airport Codes (IATA) ---
        "jfk": (40.6413, -73.7781), "lax": (33.9416, -118.4085), "lga": (40.7769, -73.8740),
        "ewr": (40.6895, -74.1745), "ord": (41.9742, -87.9073), "sfo": (37.6213, -122.3790),
        "mia": (25.7959, -80.2870), "atl": (33.6407, -84.4277), "dfw": (32.8998, -97.0403),
        "iad": (38.9531, -77.4565), "bos": (42.3656, -71.0096), "pbi": (26.6832, -80.0956),
        "stt": (18.3373, -64.9734), "stx": (17.7019, -64.7986), "teb": (40.8501, -74.0608),
        "cdg": (49.0097, 2.5479), "lhr": (51.4700, -0.4543), "lgw": (51.1537, -0.1821),
        "nrt": (35.7647, 140.3864), "hnd": (35.5494, 139.7798), "dxb": (25.2532, 55.3657),
        "sin": (1.3644, 103.9915), "hkg": (22.3080, 113.9185), "rak": (31.6069, -8.0363),
        "nyc": (40.7128, -74.0060), "isp": (40.7952, -73.1002),
        # --- Common abbreviations ---
        "islip": (40.7298, -73.2137), "marrakech": (31.6295, -7.9811), "marrakesh": (31.6295, -7.9811),
        # --- US State Capitals (not already listed) ---
        "albany": (42.6526, -73.7562), "annapolis": (38.9784, -76.4922),
        "baton rouge": (30.4515, -91.1871), "bismarck": (46.8083, -100.7837),
        "boise": (43.6150, -116.2023), "carson city": (39.1638, -119.7674),
        "charleston": (38.3498, -81.6326), "cheyenne": (41.1400, -104.8202),
        "columbia": (34.0007, -81.0348), "concord": (43.2081, -71.5376),
        "dover": (39.1582, -75.5244), "frankfort": (38.2009, -84.8733),
        "harrisburg": (40.2732, -76.8867), "hartford": (41.7658, -72.6734),
        "helena": (46.5891, -112.0391), "jackson": (32.2988, -90.1848),
        "jefferson city": (38.5767, -92.1735), "juneau": (58.3005, -134.4197),
        "lansing": (42.7325, -84.5555), "lincoln": (40.8136, -96.7026),
        "little rock": (34.7465, -92.2896), "madison": (43.0731, -89.4012),
        "montgomery": (32.3792, -86.3077), "montpelier": (44.2601, -72.5754),
        "olympia": (47.0379, -122.9007), "pierre": (44.3683, -100.3510),
        "providence": (41.8240, -71.4128), "richmond": (37.5407, -77.4360),
        "salem": (44.9429, -123.0351), "salt lake city": (40.7608, -111.8910),
        "springfield": (39.7817, -89.6501), "tallahassee": (30.4383, -84.2807),
        "topeka": (39.0473, -95.6752), "trenton": (40.2171, -74.7429),
        # --- Countries (general center) ---
        "united states": (39.8283, -98.5795), "united kingdom": (55.3781, -3.4360),
        "france": (46.2276, 2.2137), "germany": (51.1657, 10.4515), "italy": (41.8719, 12.5674),
        "spain": (40.4637, -3.7492), "russia": (61.5240, 105.3188), "china": (35.8617, 104.1954),
        "japan": (36.2048, 138.2529), "india": (20.5937, 78.9629), "brazil": (-14.2350, -51.9253),
        "australia": (-25.2744, 133.7751), "canada": (56.1304, -106.3468), "mexico": (23.6345, -102.5528),
        "israel": (31.0461, 34.8516), "saudi arabia": (23.8859, 45.0792), "south korea": (35.9078, 127.7669),
        "switzerland": (46.8182, 8.2275), "sweden": (60.1282, 18.6435), "norway": (60.4720, 8.4689),
        "denmark": (56.2639, 9.5018), "netherlands": (52.1326, 5.2913), "belgium": (50.5039, 4.4699),
        "portugal": (39.3999, -8.2245), "ireland": (53.1424, -7.6921), "poland": (51.9194, 19.1451),
        "czech republic": (49.8175, 15.4730), "austria": (47.5162, 14.5501), "greece": (39.0742, 21.8243),
        "turkey": (38.9637, 35.2433), "egypt": (26.8206, 30.8025), "south africa": (-30.5595, 22.9375),
        "nigeria": (9.0820, 8.6753), "kenya": (-0.0236, 37.9062), "colombia": (4.5709, -74.2973),
        "argentina": (-38.4161, -63.6167), "chile": (-35.6751, -71.5430), "peru": (-9.1900, -75.0152),
        "venezuela": (6.4238, -66.5897), "thailand": (15.8700, 100.9925), "vietnam": (14.0583, 108.2772),
        "philippines": (12.8797, 121.7740), "indonesia": (-0.7893, 113.9213), "malaysia": (4.2105, 101.9758),
        "taiwan": (23.6978, 120.9605), "uae": (23.4241, 53.8478), "qatar": (25.3548, 51.1839),
    }

    def _normalize(self, name: str) -> str:
        """Lowercase, strip punctuation, remove state/country suffixes."""
        n = name.lower().strip()
        n = re.sub(r"[,;:!?\"'()\[\]{}]", "", n)
        # Remove trailing state/country like "Miami, FL" or "Paris, France"
        n = re.sub(r"\s+(fl|ca|tx|ny|nj|ct|ma|pa|oh|il|ga|va|nc|md|co|az|tn|mo|in|wi|mn|la|ky|or|sc|al|ut|nv|ia|ms|ar|ks|ne|nm|hi|ak|me|mt|de|ri|vt|wy|wv|id|nd|sd|dc|usa|us|uk)$", "", n)
        n = re.sub(r"\s+", " ", n).strip()
        return n

    def _fuzzy_match(self, normalized: str) -> Optional[tuple[str, float]]:
        """Find best match in CURATED_LOCATIONS above threshold. Tie-break alphabetically."""
        best_name = None
        best_score = 0.0
        for loc_name in self.CURATED_LOCATIONS:
            score = SequenceMatcher(None, normalized, loc_name).ratio()
            if score > best_score or (score == best_score and (best_name is None or loc_name < best_name)):
                best_score = score
                best_name = loc_name
        if best_score >= FUZZY_THRESHOLD and best_name:
            return (best_name, best_score)
        return None

    def geocode(self, names: list[str]) -> dict[str, dict]:
        """Resolve location names to coordinates.

        Returns: {"geocoded": {name: {"lat": float, "lng": float}}, "unresolved": [str], "total": int, "resolved": int}
        """
        geocoded = {}
        unresolved = []
        for name in names:
            norm = self._normalize(name)
            # Exact match first
            if norm in self.CURATED_LOCATIONS:
                lat, lng = self.CURATED_LOCATIONS[norm]
                geocoded[name] = {"lat": lat, "lng": lng}
                continue
            # Fuzzy match
            match = self._fuzzy_match(norm)
            if match:
                matched_name, _ = match
                lat, lng = self.CURATED_LOCATIONS[matched_name]
                geocoded[name] = {"lat": lat, "lng": lng}
            else:
                unresolved.append(name)
        return {"geocoded": geocoded, "unresolved": unresolved, "total": len(names), "resolved": len(geocoded)}

    def cross_case_locations(self, case_id: str, aurora_cm: Any) -> list[dict]:
        """Query entities table for locations shared across cases."""
        results = []
        try:
            with aurora_cm.cursor() as cur:
                cur.execute(
                    "SELECT e1.canonical_name, e2.case_file_id, "
                    "COALESCE(m.matter_name, cf.topic_name, e2.case_file_id::text) as case_name "
                    "FROM entities e1 "
                    "JOIN entities e2 ON e1.canonical_name = e2.canonical_name AND e1.entity_type = e2.entity_type "
                    "LEFT JOIN matters m ON e2.case_file_id = m.matter_id "
                    "LEFT JOIN case_files cf ON e2.case_file_id = cf.case_id "
                    "WHERE e1.case_file_id = %s AND e1.entity_type = 'location' "
                    "AND e2.case_file_id != %s AND e2.entity_type = 'location' "
                    "ORDER BY e1.canonical_name",
                    (case_id, case_id),
                )
                rows = cur.fetchall()
                loc_map: dict[str, list[dict]] = {}
                for row in rows:
                    loc_name, other_case_id, case_name = row[0], str(row[1]), row[2]
                    if loc_name not in loc_map:
                        loc_map[loc_name] = []
                    if not any(c["case_id"] == other_case_id for c in loc_map[loc_name]):
                        loc_map[loc_name].append({"case_id": other_case_id, "case_name": case_name or other_case_id})
                for loc_name, cases in loc_map.items():
                    results.append({"location": loc_name, "cases": cases, "case_count": len(cases)})
        except Exception as e:
            logger.error("Cross-case location query failed: %s", str(e)[:200])
        return results
