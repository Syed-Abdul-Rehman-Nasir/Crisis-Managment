import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from models import CrisisSchema, AllocationPlan, StakeholderMessages, CrisisType, SeverityLevel
except ImportError:
    from ..models import CrisisSchema, AllocationPlan, StakeholderMessages, CrisisType, SeverityLevel

from gemini_settings import generate_json, is_gemini_enabled

class StakeholderMessageGenerator:
    """
    Generates tailored warning messages and advisories for multiple stakeholders.
    Uses Gemini API if available, else falls back to local rules-based templates.
    """
    
    def __init__(self):
        self.gemini_available = is_gemini_enabled()

    def _generate_from_templates(self, crisis: CrisisSchema, allocation: AllocationPlan) -> StakeholderMessages:
        location = crisis.location
        severity = crisis.severity.value
        c_type = crisis.type.value
        
        # Determine minimum ETA
        etas = [a.eta_minutes for a in allocation.allocations if a.eta_minutes > 0]
        eta = str(min(etas)) if etas else "15"
        
        # Urdu templates
        urdu_templates = {
            CrisisType.FLOOD: "خبردار! {location} میں شدید سیلاب کی صورتحال ہے۔ تمام مکینوں کو فوری طور پر محفوظ مقامات پر منتقل ہوجائیں۔ امدادی ٹیمیں {eta} منٹ میں پہنچ رہی ہیں۔",
            CrisisType.HEATWAVE: "گرمی کی لہر وارننگ: {location} میں درجہ حرارت خطرناک حد تک بڑھ گیا ہے۔ گھروں میں رہیں، پانی پیتے رہیں، طبی امداد کے لیے 1122 پر کال کریں۔",
            CrisisType.FIRE: "آگ لگنے کی اطلاع: {location} میں آگ لگی ہے۔ فوری طور پر علاقہ خالی کریں۔ فائر بریگیڈ راستے میں ہے۔",
            CrisisType.ACCIDENT: "ٹریفک حادثہ: {location} پر سنگین حادثہ ہوا ہے۔ متبادل راستہ استعمال کریں۔ ہنگامی ٹیمیں موجود ہیں۔",
            CrisisType.INFRASTRUCTURE: "انفراسٹرکچر مسئلہ: {location} میں {crisis_type} کی وجہ سے خدمات متاثر ہیں۔ مرمتی کام جاری ہے۔",
            CrisisType.UNKNOWN: "ہنگامی صورتحال: {location} میں غیر متوقع صورتحال ہے۔ محتاط رہیں اور حکومتی ہدایات پر عمل کریں۔"
        }
        
        c_key = crisis.type if crisis.type in urdu_templates else CrisisType.UNKNOWN
        public_urdu = urdu_templates[c_key].format(location=location, eta=eta, crisis_type=c_type)
        
        # Other templates
        public_english = (
            f"Advisory for {location}: {c_type} incident reported with {severity} severity. "
            f"Please avoid the area. Deployed response units are en route with ETAs around {eta} minutes."
        )
        
        hospital_request = (
            f"Hospital Dispatch Request: Incident type {c_type.upper()} confirmed at {location}. "
            f"Estimate response timeline: {eta} mins. Please prepare trauma units, emergency wards, and medical outreach."
        )
        
        utility_alert = (
            f"Utility Alert: NDMA advises immediate inspection of grids, pipelines, and drainage lines near {location} "
            f"due to {c_type} incident. Coordinate with local field response units."
        )
        
        transport_rerouting = (
            f"Traffic Rerouting Plan: Active {c_type} at {location} has restricted lanes. "
            f"Alternate routes are recommended. Travel delays estimated at {eta} minutes."
        )
        
        media_briefing = (
            f"NDMA Media Briefing: A {severity} severity {c_type} incident was detected at {location}. "
            f"Active emergency coordination is underway. Deployed resources: {len(allocation.allocations)} units. "
            f"First responder arrivals starting within {eta} minutes."
        )
        
        return StakeholderMessages.model_validate({
            "crisis_id": crisis.crisis_id,
            "public_urdu": public_urdu,
            "public_english": public_english,
            "hospital_request": hospital_request,
            "utility_alert": utility_alert,
            "transport_rerouting": transport_rerouting,
            "media_briefing": media_briefing,
            "generated_at": datetime.utcnow().isoformat()
        })

    def _generate_with_gemini(self, crisis: CrisisSchema, allocation: AllocationPlan) -> StakeholderMessages:
        if not self.gemini_available:
            return self._generate_from_templates(crisis, allocation)
            
        location = crisis.location
        c_type = crisis.type.value
        severity = crisis.severity.value
        
        resources_str = ", ".join([f"{a.unit_name} (ETA: {a.eta_minutes}m)" for a in allocation.allocations])
        
        system_prompt = "You are the emergency communications officer for Pakistan's NDMA."
        
        user_prompt = f"""
        Generate localized stakeholder warning messages for the following crisis:
        - Type: {c_type}
        - Location: {location}
        - Severity: {severity}
        - Resources allocated: {resources_str or 'None'}

        Your output must be a valid JSON object with EXACTLY the following keys:
        - "public_urdu": Actionable alert in Urdu script (Unicode). Do NOT use Roman Urdu (do not write Urdu words using English letters).
        - "public_english": Concise warning and instruction in English.
        - "hospital_request": Urgent standby coordination instruction for local hospitals (e.g. PIMS Islamabad, Mayo Hospital Lahore, Jinnah Karachi depending on the city of the location).
        - "utility_alert": Task order for utility companies (WASA, WAPDA, CDA, K-Electric etc.) depending on location.
        - "transport_rerouting": Traffic advisory detailing alternate roads to use instead of roads near the incident.
        - "media_briefing": Objective fact summary for press updates.

        Return ONLY the raw JSON block without markdown formatting or surrounding backticks.
        """
        
        parsed_json = generate_json(f"{system_prompt}\n\n{user_prompt}", temperature=0.3)
        if not parsed_json:
            return self._generate_from_templates(crisis, allocation)

        required_keys = [
            "public_urdu", "public_english", "hospital_request",
            "utility_alert", "transport_rerouting", "media_briefing",
        ]
        for k in required_keys:
            if k not in parsed_json or not parsed_json[k]:
                return self._generate_from_templates(crisis, allocation)

        return StakeholderMessages.model_validate({
            "crisis_id": crisis.crisis_id,
            **parsed_json,
            "generated_at": datetime.utcnow().isoformat(),
        })

    def generate_all(self, crisis: CrisisSchema, allocation: AllocationPlan, use_gemini: bool = True) -> StakeholderMessages:
        if use_gemini and is_gemini_enabled() and self.gemini_available:
            return self._generate_with_gemini(crisis, allocation)
        return self._generate_from_templates(crisis, allocation)


