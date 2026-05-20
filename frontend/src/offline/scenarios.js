/** Bundled demo payloads — mirrors backend compat_trigger / detect / allocate outputs */

export const GEO = {
  g10: { latitude: 33.6938, longitude: 73.0652 },
  gulberg_lahore: { latitude: 31.5204, longitude: 74.3587 },
  karachi: { latitude: 24.8607, longitude: 67.0011 },
  quetta: { latitude: 30.1798, longitude: 66.9750 },
  lahore: { latitude: 31.5204, longitude: 74.3587 },
};

const BADGE = {
  SignalFusionAgent: 'bg-indigo-900 text-indigo-200 border-indigo-700',
  ClassificationAgent: 'bg-red-900 text-red-200 border-red-700',
  ResourceAllocationAgent: 'bg-yellow-900 text-yellow-200 border-yellow-700',
  ResponsePlanningAgent: 'bg-green-900 text-green-200 border-green-700',
  StakeholderCommunicationAgent: 'bg-blue-900 text-blue-200 border-blue-700',
  VerificationAgent: 'bg-purple-900 text-purple-200 border-purple-700',
};

function traceStep(step, agent, message) {
  return {
    step,
    agent,
    badge_color: BADGE[agent] || 'bg-gray-900 text-gray-200 border-gray-700',
    message,
  };
}

const COMPARISON_DEFAULT = {
  detection_time: { baseline: '4.2s', ciro: '28ms' },
  accuracy: {
    baseline: 'Keyword match — possible flood (unverified)',
    ciro: 'Multi-source fusion — urban flooding confirmed',
  },
  overall: { improvement: 'Validated automated response with explainable allocation' },
};

const FLOOD_TRACE = [
  traceStep(1, 'SignalFusionAgent', '[FUSE_SIGNALS] Fusing 7 signal sources. Credibility-weighted batch ready. High spatial correlation on G-10 coordinates.'),
  traceStep(2, 'ClassificationAgent', '[CLASSIFY] Crisis type FLOOD at G-10 Islamabad. Confidence 0.89. Affected radius 2.4 km.'),
  traceStep(3, 'ResourceAllocationAgent', '[ALLOCATION UPDATE] Deploy rescue and drainage assets to G-10 corridor. Tradeoff: maintain Gulberg heatwave coverage with minimal medical unit.\nNote: Allocation uses severity-weighted inventory across zones.'),
  traceStep(4, 'ResponsePlanningAgent', '[PLAN_RESPONSE] Reroute Ring Road traffic, stage PIMS trauma standby, activate water pumps on Main Boulevard.'),
  traceStep(5, 'StakeholderCommunicationAgent', '[BROADCAST] Urdu/English public advisory issued. Utilities and transport authorities notified.'),
];

const FALSE_POSITIVE_TRACE = [
  ...FLOOD_TRACE,
  traceStep(6, 'VerificationAgent', 'Contradiction score: 0.71 (above threshold 0.6). RETRACTING flood alert. Updating classification to: Infrastructure - Water Main Burst. Public retraction broadcast.'),
];

const STANDARD_TRACE = (location, type, confidence) => [
  traceStep(1, 'SignalFusionAgent', `[FUSE_SIGNALS] Fusing scenario signals for ${location}. Credibility scoring complete.`),
  traceStep(2, 'ClassificationAgent', `[CLASSIFY] Crisis ${type} at ${location}. Confidence ${confidence}.`),
  traceStep(3, 'ResourceAllocationAgent', '[ALLOCATION UPDATE] Standard response force dispatched per severity and zone inventory.'),
  traceStep(4, 'ResponsePlanningAgent', '[PLAN_RESPONSE] Field actions and cordons planned for primary incident zone.'),
  traceStep(5, 'StakeholderCommunicationAgent', '[BROADCAST] Stakeholder messages generated for public, hospitals, and utilities.'),
];

function signal(source_type, location, content, lat, lng) {
  return {
    source_type,
    location,
    content,
    latitude: lat,
    longitude: lng,
    recency_minutes: 1,
  };
}

