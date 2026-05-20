import collections
import asyncio
import json
import urllib.request
from datetime import datetime
from uuid import uuid4
from typing import List, Dict, Any, Optional, Callable

try:
    from models import RawSignal, SignalSource
except ImportError:
    from ..models import RawSignal, SignalSource

class SocialPostGenerator:
    FLOOD_POSTS_G10 = [
        {"urdu": "G-10/3 mein pani bhar gaya hai, gali number 4 band ho gayi. Koi rescue nahin aaya abhi tak!", "geo": "G-10, Islamabad", "urgency": 0.9},
        {"urdu": "Bahut zyada barish, G-10 markaz ke paas road block ho gayi water se", "geo": "G-10, Islamabad", "urgency": 0.7},
        {"urdu": "G-10/1 residents please evacuate, ground floor mein paani aa gaya hai", "geo": "G-10, Islamabad", "urgency": 0.95},
        {"urdu": "Cars floating in G-10 sector, Ring Road under 3 feet water", "geo": "Ring Road near G-10", "urgency": 0.92},
        {"urdu": "Emergency! G-10 nala overflowing. Please send help. Children trapped.", "geo": "G-10, Islamabad", "urgency": 1.0},
        {"urdu": "CCTV footage shows G-10 main bazar completely underwater", "geo": "G-10 Markaz", "urgency": 0.85}
    ]
    
    HEATWAVE_POSTS_GULBERG = [
        {"urdu": "Gulberg mein aj 43 degree temperature. 3 log heat stroke se hospital gaye", "geo": "Gulberg, Lahore", "urgency": 0.8},
        {"urdu": "WARNING: Extreme heat in Gulberg. Avoid going outside between 12-4pm", "geo": "Gulberg III, Lahore", "urgency": 0.75},
        {"urdu": "WASA paani band hai Gulberg mein, garmi mein pani ka bhi masla", "geo": "Gulberg, Lahore", "urgency": 0.7}
    ]
    
    FALSE_POSITIVE_POSTS = [
        {"urdu": "Update: jo G-10 mein paani tha wo actually water main burst tha, flood nahin", "geo": "G-10, Islamabad", "urgency": 0.6},
        {"urdu": "CLARIFICATION: Water in G-10 7th Avenue is from a burst water main, not flooding. Repair crew on site.", "geo": "G-10, Islamabad", "urgency": 0.5}
    ]

    def generate_flood_scenario(self, location="G-10, Islamabad", count=5) -> List[RawSignal]:
        signals = []
        posts = self.FLOOD_POSTS_G10[:count]
        for idx, post in enumerate(posts):
            signals.append(RawSignal(
                signal_id=f"sig-soc-f-{idx+1}",
                source_type=SignalSource.SOCIAL_MEDIA,
                content=post["urdu"],
                location=post["geo"],
                latitude=33.6938,
                longitude=73.0652,
                recency_minutes=2 + idx * 2,
                mention_frequency=15 + idx * 5,
                geo_precision=0.80,
                raw_metadata={"urgency": post["urgency"]}
            ))
        return signals

    def generate_heatwave_scenario(self, location="Gulberg, Lahore", count=3) -> List[RawSignal]:
        signals = []
        posts = self.HEATWAVE_POSTS_GULBERG[:count]
        for idx, post in enumerate(posts):
            signals.append(RawSignal(
                signal_id=f"sig-soc-h-{idx+1}",
                source_type=SignalSource.SOCIAL_MEDIA,
                content=post["urdu"],
                location=post["geo"],
                latitude=33.6007,
                longitude=73.0679,
                recency_minutes=5 + idx * 3,
                mention_frequency=8 + idx * 3,
                geo_precision=0.75,
                raw_metadata={"urgency": post["urgency"]}
            ))
        return signals

    def generate_false_positive_correction(self, original_location="G-10, Islamabad") -> List[RawSignal]:
        signals = []
        for idx, post in enumerate(self.FALSE_POSITIVE_POSTS):
            signals.append(RawSignal(
                signal_id=f"sig-soc-fp-{idx+1}",
                source_type=SignalSource.SOCIAL_MEDIA,
                content=post["urdu"],
                location=post["geo"],
                latitude=33.6938,
                longitude=73.0652,
                recency_minutes=1,
                mention_frequency=4 + idx * 2,
                geo_precision=0.85,
                raw_metadata={"urgency": post["urgency"]}
            ))
        return signals

    def generate_stream(self, scenario="g10_flood") -> List[RawSignal]:
        if scenario == "g10_flood":
            return self.generate_flood_scenario()
        elif scenario == "gulberg_heatwave":
            return self.generate_heatwave_scenario()
        elif scenario == "false_positive":
            return self.generate_false_positive_correction()
        return []

    def get_social_signal(self, location: str, content: str, scenario: str) -> RawSignal:
        lat = 30.1798 if "Quetta" in location else (24.8607 if "Karachi" in location else 31.5204)
        lng = 66.9750 if "Quetta" in location else (67.0011 if "Karachi" in location else 74.3587)
        return RawSignal(
            signal_id=f"soc-{uuid4().hex[:6]}",
            source_type=SignalSource.SOCIAL_MEDIA,
            content=content,
            location=location,
            latitude=lat,
            longitude=lng,
            recency_minutes=1,
            mention_frequency=50,
            geo_precision=0.85,
            raw_metadata={"urgency": 0.9}
        )

