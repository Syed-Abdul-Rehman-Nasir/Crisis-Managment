import React, { useState, useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import { 
  AlertTriangle, Activity, Shield, 
  RefreshCw, ActivitySquare
} from 'lucide-react';
import { isOfflineMode, getOfflineScenario, formatComparisonForUi } from './offline/offlineDemo';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const OFFLINE = isOfflineMode();

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [scenario, setScenario] = useState('idle'); 
  const [currentStep, setCurrentStep] = useState(0);
  const [demoRunning, setDemoRunning] = useState(false);
  const [time, setTime] = useState(new Date().toLocaleTimeString());
  
  const [crises, setCrises] = useState([]);
  const [allocations, setAllocations] = useState({});
  const [allocationReasoning, setAllocationReasoning] = useState('');
  const [actions, setActions] = useState([]);
  const [traceLogs, setTraceLogs] = useState([]);
  const [visibleLogs, setVisibleLogs] = useState([]);
  const [liveSignals, setLiveSignals] = useState([]);
  const [comparisonData, setComparisonData] = useState(null);
  const [backendStatus, setBackendStatus] = useState(OFFLINE ? 'LOCAL DEMO' : 'Checking...');
  
  const mapRef = useRef(null);
  const mapInstance = useRef(null);
  const markersGroup = useRef(null);
  const ws = useRef(null);
  const demoIntervalRef = useRef(null);
  const signalStreamRef = useRef(null);
  const offlineSignalsRef = useRef(getOfflineScenario('idle').signals);

  const safeStr = (val, fallback = '') => {
    if (val == null) return fallback;
    if (typeof val === 'string') return val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    try {
      return JSON.stringify(val);
    } catch {
      return fallback;
    }
  };

  const normalizeCrises = useCallback((list) => {
    if (!Array.isArray(list)) return [];
    return list.map((c, i) => ({
      id: c.id || c.crisis_id || `crisis-${i}`,
      type: safeStr(c.type, 'Unknown'),
      location: safeStr(c.location, 'Unknown'),
      severity: safeStr(c.severity, '—'),
      confidence: typeof c.confidence === 'number' ? c.confidence : parseFloat(c.confidence) || 0,
      time_detected: safeStr(c.time_detected, '—'),
      latitude: c.latitude != null ? Number(c.latitude) : null,
      longitude: c.longitude != null ? Number(c.longitude) : null,
    }));
  }, []);

  const pushOfflineSignal = useCallback(() => {
    const pool = offlineSignalsRef.current;
    if (!pool?.length) return;
    const sig = pool[Math.floor(Math.random() * pool.length)];
    setLiveSignals(prev => [{ ...sig, _ts: Date.now() }, ...prev].slice(0, 50));
  }, []);

  const startOfflineSignalStream = useCallback((signals) => {
    if (signals?.length) offlineSignalsRef.current = signals;
    if (signalStreamRef.current) clearInterval(signalStreamRef.current);
    pushOfflineSignal();
    signalStreamRef.current = setInterval(pushOfflineSignal, 4000);
  }, [pushOfflineSignal]);

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (OFFLINE) {
      setBackendStatus('LOCAL DEMO');
      startOfflineSignalStream(getOfflineScenario('idle').signals);
      return () => {
        if (signalStreamRef.current) clearInterval(signalStreamRef.current);
      };
    }

    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`);
        if (res.ok) {
          setBackendStatus('ONLINE');
        } else {
          setBackendStatus('COLD START (Waking up...)');
        }
      } catch {
        setBackendStatus('OFFLINE');
      }
    };
    checkHealth();
    const healthTimer = setInterval(checkHealth, 30000);
    return () => clearInterval(healthTimer);
  }, [startOfflineSignalStream]);

  useEffect(() => {
    if (OFFLINE) return undefined;

    const wsUrl = BACKEND_URL.replace('http', 'ws') + '/ws/signals';
    ws.current = new WebSocket(wsUrl);
    ws.current.onmessage = (event) => {
      try {
        const signal = JSON.parse(event.data);
        if (!signal || typeof signal !== 'object') return;
        setLiveSignals(prev => [signal, ...prev].slice(0, 50));
      } catch {
        // Ignore malformed websocket payloads
      }
    };
    return () => ws.current?.close();
  }, []);

  useEffect(() => {
    if (activeTab === 'map' && mapRef.current) {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
      const map = L.map(mapRef.current).setView([33.6844, 73.0479], 12);
      mapInstance.current = map;
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19
      }).addTo(map);
      markersGroup.current = L.layerGroup().addTo(map);
      updateMapElements();
    }
    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [activeTab, crises, scenario]);

  const updateMapElements = () => {
    if (!mapInstance.current || !markersGroup.current) return;
    markersGroup.current.clearLayers();

    const redIcon = L.divIcon({
      html: `<div class="relative flex items-center justify-center">
        <span class="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-red-500 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-4 w-4 bg-red-600 border border-white"></span>
      </div>`,
      className: 'custom-div-icon',
      iconSize: [32, 32],
      iconAnchor: [16, 16]
    });

    const bounds = [];
    crises.forEach(c => {
      const lat = Number(c.latitude);
      const lng = Number(c.longitude);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      bounds.push([lat, lng]);
      L.marker([lat, lng], { icon: redIcon })
        .addTo(markersGroup.current)
        .bindPopup(`<div class="p-2 text-slate-900"><b>${c.type}</b><br/>${c.location}</div>`);
    });

    if (bounds.length === 1) {
      mapInstance.current.setView(bounds[0], 12);
    } else if (bounds.length > 1) {
      mapInstance.current.fitBounds(bounds, { padding: [48, 48], maxZoom: 11 });
    }
  };

  const fetchAPI = async (endpoint, options = {}) => {
    if (OFFLINE) return null;
    try {
      const res = await fetch(`${BACKEND_URL}${endpoint}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      return await res.json();
    } catch (e) {
      console.warn("Backend API not reachable.", e);
      return null;
    }
  };

  const applyOfflineScenarioResults = (pack) => {
    setCrises(normalizeCrises(pack.crises));
    setAllocations(pack.allocation || {});
    setAllocationReasoning(pack.reasoning || '');
    setActions(pack.actions || []);
    setComparisonData(formatComparisonForUi(pack.comparison));
    startOfflineSignalStream(pack.signals);
  };

  const loadComparison = async (scenarioKey) => {
    if (OFFLINE) {
      const pack = getOfflineScenario(scenarioKey || scenario);
      setComparisonData(formatComparisonForUi(pack.comparison));
      return;
    }
    const data = await fetchAPI('/api/alerts/comparison');
    if (!data) return;
    if (data.baseline?.latency_ms != null) {
      setComparisonData(data);
      return;
    }
    setComparisonData({
      baseline: {
        latency_ms: safeStr(data.detection_time?.baseline, '—').replace(/[^\d]/g, '') || '—',
        detection: safeStr(data.accuracy?.baseline, 'Keyword match'),
      },
      ciro: {
        latency_ms: safeStr(data.detection_time?.ciro, '—').replace(/[^\d]/g, '') || '—',
        detection: safeStr(data.accuracy?.ciro, 'CIRO fusion'),
      },
      impact_summary: safeStr(data.overall?.improvement || data.explainability?.improvement, 'Validated automated response'),
    });
  };

  const runDemoModeOffline = (targetScenario) => {
    const pack = getOfflineScenario(targetScenario);
    const logs = (pack.logs || []).filter(Boolean);
    setTraceLogs(logs);
    startOfflineSignalStream(pack.signals);

    let step = 0;
    demoIntervalRef.current = setInterval(() => {
      if (step < logs.length) {
        const entry = logs[step];
        setVisibleLogs(prev => [
          ...prev,
          {
            ...entry,
            step: entry.step ?? step + 1,
            agent: safeStr(entry.agent, 'Agent'),
            message: safeStr(entry.message, entry.reasoning || ''),
          },
        ]);
        setCurrentStep(step + 1);
        step++;
        return;
      }

      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
      applyOfflineScenarioResults(pack);
      setActiveTab('dashboard');
      loadComparison(targetScenario);
      setDemoRunning(false);
    }, 1500);
  };

  const runDemoMode = async (targetScenario) => {
    if (demoRunning) return;
    if (demoIntervalRef.current) {
      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
    }

    setDemoRunning(true);
    setScenario(targetScenario);
    setCurrentStep(0);
    setActiveTab('trace');
    setVisibleLogs([]);

    if (OFFLINE) {
      runDemoModeOffline(targetScenario);
      return;
    }

    await fetchAPI('/api/trigger', {
      method: 'POST',
      body: JSON.stringify({ scenario: targetScenario })
    });

    const traceRes = await fetchAPI('/api/trace');
    const logs = (traceRes?.logs || []).filter(Boolean);
    setTraceLogs(logs);

    let step = 0;
    demoIntervalRef.current = setInterval(async () => {
      if (step < logs.length) {
        const entry = logs[step];
        setVisibleLogs(prev => [
          ...prev,
          {
            ...entry,
            step: entry.step ?? step + 1,
            agent: safeStr(entry.agent, 'Agent'),
            message: safeStr(entry.message, entry.reasoning || ''),
          },
        ]);
        setCurrentStep(step + 1);
        step++;
        return;
      }

      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;

      try {
        const detectRes = await fetchAPI('/api/crisis/detect', { method: 'POST' });
        const allocRes = await fetchAPI('/api/resources/allocate', { method: 'POST' });

        if (detectRes?.crises) setCrises(normalizeCrises(detectRes.crises));
        if (allocRes) {
          setAllocations(allocRes.allocation && typeof allocRes.allocation === 'object' ? allocRes.allocation : {});
          const reasoning = allocRes.reasoning ?? allocRes.allocation_reasoning ?? '';
          setAllocationReasoning(safeStr(reasoning));
        }
      } catch (e) {
        console.warn('Demo sync failed', e);
      }

      setActiveTab('dashboard');
      loadComparison();
      setDemoRunning(false);
    }, 1500);
  };

  const handleReset = async () => {
    if (demoIntervalRef.current) {
      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
    }
    setDemoRunning(false);
    setCurrentStep(0);
    setVisibleLogs([]);
    setScenario('idle');
    setCrises([]);
    setAllocations({});
    setAllocationReasoning('');
    setActions([]);
    setLiveSignals([]);
    setComparisonData(null);

    if (OFFLINE) {
      startOfflineSignalStream(getOfflineScenario('idle').signals);
      return;
    }
    await fetchAPI('/api/trigger', { method: 'POST', body: JSON.stringify({ scenario: 'idle' }) });
  };

  const statusClass =
    backendStatus === 'ONLINE' || backendStatus === 'LOCAL DEMO'
      ? 'text-emerald-500 bg-emerald-950/30 border-emerald-900/50'
      : backendStatus === 'OFFLINE'
        ? 'text-red-500 bg-red-950/30 border-red-900/50'
        : 'text-yellow-500 bg-yellow-950/30 border-yellow-900/50 animate-pulse';

  return (
    <div className="min-h-screen bg-black text-gray-200 flex flex-col font-mono text-sm">
      
      <header className="bg-slate-950 border-b border-emerald-900/50 flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-4">
          <ActivitySquare className="h-8 w-8 text-emerald-500 animate-pulse" />
          <div>
            <h1 className="text-xl font-bold text-emerald-400 tracking-widest">TACTICAL OPS CENTER</h1>
            <p className="text-xs text-emerald-700">
              CIRO PLATFORM{OFFLINE ? ' — OFFLINE MOBILE DEMO' : ' — GEMINI SECURE COMM'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className={`font-bold px-3 py-1 rounded border ${statusClass}`}>
            {time} | SYSTEM {backendStatus}
          </div>
          <button onClick={handleReset} className="p-2 border border-emerald-900/50 rounded hover:bg-emerald-900/20 text-emerald-500">
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className="bg-slate-900/50 border-b border-emerald-900/30 px-6 py-2 flex flex-wrap gap-2">
        <span className="text-emerald-700 py-1 mr-2 text-xs">SCENARIOS:</span>
        <button onClick={() => runDemoMode('g10_flood')} disabled={demoRunning} className="px-3 py-1 bg-blue-950 text-blue-400 border border-blue-900 hover:bg-blue-900 rounded text-xs">FLOOD</button>
        <button onClick={() => runDemoMode('false_positive')} disabled={demoRunning} className="px-3 py-1 bg-yellow-950 text-yellow-400 border border-yellow-900 hover:bg-yellow-900 rounded text-xs">FALSE POSITIVE</button>
        <button onClick={() => runDemoMode('balochistan_earthquake')} disabled={demoRunning} className="px-3 py-1 bg-red-950 text-red-400 border border-red-900 hover:bg-red-900 rounded text-xs">EARTHQUAKE</button>
        <button onClick={() => runDemoMode('karachi_industrial_fire')} disabled={demoRunning} className="px-3 py-1 bg-orange-950 text-orange-400 border border-orange-900 hover:bg-orange-900 rounded text-xs">INDUSTRIAL FIRE</button>
        <button onClick={() => runDemoMode('lahore_smog_health_crisis')} disabled={demoRunning} className="px-3 py-1 bg-purple-950 text-purple-400 border border-purple-900 hover:bg-purple-900 rounded text-xs">SMOG EMERGENCY</button>
      </div>

      <div className="flex gap-1 px-6 py-3 border-b border-emerald-900/20">
        {['dashboard', 'map', 'trace', 'before_after'].map(tab => (
          <button 
            key={tab} 
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 uppercase text-xs tracking-wider border-b-2 ${activeTab === tab ? 'border-emerald-500 text-emerald-400 bg-emerald-950/20' : 'border-transparent text-gray-500 hover:text-emerald-300'}`}
          >
            {tab.replace('_', ' ')}
          </button>
        ))}
      </div>

      <main className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-4 gap-6 overflow-hidden">
        
        <div className="col-span-1 lg:col-span-3 overflow-y-auto">
          {activeTab === 'dashboard' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-900/40 border border-emerald-900/30 p-4 rounded-lg">
                <h2 className="text-red-500 border-b border-red-900/30 pb-2 mb-4 font-bold tracking-widest flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" /> ACTIVE THREATS
                </h2>
                {crises.length === 0 ? <span className="text-gray-600 text-xs">NO ACTIVE THREATS</span> : crises.map((c, i) => (
                  <div key={i} className="mb-4 bg-slate-950 p-3 border-l-2 border-red-500">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-red-400 font-bold">{safeStr(c.type).toUpperCase()} - {safeStr(c.location)}</span>
                      <span className="text-xs bg-red-950 text-red-300 px-2 rounded">{safeStr(c.severity)}</span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded mt-2">
                      <div className="bg-red-500 h-1.5 rounded" style={{width: `${Math.min(100, (c.confidence || 0) * 100)}%`}}></div>
                    </div>
                    <div className="text-[10px] text-gray-500 mt-1">CONFIDENCE: {(c.confidence * 100).toFixed(1)}% | TIME: {c.time_detected}</div>
                  </div>
                ))}
              </div>

              <div className="bg-slate-900/40 border border-emerald-900/30 p-4 rounded-lg">
                <h2 className="text-blue-400 border-b border-blue-900/30 pb-2 mb-4 font-bold tracking-widest flex items-center gap-2">
                  <Shield className="h-4 w-4" /> DEPLOYMENT TRACE
                </h2>
                {Object.entries(allocations).map(([loc, force], i) => (
                  <div key={i} className="mb-3 text-xs">
                    <span className="text-gray-400">{loc}:</span> <span className="text-blue-300">{force}</span>
                  </div>
                ))}
                {allocationReasoning && (
                  <div className="mt-4 p-3 bg-slate-950 border border-slate-800 text-xs text-gray-400 whitespace-pre-wrap">
                    <span className="text-emerald-500 mb-1 block">{'>> GEMINI REASONING LOG:'}</span>
                    {allocationReasoning}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'map' && (
            <div className="h-[600px] border border-emerald-900/50 rounded-lg overflow-hidden">
              <div id="map" ref={mapRef} className="h-full w-full" />
            </div>
          )}

          {activeTab === 'trace' && (
            <div className="bg-slate-900/40 border border-emerald-900/30 p-4 rounded-lg h-[600px] overflow-y-auto font-mono text-xs">
              <h2 className="text-emerald-500 border-b border-emerald-900/30 pb-2 mb-4 font-bold tracking-widest">AGENT EXECUTION TRACE</h2>
              {visibleLogs.length === 0 && (
                <p className="text-gray-600">Run a scenario to see agent trace…</p>
              )}
              {visibleLogs.map((log, i) => (
                <div key={`${log.step}-${log.agent}-${i}`} className="mb-4 border-l-2 border-emerald-500 pl-3">
                  <span className="text-emerald-700">[{log.step ?? i + 1}] </span>
                  <span className="text-emerald-400 font-bold">{safeStr(log.agent, 'Agent')}</span>
                  <div className="mt-1 text-gray-300 whitespace-pre-wrap break-words">{safeStr(log.message)}</div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'before_after' && comparisonData && (
            <div className="grid grid-cols-2 gap-6 h-[600px]">
              <div className="bg-slate-900/40 border border-gray-800 p-6 rounded-lg text-xs">
                <h3 className="text-gray-500 font-bold mb-4 border-b border-gray-800 pb-2 tracking-widest">BASELINE (KEYWORD SCRIPT)</h3>
                <div className="mb-4">
                  <div className="text-gray-600 mb-1">Latency:</div>
                  <div className="text-xl text-gray-300">{safeStr(comparisonData.baseline?.latency_ms, '—')} ms</div>
                </div>
                <div className="mb-4">
                  <div className="text-gray-600 mb-1">Detection Result:</div>
                  <div className="text-gray-400 p-2 bg-slate-950 border border-gray-800">{safeStr(comparisonData.baseline?.detection)}</div>
                </div>
              </div>
              
              <div className="bg-emerald-950/20 border border-emerald-900/50 p-6 rounded-lg text-xs">
                <h3 className="text-emerald-500 font-bold mb-4 border-b border-emerald-900/50 pb-2 tracking-widest">GEMINI AI FUSION</h3>
                <div className="mb-4">
                  <div className="text-emerald-700 mb-1">Latency:</div>
                  <div className="text-xl text-emerald-400">{safeStr(comparisonData.ciro?.latency_ms, '—')} ms</div>
                </div>
                <div className="mb-4">
                  <div className="text-emerald-700 mb-1">Detection Result:</div>
                  <div className="text-emerald-300 p-2 bg-emerald-950 border border-emerald-900/30">{safeStr(comparisonData.ciro?.detection)}</div>
                </div>
                <div className="mb-4">
                  <div className="text-emerald-700 mb-1">Impact:</div>
                  <div className="text-white p-2 bg-emerald-900/30 border border-emerald-500">{safeStr(comparisonData.impact_summary)}</div>
                </div>
              </div>
            </div>
          )}
          {activeTab === 'before_after' && !comparisonData && (
            <div className="text-gray-500 p-4">Run a scenario to generate comparison data.</div>
          )}
        </div>

        <div className="col-span-1 border-l border-emerald-900/30 pl-6 flex flex-col">
          <h2 className="text-emerald-500 border-b border-emerald-900/30 pb-2 mb-4 font-bold tracking-widest flex items-center gap-2">
            <Activity className="h-4 w-4 animate-pulse" /> LIVE STREAM
          </h2>
          <div className="flex-1 overflow-y-auto pr-2 space-y-3">
            {liveSignals.length === 0 ? <span className="text-xs text-gray-600">AWAITING TELEMETRY...</span> : liveSignals.map((sig, i) => (
              <div key={sig._ts ?? i} className="text-[10px] p-2 bg-slate-900/50 border border-emerald-900/20 rounded">
                <div className="text-emerald-700 flex justify-between mb-1">
                  <span>{safeStr(sig.source_type, 'signal').toUpperCase()}</span>
                  <span>{safeStr(sig.location)}</span>
                </div>
                <div className="text-gray-300 break-words">{safeStr(sig.content)}</div>
              </div>
            ))}
          </div>
        </div>
        
      </main>
    </div>
  );
}

export default App;