export const OFFLINE_SCENARIOS = {
  idle: {
    logs: [],
    crises: [],
    allocation: {},
    reasoning: '',
    actions: [],
    comparison: null,
    signals: [
      signal('WEATHER_API', 'Islamabad, Pakistan', 'Standby: monitoring Islamabad sector.', GEO.g10.latitude, GEO.g10.longitude),
    ],
  },

  g10_flood: {
    logs: FLOOD_TRACE,
    crises: [
      {
        id: 'g10_flood',
        type: 'Urban Flooding',
        location: 'G-10 Islamabad',
        severity: 'HIGH',
        confidence: 0.89,
        time_detected: 'Just now',
        radius_km: 2.4,
        ...GEO.g10,
      },
      {
        id: 'gulberg_heatwave',
        type: 'Heatwave',
        location: 'Gulberg, Lahore',
        severity: 'MEDIUM',
        confidence: 0.74,
        time_detected: '10 mins ago',
        radius_km: 5.0,
        ...GEO.gulberg_lahore,
      },
    ],
    allocation: {
      'G-10 Islamabad (Flooding)': '3 Rescue Teams + 2 Police Units + 2 Water Tankers/Pumps',
      'Gulberg, Lahore (Heatwave)': '1 Medical Outreach Unit',
    },
    reasoning:
      'Priority to G-10 flood due to HIGH severity and rescue demand. Gulberg heatwave retains medical outreach. Inventory travel times within 12 min for G-10 assets.',
    actions: [
      { action: 'Deploy rescue teams to G-10/3 and Ring Road interchange', status: 'IN_PROGRESS' },
      { action: 'Activate water pumps on Main Boulevard', status: 'IN_PROGRESS' },
      { action: 'Issue public flood advisory (Urdu + English)', status: 'COMPLETED' },
      { action: 'Stage PIMS trauma standby', status: 'IN_PROGRESS' },
    ],
    comparison: COMPARISON_DEFAULT,
    signals: [
      signal('SOCIAL_MEDIA', 'G-10, Islamabad', 'G-10 street flooded, water rising fast #Islamabad', GEO.g10.latitude, GEO.g10.longitude),
      signal('WEATHER_API', 'G-10, Islamabad', 'Heavy rainfall 87mm last hour — thunderstorm alert', GEO.g10.latitude, GEO.g10.longitude),
      signal('GOOGLE_MAPS', 'G-10, Islamabad', 'Road closure: severe waterlogging G-10 Main Boulevard', GEO.g10.latitude, GEO.g10.longitude),
      signal('EMERGENCY_CALL', 'G-10, Islamabad', 'NDMA hotline spike: 18 calls/min', GEO.g10.latitude, GEO.g10.longitude),
      signal('SOCIAL_MEDIA', 'Gulberg, Lahore', 'Extreme heat 43°C — heat stroke reports', GEO.gulberg_lahore.latitude, GEO.gulberg_lahore.longitude),
    ],
  },

  false_positive: {
    logs: FALSE_POSITIVE_TRACE,
    crises: [
      {
        id: 'g10_water_main',
        type: 'Infrastructure - Water Main Burst',
        location: 'G-10 Islamabad',
        severity: 'MEDIUM',
        confidence: 0.92,
        time_detected: '1 mins ago',
        radius_km: 0.5,
        ...GEO.g10,
      },
      {
        id: 'gulberg_heatwave',
        type: 'Heatwave',
        location: 'Gulberg, Lahore',
        severity: 'MEDIUM',
        confidence: 0.74,
        time_detected: '15 mins ago',
        radius_km: 5.0,
        ...GEO.gulberg_lahore,
      },
    ],
    allocation: {
      'G-10 Islamabad (Water Main)': '2 Utility Repair Teams + 1 Police Unit (Rescue teams recalled)',
      'Gulberg, Lahore (Heatwave)': '1 Medical Outreach Unit',
    },
    reasoning:
      'VerificationAgent: authoritative CDA signal contradicts flood classification. Retracted public flood alert; reclassified as water main infrastructure event.',
    actions: [
      { action: 'Alert WAPDA & CDA to repair main water line at 7th Avenue', status: 'COMPLETED' },
      { action: 'Retract G-10 Urban Flooding Public Advisory', status: 'COMPLETED' },
      { action: 'Reopen Margalla Road normal flow', status: 'IN_PROGRESS' },
      { action: 'Cancel PIMS Hospital trauma standby request', status: 'COMPLETED' },
    ],
    comparison: {
      ...COMPARISON_DEFAULT,
      accuracy: {
        baseline: 'Keyword match — flood (false stay)',
        ciro: 'Contradiction detected — reclassified water main burst',
      },
      overall: { improvement: 'False positive retracted in under 60s with audit trail' },
    },
    signals: [
      signal('EMERGENCY_CALL', 'G-10, Islamabad', 'CDA: water main burst on 7th Avenue G-10, not natural flood', GEO.g10.latitude, GEO.g10.longitude),
      signal('SOCIAL_MEDIA', 'G-10, Islamabad', 'Water cleared quickly after pipe burst — not monsoon flooding', GEO.g10.latitude, GEO.g10.longitude),
    ],
  },

  balochistan_earthquake: {
    logs: STANDARD_TRACE('Quetta, Balochistan', 'EARTHQUAKE', 0.91),
    crises: [
      {
        id: 'balochistan_earthquake',
        type: 'Earthquake',
        location: 'Quetta, Balochistan',
        severity: 'CRITICAL',
        confidence: 0.91,
        time_detected: 'Just now',
        radius_km: 15.0,
        ...GEO.quetta,
      },
    ],
    allocation: {
      'Quetta, Balochistan (Earthquake)': 'Standard Response Force',
    },
    reasoning: 'Seismic social + weather corroboration. Mass casualty protocols and search teams prioritized for Quetta basin.',
    actions: [
      { action: 'Activate regional search & rescue coordination', status: 'IN_PROGRESS' },
      { action: 'Open field hospitals — trauma surge planning', status: 'IN_PROGRESS' },
    ],
    comparison: {
      ...COMPARISON_DEFAULT,
      accuracy: { baseline: 'Keyword — shake reported', ciro: 'Earthquake crisis confirmed — multi-source' },
    },
    signals: [
      signal('SOCIAL_MEDIA', 'Quetta', 'Did anyone else feel that? Whole house shaking! #earthquake', GEO.quetta.latitude, GEO.quetta.longitude),
      signal('WEATHER_API', 'Quetta', 'Seismic weather watch — aftershock risk elevated', GEO.quetta.latitude, GEO.quetta.longitude),
    ],
  },

  karachi_industrial_fire: {
    logs: STANDARD_TRACE('SITE Area, Karachi', 'INDUSTRIAL_FIRE', 0.88),
    crises: [
      {
        id: 'karachi_industrial_fire',
        type: 'Industrial Fire',
        location: 'SITE Area, Karachi',
        severity: 'HIGH',
        confidence: 0.88,
        time_detected: 'Just now',
        radius_km: 3.0,
        ...GEO.karachi,
      },
    ],
    allocation: {
      'SITE Area, Karachi (Industrial Fire)': 'Standard Response Force',
    },
    reasoning: 'Industrial fire with toxic smoke reports. HAZMAT-aware units and downwind evacuation messaging required.',
    actions: [
      { action: 'HAZMAT team dispatch to SITE industrial zone', status: 'IN_PROGRESS' },
      { action: 'Toxic smoke shelter-in-place advisory', status: 'COMPLETED' },
    ],
    comparison: {
      ...COMPARISON_DEFAULT,
      accuracy: { baseline: 'Keyword — fire mentioned', ciro: 'Industrial fire — SITE Karachi confirmed' },
    },
    signals: [
      signal('SOCIAL_MEDIA', 'SITE Area, Karachi', 'Massive fire in SITE industrial area. Toxic smoke everywhere.', GEO.karachi.latitude, GEO.karachi.longitude),
      signal('GOOGLE_MAPS', 'SITE Area, Karachi', 'Road closures and congestion near industrial sector', GEO.karachi.latitude, GEO.karachi.longitude),
    ],
  },

  lahore_smog_health_crisis: {
    logs: STANDARD_TRACE('Lahore', 'HEALTH / SMOG', 0.85),
    crises: [
      {
        id: 'lahore_smog_health_crisis',
        type: 'Health Crisis',
        location: 'Lahore',
        severity: 'HIGH',
        confidence: 0.85,
        time_detected: 'Just now',
        radius_km: 20.0,
        ...GEO.lahore,
      },
    ],
    allocation: {
      'Lahore (Health Crisis)': 'Standard Response Force',
    },
    reasoning: 'AQI emergency and pediatric respiratory spike. School closure advisory and hospital surge capacity recommended.',
    actions: [
      { action: 'Issue AQI health emergency — schools closure advisory', status: 'COMPLETED' },
      { action: 'Scale pulmonary units at major Lahore hospitals', status: 'IN_PROGRESS' },
    ],
    comparison: {
      ...COMPARISON_DEFAULT,
      accuracy: { baseline: 'Keyword — smog/air', ciro: 'Health crisis — AQI 600+ fusion confirmed' },
    },
    signals: [
      signal('SOCIAL_MEDIA', 'Lahore', 'AQI is 600+ today. Kids getting sick. Close the schools!', GEO.lahore.latitude, GEO.lahore.longitude),
      signal('EMERGENCY_CALL', 'Lahore', 'Emergency hotline spike: 15 calls/min respiratory distress', GEO.lahore.latitude, GEO.lahore.longitude),
    ],
  },
};