class WeatherMockAPI:
    ISLAMABAD_FLOOD_WEATHER = {
        "city": "Islamabad", "temperature_celsius": 28.0,
        "rainfall_mm_last_hour": 87.3, "wind_speed_kmh": 42.0,
        "humidity_percent": 94, "weather_condition": "Thunderstorm",
        "weather_alert": "FLOOD WATCH: Heavy rainfall expected to continue 3+ hours.",
        "forecast_6h_rainfall_mm": 45.0
    }
    
    LAHORE_HEATWAVE_WEATHER = {
        "city": "Lahore", "temperature_celsius": 43.0,
        "rainfall_mm_last_hour": 0.0, "wind_speed_kmh": 8.0,
        "humidity_percent": 15, "weather_condition": "Clear",
        "weather_alert": "HEAT WARNING: Temperature expected to reach 45°C.",
        "heat_index_celsius": 47.2
    }

    def get_weather_signal(self, city: str, scenario: str) -> RawSignal:
        data = self.ISLAMABAD_FLOOD_WEATHER if "flood" in scenario.lower() else self.LAHORE_HEATWAVE_WEATHER
        lat = 33.6938 if city == "Islamabad" else 33.6007
        lng = 73.0652 if city == "Islamabad" else 73.0679
        return RawSignal(
            signal_id=f"sig-wea-{city.lower()}",
            source_type=SignalSource.WEATHER_API,
            content=f"Weather alert for {city}: {data['weather_alert']} Temp: {data['temperature_celsius']}C, Rain last hour: {data['rainfall_mm_last_hour']}mm",
            location=f"{city}, Pakistan",
            latitude=lat,
            longitude=lng,
            recency_minutes=0,
            mention_frequency=1,
            geo_precision=0.98,
            raw_metadata=data
        )

    def get_real_weather(self, city: str, api_key: str, on_failure: Optional[Callable[[], None]] = None) -> Optional[RawSignal]:
        # Map specific locations to wttr.in city names
        city_query = city.split(",")[0].strip()
        if city_query.lower() == "gulberg":
            city_query = "Lahore"
            
        url = f"https://wttr.in/{city_query}?format=j1"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CIRO-App"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                current = data.get("current_condition", [{}])[0]
                temp = current.get("temp_C", "28")
                desc = current.get("weatherDesc", [{"value": "Unknown"}])[0].get("value", "Unknown")
                humidity = current.get("humidity", "0")
                precip = current.get("precipMM", "0")
                
                lat, lng = 33.6844, 73.0479
                c_low = city_query.lower()
                if c_low == "islamabad":
                    lat, lng = 33.6938, 73.0652
                elif c_low == "lahore":
                    lat, lng = 31.5204, 74.3587
                elif c_low == "karachi":
                    lat, lng = 24.8607, 67.0011
                elif c_low == "quetta":
                    lat, lng = 30.1798, 66.9750
                
                return RawSignal(
                    signal_id=f"sig-wea-real-{city_query.lower()}",
                    source_type=SignalSource.WEATHER_API,
                    content=f"Live weather for {city_query}: {desc.upper()} Temp: {temp}C, Humidity: {humidity}%, Precip: {precip}mm.",
                    location=f"{city_query}, Pakistan",
                    latitude=lat,
                    longitude=lng,
                    recency_minutes=0,
                    mention_frequency=1,
                    geo_precision=1.0,
                    raw_metadata=data
                )
        except Exception as e:
            print(f"Error fetching live weather: {e}")
            if on_failure:
                try:
                    on_failure()
                except Exception:
                    pass
            return None