if __name__ == "__main__":
    import sys
    from unittest.mock import MagicMock, patch
    
    # Mock google module in sys.modules to prevent ModuleNotFoundError during patching
    mock_g = MagicMock()
    sys.modules["google"] = mock_g
    sys.modules["google.generativeai"] = mock_g
    sys.modules["google.generativeai.GenerativeModel"] = MagicMock()
    
    # Add parent dir to path so absolute imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from models.crisis_models import CrisisSchema, CrisisType, SeverityLevel
    from models.resource_models import AllocationPlan, AllocationItem, ResourceType

    crisis = CrisisSchema(
        crisis_id="c-test",
        type=CrisisType.FLOOD,
        severity=SeverityLevel.HIGH,
        confidence=0.88,
        affected_radius_km=2.5,
        location="G-10, Islamabad",
        latitude=33.6938,
        longitude=73.0652,
        explanation="Flooding G-10"
    )
    
    plan = AllocationPlan(
        crisis_id="c-test",
        allocations=[
            AllocationItem(resource_id="r1", resource_type=ResourceType.RESCUE_TEAM, unit_name="Rescue Team Alpha", destination="G-10, Islamabad", eta_minutes=12, reasoning="relevance")
        ],
        allocation_reasoning="reasoning"
    )

    generator = StakeholderMessageGenerator()

    # 1. Test template path (use_gemini=False)
    msgs_template = generator.generate_all(crisis, plan, use_gemini=False)
    assert msgs_template.crisis_id == "c-test"
    assert "G-10" in msgs_template.public_urdu
    # verify native Urdu Unicode is outputted
    assert "شدید سیلاب" in msgs_template.public_urdu

    # 2. Test Gemini mocked path
    mock_response_json = {
        "public_urdu": "جی ٹین اسلام آباد میں سیلاب ہے۔",
        "public_english": "Flooding alert in G-10 Islamabad.",
        "hospital_request": "PIMS hospital standby.",
        "utility_alert": "CDA inspect water lines.",
        "transport_rerouting": "Reroute from G-10 to Margalla road.",
        "media_briefing": "Urban flooding in Islamabad G-10."
    }
    
    with patch("google.generativeai.GenerativeModel") as mock_model_class:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value.text = json.dumps(mock_response_json)
        mock_model_class.return_value = mock_instance
        
        # Configure generator to use mocked class
        generator_mocked = StakeholderMessageGenerator()
        generator_mocked.gemini_available = True
        generator_mocked.model = mock_instance
        
        msgs_gemini = generator_mocked.generate_all(crisis, plan, use_gemini=True)
        assert msgs_gemini.crisis_id == "c-test"
        assert msgs_gemini.public_urdu == mock_response_json["public_urdu"]
        assert msgs_gemini.public_english == mock_response_json["public_english"]

    print("ALL STAKEHOLDER TESTS PASSED")
