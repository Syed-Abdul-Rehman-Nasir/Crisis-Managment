from typing import List, Dict, Any, Optional
from uuid import uuid4

try:
    from models import Resource, ResourceType, ResourceStatus
except ImportError:
    from ..models import Resource, ResourceType, ResourceStatus

class ResourceInventory:
    """
    Manages the pre-populated list of 47 rescue and response assets across Pakistan.
    """

    ISLAMABAD_ZONES = ["G-10", "G-11", "I-8", "F-6", "F-7", "F-8", "E-7", "Rawal Town", "Sector H", "Blue Area", "Islamabad"]
    LAHORE_ZONES = ["Gulberg", "Model Town", "DHA Phase 4", "Johar Town", "Cantt", "Walled City", "Lahore"]
    KARACHI_ZONES = ["Clifton", "PECHS", "Korangi", "Saddar", "Karachi"]

    # Pre-calculated travel time matrix (minutes)
    TRAVEL_TIMES = {
        "Islamabad": {
            ("G-10", "G-10"): 0, ("G-10", "G-11"): 8, ("G-10", "F-8"): 12, ("G-10", "I-8"): 15, 
            ("G-10", "F-6"): 20, ("G-10", "F-7"): 18, ("G-10", "E-7"): 16, ("G-10", "Rawal Town"): 25, 
            ("G-10", "Sector H"): 22, ("G-10", "Blue Area"): 15,
            ("G-11", "G-10"): 8, ("F-8", "G-10"): 12, ("I-8", "G-10"): 15, ("F-6", "G-10"): 20,
            ("F-7", "G-10"): 18, ("E-7", "G-10"): 16, ("Rawal Town", "G-10"): 25, ("Sector H", "G-10"): 22,
            ("Blue Area", "G-10"): 15
        },
        "Lahore": {
            ("Gulberg", "Gulberg"): 0, ("Gulberg", "Model Town"): 15, ("Gulberg", "DHA Phase 4"): 20,
            ("Gulberg", "Johar Town"): 18, ("Gulberg", "Cantt"): 12, ("Gulberg", "Walled City"): 25,
            ("Model Town", "Gulberg"): 15, ("DHA Phase 4", "Gulberg"): 20, ("Johar Town", "Gulberg"): 18,
            ("Cantt", "Gulberg"): 12, ("Walled City", "Gulberg"): 25
        },
        "Karachi": {
            ("Clifton", "Clifton"): 0, ("Clifton", "PECHS"): 22, ("Clifton", "Korangi"): 30, ("Clifton", "Saddar"): 12,
            ("PECHS", "Clifton"): 22, ("Korangi", "Clifton"): 30, ("Saddar", "Clifton"): 12
        }
    }

    def __init__(self):
        self.resources: List[Resource] = []
        self._initialize_inventory()

    def _get_city(self, zone: str) -> str:
        zone_clean = zone.split(",")[0].strip()
        if any(z == zone_clean for z in self.ISLAMABAD_ZONES):
            return "Islamabad"
        if any(z == zone_clean for z in self.LAHORE_ZONES):
            return "Lahore"
        if any(z == zone_clean for z in self.KARACHI_ZONES):
            return "Karachi"
        
        # Fallbacks for prefix matching
        if any(z in zone_clean for z in self.ISLAMABAD_ZONES):
            return "Islamabad"
        if any(z in zone_clean for z in self.LAHORE_ZONES):
            return "Lahore"
        if any(z in zone_clean for z in self.KARACHI_ZONES):
            return "Karachi"
        return "Islamabad"

    def _initialize_inventory(self) -> None:
        self.resources.clear()
        
        # 10 Ambulances: Rescue-1 to Rescue-5 in Islamabad, 6-8 in Lahore, 9-10 in Karachi
        for i in range(1, 11):
            if i <= 5:
                city, loc, lat, lng = "Islamabad", "G-10", 33.6938, 73.0652
            elif i <= 8:
                city, loc, lat, lng = "Lahore", "Gulberg", 31.5117, 74.3468
            else:
                city, loc, lat, lng = "Karachi", "Clifton", 24.8138, 67.0336
            self.resources.append(Resource(
                resource_id=f"AMB-{i}", type=ResourceType.AMBULANCE, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=f"Rescue-{i}", capacity=2
            ))
            
        # 15 Police Units: Traffic Police Alpha to Omega distributed 5 per city
        police_names = [
            "Traffic Police Alpha", "Traffic Police Beta", "Traffic Police Gamma", "Traffic Police Delta", "Traffic Police Epsilon",
            "Traffic Police Zeta", "Traffic Police Eta", "Traffic Police Theta", "Traffic Police Iota", "Traffic Police Kappa",
            "Traffic Police Lambda", "Traffic Police Mu", "Traffic Police Nu", "Traffic Police Xi", "Traffic Police Omicron"
        ]
        for i, name in enumerate(police_names):
            if i < 5:
                city, loc, lat, lng = "Islamabad", "F-8", 33.7128, 73.0425
            elif i < 10:
                city, loc, lat, lng = "Lahore", "Model Town", 31.4806, 74.3214
            else:
                city, loc, lat, lng = "Karachi", "Saddar", 24.8607, 67.0011
            self.resources.append(Resource(
                resource_id=f"POL-{i+1}", type=ResourceType.POLICE_UNIT, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=name, capacity=4
            ))

        # 8 Rescue Teams: Rescue Team Alpha through Theta
        rescue_names = ["Rescue Team Alpha", "Rescue Team Beta", "Rescue Team Gamma", "Rescue Team Delta",
                        "Rescue Team Epsilon", "Rescue Team Zeta", "Rescue Team Eta", "Rescue Team Theta"]
        for i, name in enumerate(rescue_names):
            if i < 4:
                city, loc, lat, lng = "Islamabad", "I-8", 33.6682, 73.0783
            elif i < 6:
                city, loc, lat, lng = "Lahore", "Cantt", 31.5204, 74.3587
            else:
                city, loc, lat, lng = "Karachi", "PECHS", 24.8683, 67.0712
            self.resources.append(Resource(
                resource_id=f"RES-{i+1}", type=ResourceType.RESCUE_TEAM, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=name, capacity=8
            ))

        # 5 Water Tankers: Tanker-1 to Tanker-5
        for i in range(1, 6):
            if i <= 3:
                city, loc, lat, lng = "Islamabad", "Sector H", 33.6425, 73.0236
            else:
                city, loc, lat, lng = "Lahore", "Johar Town", 31.4697, 74.2728
            self.resources.append(Resource(
                resource_id=f"TNK-{i}", type=ResourceType.WATER_TANKER, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=f"Tanker-{i}", capacity=1000
            ))

        # 6 Medical Outreach Units: MOU-1 to MOU-6
        for i in range(1, 7):
            if i <= 2:
                city, loc, lat, lng = "Islamabad", "Blue Area", 33.7112, 73.0564
            elif i <= 4:
                city, loc, lat, lng = "Lahore", "Gulberg", 31.5117, 74.3468
            else:
                city, loc, lat, lng = "Karachi", "PECHS", 24.8683, 67.0712
            self.resources.append(Resource(
                resource_id=f"MOU-{i}", type=ResourceType.MEDICAL_OUTREACH, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=f"MOU-{i}", capacity=10
            ))

        # 3 Fire Engines: Red, Blue, Green
        fire_colors = [("Red", "Islamabad", "F-7", 33.7215, 73.0562),
                       ("Blue", "Lahore", "Walled City", 31.5815, 74.3168),
                       ("Green", "Karachi", "Korangi", 24.8215, 67.1268)]
        for name, city, loc, lat, lng in fire_colors:
            self.resources.append(Resource(
                resource_id=f"FIR-{name.upper()}", type=ResourceType.FIRE_ENGINE, status=ResourceStatus.AVAILABLE,
                current_location=loc, current_lat=lat, current_lng=lng, unit_name=f"Fire Engine {name}", capacity=500
            ))

    def get_available(self, resource_type: Optional[ResourceType] = None) -> List[Resource]:
        res = [r for r in self.resources if r.status == ResourceStatus.AVAILABLE]
        if resource_type:
            res = [r for r in res if r.type == resource_type]
        return res

    def mark_deployed(self, resource_ids: List[str], destination: str) -> None:
        for r in self.resources:
            if r.resource_id in resource_ids:
                r.status = ResourceStatus.DEPLOYED
                r.current_location = destination

    def mark_available(self, resource_ids: List[str], location: str) -> None:
        for r in self.resources:
            if r.resource_id in resource_ids:
                r.status = ResourceStatus.AVAILABLE
                r.current_location = location

    def get_eta(self, resource: Resource, destination_zone: str, dest_lat: Optional[float] = None, dest_lng: Optional[float] = None) -> int:
        src_clean = resource.current_location.split(",")[0].strip()
        dest_clean = destination_zone.split(",")[0].strip()
        
        src_city = self._get_city(src_clean)
        dest_city = self._get_city(dest_clean)
        
        # 1. Try to get from travel time matrix first if same city
        if src_city == dest_city:
            city_times = self.TRAVEL_TIMES.get(src_city, {})
            # Check bidirectional direct mapping
            if (src_clean, dest_clean) in city_times:
                return city_times[(src_clean, dest_clean)]
            if (dest_clean, src_clean) in city_times:
                return city_times[(dest_clean, src_clean)]
            if src_clean == dest_clean:
                return 5

        # 2. Haversine distance fallback if coordinates are available
        if dest_lat is not None and dest_lng is not None and resource.current_lat is not None and resource.current_lng is not None:
            import math
            lat1, lon1 = math.radians(resource.current_lat), math.radians(resource.current_lng)
            lat2, lon2 = math.radians(dest_lat), math.radians(dest_lng)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
            c = 2 * math.asin(math.sqrt(a))
            r = 6371  # Radius of earth in kilometers
            distance_km = c * r
            
            calculated_eta = int(distance_km * 2.0) + 5
            return calculated_eta

        # 3. Fallbacks if no coordinates or no match
        if src_city != dest_city:
            return 180  # Different city default
            
        return 25  # Same city unknown zone default

    def get_inventory_summary(self) -> Dict[str, Any]:
        summary = {}
        for r_type in ResourceType:
            typed_resources = [r for r in self.resources if r.type == r_type]
            available = sum(1 for r in typed_resources if r.status == ResourceStatus.AVAILABLE)
            deployed = sum(1 for r in typed_resources if r.status == ResourceStatus.DEPLOYED)
            summary[r_type.value] = {
                "total": len(typed_resources),
                "available": available,
                "deployed": deployed
            }
        summary["total_count"] = len(self.resources)
        summary["available_count"] = sum(1 for r in self.resources if r.status == ResourceStatus.AVAILABLE)
        summary["deployed_count"] = sum(1 for r in self.resources if r.status == ResourceStatus.DEPLOYED)
        return summary

    def reset_all(self) -> None:
        self._initialize_inventory()