class TrafficMockAPI:
    G10_FLOOD_TRAFFIC = {
        "affected_roads": ["G-10 Main Boulevard", "Ring Road Exit 5", "Margalla Road"],
        "congestion_levels": {"G-10 Main Boulevard": "SEVERE", "Ring Road Exit 5": "HEAVY", "Margalla Road": "MODERATE"},
        "incidents": [
            {"type": "ROAD_CLOSED", "location": "G-10/3 Main Gali", "cause": "Standing water"},
            {"type": "TRAFFIC_JAM", "location": "Ring Road near G-10 Interchange", "delay_minutes": 45}
        ],
        "alternate_routes": [
            {"from": "Ring Road", "to": "Islamabad Expressway", "via": "IJP Road", "added_time_min": 12},
            {"from": "G-10", "to": "G-8", "via": "Fazaia Road", "added_time_min": 8}
        ]
    }

    def get_traffic_signal(self, location: str, scenario: str) -> RawSignal:
        lat = 33.6938 if "G-10" in location else 33.6007
        lng = 73.0652 if "G-10" in location else 73.0679
        return RawSignal(
            signal_id="sig-tra-1",
            source_type=SignalSource.GOOGLE_MAPS,
            content=f"Google Maps Traffic: Severe congestion and road closures reported near {location}.",
            location=location,
            latitude=lat,
            longitude=lng,
            recency_minutes=1,
            mention_frequency=1,
            geo_precision=0.90,
            raw_metadata=self.G10_FLOOD_TRAFFIC
        )

    def get_alternate_routes(self, location: str, scenario: str) -> List[Dict[str, Any]]:
        return self.G10_FLOOD_TRAFFIC["alternate_routes"]

class EmergencyCallFeed:
    def get_call_spike_signal(self, location: str, calls_per_minute: int, scenario: str) -> RawSignal:
        lat = 33.6938 if "G-10" in location else 33.6007
        lng = 73.0652 if "G-10" in location else 73.0679
        return RawSignal(
            signal_id="sig-cal-1",
            source_type=SignalSource.EMERGENCY_CALL,
            content=f"NDMA Emergency Hotline: Call volume spike detected at {location}. Current: {calls_per_minute} calls/min.",
            location=location,
            latitude=lat,
            longitude=lng,
            recency_minutes=2,
            mention_frequency=1,
            geo_precision=0.88,
            raw_metadata={"calls_per_minute": calls_per_minute, "baseline": 2}
        )

    def generate_call_log(self, scenario: str, duration_minutes=10) -> List[RawSignal]:
        return []

class FloodZoneData:
    def get_historical_signal(self, location: str) -> RawSignal:
        lat = 33.6938 if "G-10" in location else 33.6007
        lng = 73.0652 if "G-10" in location else 73.0679
        return RawSignal(
            signal_id="sig-his-1",
            source_type=SignalSource.HISTORICAL_DATA,
            content=f"NDMA Risk Database: {location} is marked as a historically high-risk zone.",
            location=location,
            latitude=lat,
            longitude=lng,
            recency_minutes=0,
            mention_frequency=1,
            geo_precision=1.0,
            raw_metadata={"zone_risk_level": "CRITICAL"}
        )

    def get_zone_risk_level(self, location: str) -> str:
        return "CRITICAL" if "G-10" in location else "HIGH"

class SignalStreamScheduler:
    """
    Maintains an internal signal buffer (collections.deque, maxlen=200).
    FastAPI WebSocket handler reads from this buffer — scheduler does NOT
    directly write to any WebSocket connection.
    """
    
    def __init__(self):
        self.buffer = collections.deque(maxlen=200)
        self.social_gen = SocialPostGenerator()
        self.weather_api = WeatherMockAPI()
        self.traffic_api = TrafficMockAPI()
        self.call_feed = EmergencyCallFeed()
        self.flood_zones = FloodZoneData()
    
    def _build_scenario_signals(self, scenario: str) -> List[RawSignal]:
        signals = []
        scenario_clean = scenario.lower().strip()
        
        if scenario_clean == "g10_flood":
            # 3 social + 1 weather + 1 traffic + 1 emergency_call + 1 historical = 7
            signals.extend(self.social_gen.generate_flood_scenario(count=3))
            signals.append(self.weather_api.get_weather_signal("Islamabad", "g10_flood"))
            signals.append(self.traffic_api.get_traffic_signal("G-10, Islamabad", "g10_flood"))
            signals.append(self.call_feed.get_call_spike_signal("G-10, Islamabad", 18, "g10_flood"))
            signals.append(self.flood_zones.get_historical_signal("G-10, Islamabad"))
            
        elif scenario_clean == "gulberg_heatwave":
            # 2 social + 1 weather + 1 medical_call = 4
            signals.extend(self.social_gen.generate_heatwave_scenario(count=2))
            signals.append(self.weather_api.get_weather_signal("Lahore", "gulberg_heatwave"))
            signals.append(self.call_feed.get_call_spike_signal("Gulberg, Lahore", 12, "gulberg_heatwave"))
            
        elif scenario_clean == "dual_crisis":
            # flood + heatwave = 11
            signals.extend(self._build_scenario_signals("g10_flood"))
            # Make sure we don't duplicate IDs
            heat_signals = self._build_scenario_signals("gulberg_heatwave")
            for h in heat_signals:
                h.signal_id = h.signal_id + "-dual"
            signals.extend(heat_signals)
            
        elif scenario_clean == "false_positive":
            # g10_flood + 2 correction = 9
            signals.extend(self._build_scenario_signals("g10_flood"))
            signals.extend(self.social_gen.generate_false_positive_correction())
            
        elif scenario_clean == "robustness_test":
            # 3 signals only
            signals.extend(self.social_gen.generate_flood_scenario(count=2))
            signals.append(self.traffic_api.get_traffic_signal("G-10, Islamabad", "g10_flood"))
            
        elif scenario_clean == "balochistan_earthquake":
            signals.extend([
                self.social_gen.get_social_signal("Quetta", "Did anyone else feel that? The whole house was shaking! #earthquake #Quetta", scenario),
                self.social_gen.get_social_signal("Quetta", "زلزلہ! یا اللہ رحم کر۔ (Earthquake! Oh Allah have mercy)", scenario),
                self.weather_api.get_weather_signal("Quetta", scenario)
            ])
            
        elif scenario_clean == "karachi_industrial_fire":
            signals.extend([
                self.social_gen.get_social_signal("SITE Area, Karachi", "Massive fire in SITE industrial area. Toxic smoke everywhere.", scenario),
                self.traffic_api.get_traffic_signal("SITE Area, Karachi", scenario)
            ])
            
        elif scenario_clean == "lahore_smog_health_crisis":
            signals.extend([
                self.social_gen.get_social_signal("Lahore", "AQI is 600+ today. Kids are getting sick. Close the schools!", scenario),
                self.call_feed.get_call_spike_signal("Lahore", 15, scenario)
            ])
            
        return signals

    def get_scenario_signals(self, scenario: str = "g10_flood") -> List[RawSignal]:
        signals = self._build_scenario_signals(scenario)
        for s in signals:
            self.buffer.append(s)
        return signals
    
    def get_buffered_signals(self, max_count: int = 50) -> List[RawSignal]:
        buf_list = list(self.buffer)
        return buf_list[-max_count:]
    
    async def generate_continuously(self, scenario: str, interval_seconds: float = 10.0):
        while True:
            try:
                self.get_scenario_signals(scenario)
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in continuous signal generation: {e}")
                await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    scheduler = SignalStreamScheduler()
    
    # Test g10_flood scenario load
    sigs_g10 = scheduler.get_scenario_signals("g10_flood")
    assert len(sigs_g10) == 7
    assert len(scheduler.buffer) == 7
    
    # Test false_positive load
    sigs_fp = scheduler.get_scenario_signals("false_positive")
    assert len(sigs_fp) == 9
    assert len(scheduler.buffer) == 16 # 7 + 9
    
    print("ALL GENERATOR TESTS PASSED")
