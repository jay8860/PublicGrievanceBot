import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { LayoutDashboard, Map as MapIcon, Table as TableIcon, Filter, RefreshCcw, LogOut } from 'lucide-react';
import L from 'leaflet';
import Login from './Login'; // Import Login
import api, { AUTH_EXPIRED_EVENT, isAbortedRequest, isAuthFailure } from './api';
import AuthImage from './AuthImage';

// Fix Leaflet Icon
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// TEMPORARY LOGIN BYPASS (mirrors BYPASS_LOGIN in auth.py): placeholder
// "token" that only satisfies the local auth guard below while the backend
// has the login bypass on. It is never used as a real JWT - when the bypass
// is enabled the API accepts requests without one anyway.
const BYPASS_TOKEN = 'bypass-login';

function App() {
    const [token, setToken] = useState(localStorage.getItem('token') || null); // Auth State
    // Whether the API reported that its temporary login bypass is on.
    const [bypassLogin, setBypassLogin] = useState(false);
    // Hold off choosing between Login / Dashboard until /health answered.
    const [authChecked, setAuthChecked] = useState(false);
    const [view, setView] = useState('map'); // map, list
    const [stats, setStats] = useState(null);
    const [filters, setFilters] = useState({});
    const [works, setWorks] = useState([]);
    const [locations, setLocations] = useState([]);
    const [loading, setLoading] = useState(false);

    // Filter States
    const [selectedCategory, setSelectedCategory] = useState('');
    const [selectedStatus, setSelectedStatus] = useState('');
    const [selectedSeverity, setSelectedSeverity] = useState('');
    const [search, setSearch] = useState('');

    // Officer Map
    const [officerMap, setOfficerMap] = useState({});

    // True when the API rejected our stored token (see AUTH_EXPIRED_EVENT
    // below) so the Login screen can explain why the dashboard vanished.
    const [sessionExpired, setSessionExpired] = useState(false);

    // --- EFFECTS ---

    // While the temporary backend bypass is on, this placeholder satisfies
    // the auth guard so the Login screen stays hidden.
    const effectiveToken = token || (bypassLogin ? BYPASS_TOKEN : null);

    // 1. Initial Auth Check
    useEffect(() => {
        const storedToken = localStorage.getItem('token');
        if (storedToken) setToken(storedToken);

        // /api/health is public and reports whether the API has BYPASS_LOGIN
        // on. If it is unreachable (or still protected), we silently fall
        // back to the normal Login screen - that case is expected and must
        // not show an error here.
        api.get('/health')
            .then((res) => {
                if (res.data && res.data.bypass_login) setBypassLogin(true);
            })
            .catch(() => { })
            .finally(() => setAuthChecked(true));
    }, []);

    // 2. React to a rejected token without reloading the page.
    // api.js fires AUTH_EXPIRED_EVENT when a protected call comes back 401
    // (missing/expired JWT). Clearing the token here makes the auth guard below
    // render <Login /> again, and `sessionExpired` explains why the dashboard
    // disappeared. A full window.location.reload() used to do this job, but the
    // reload aborted the dashboard requests that were still in flight, so the
    // console filled up with "Data Error / Request aborted".
    useEffect(() => {
        const onAuthExpired = () => {
            setToken(null);
            setSessionExpired(true);
        };
        window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
        return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
    }, []);

    // 3. Fetch Data on Auth or Load
    useEffect(() => {
        if (effectiveToken) {
            fetchStats();
            fetchFilters();
            fetchOfficerMap();
        }
    }, [effectiveToken]);

    // Re-fetch when filters change (and once on load / after login).
    // The token guard matters: without it this effect also fired /works while
    // the Login screen was up, the API answered 401, and the old reload-on-401
    // interceptor turned that into an endless page-reload loop.
    useEffect(() => {
        if (effectiveToken) fetchData();
    }, [effectiveToken, selectedCategory, selectedStatus, selectedSeverity, search]);

    const fetchStats = async () => {
        try {
            const res = await api.get('/stats');
            setStats(res.data);
        } catch (e) {
            // Aborted requests (page reload / navigation) and 401s (already
            // handled by api.js -> Login screen) are not data errors.
            if (!isAbortedRequest(e) && !isAuthFailure(e)) console.error("Stats Error", e);
        }
    };

    const fetchFilters = async () => {
        try {
            const res = await api.get('/filters');
            setFilters(res.data);
        } catch (e) {
            if (!isAbortedRequest(e) && !isAuthFailure(e)) console.error("Filters Error", e);
        }
    };

    const fetchOfficerMap = async () => {
        try {
            const res = await api.get('/officers');
            setOfficerMap(res.data);
        } catch (e) {
            if (!isAbortedRequest(e) && !isAuthFailure(e)) console.error("Officer Map Error", e);
        }
    };

    const fetchData = async () => {
        setLoading(true);
        try {
            const params = {
                category: selectedCategory || undefined,
                status: selectedStatus || undefined,
                severity: selectedSeverity || undefined,
                search: search || undefined
            };

            const worksRes = await api.get('/works', { params });
            setWorks(worksRes.data);

            // For map, we use the same filtered dataset for consistency
            setLocations(worksRes.data.filter(w => w.Lat && w.Long));

        } catch (e) {
            // Aborted requests (reload/navigation while Sheets was still
            // answering) and 401s are not data errors - see api.js helpers.
            if (!isAbortedRequest(e) && !isAuthFailure(e)) console.error("Data Error", e);
        }
        setLoading(false);
    };

    // --- HELPERS ---
    const handleLogout = () => {
        localStorage.removeItem('token');
        setToken(null);
    };

    // Helper to calculate Escalation
    const getEscalationStatus = (ticket) => {
        if (ticket.Status === 'Resolved') return null;

        const category = ticket.Category;
        const config = officerMap[category];
        if (!config) return null;

        const created = new Date(ticket.Timestamp);
        const now = new Date();
        const diffHours = (now - created) / (1000 * 60 * 60);

        if (diffHours > config.SLA) {
            return {
                isEscalated: true,
                message: `Escalated to ${config.L2} (SLA: ${config.SLA}h)`
            };
        } else {
            return {
                isEscalated: false,
                message: `With ${config.L1} (${Math.round(config.SLA - diffHours)}h left)`
            };
        }
    };

    // --- COMPONENTS ---

    const StatCard = ({ title, value, color }) => (
        <div className={`p-4 rounded-xl shadow-sm border border-gray-100 bg-white`}>
            <p className="text-gray-500 text-sm font-medium">{title}</p>
            <h3 className={`text-2xl font-bold mt-1`} style={{ color: color }}>{value}</h3>
        </div>
    );

    // --- AUTH GUARD ---
    // Unchanged behaviour: no token -> Login screen. The <Login /> component
    // and the whole auth flow are untouched. The only difference is that when
    // the API runs with BYPASS_LOGIN=true, /health reports it and
    // `effectiveToken` satisfies this guard, so the dashboard opens directly.
    // Turn the bypass off and this screen comes back on its own.
    if (!authChecked) {
        return (
            <div className="min-h-screen flex items-center justify-center text-gray-400">
                Loading...
            </div>
        );
    }
    if (!effectiveToken) {
        return (
            <Login
                notice={sessionExpired ? 'Your session expired. Please sign in again.' : ''}
                onLogin={(newToken) => {
                    setSessionExpired(false);
                    setToken(newToken);
                }}
            />
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 font-sans text-gray-800">

            {/* HEADER */}
            <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
                <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="bg-blue-600 text-white p-2 rounded-lg">
                            <LayoutDashboard size={20} />
                        </div>
                        <h1 className="text-xl font-bold text-gray-900">Grievance Monitor</h1>
                    </div>

                    <div className="flex gap-2">
                        <button
                            onClick={() => setView('map')}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'map' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
                        >
                            <div className="flex items-center gap-2"><MapIcon size={16} /> Map</div>
                        </button>
                        <button
                            onClick={() => setView('list')}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'list' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
                        >
                            <div className="flex items-center gap-2"><TableIcon size={16} /> List</div>
                        </button>
                        <button onClick={fetchData} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg" title="Refresh Data">
                            <RefreshCcw size={18} />
                        </button>
                        <div className="h-6 w-px bg-gray-300 mx-1 self-center"></div>
                        {/* Temporary: visible while the API has BYPASS_LOGIN on. */}
                        {bypassLogin && !token && (
                            <span
                                className="self-center text-xs font-semibold px-2 py-1 rounded bg-amber-100 text-amber-800 border border-amber-300"
                                title="BYPASS_LOGIN is enabled on the API - the login screen is temporarily hidden. Set BYPASS_LOGIN=false and restart the API to bring it back."
                            >
                                LOGIN BYPASSED
                            </span>
                        )}
                        {token && (
                            <button onClick={handleLogout} className="p-2 text-red-500 hover:bg-red-50 rounded-lg" title="Logout">
                                <LogOut size={18} />
                            </button>
                        )}
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 py-8">

                {/* STATS ROW */}
                {stats && (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                        <StatCard title="Total Grievances" value={stats.total} color="#1f2937" />
                        <StatCard title="Open Issues" value={stats.open} color="#dc2626" />
                        <StatCard title="Resolved" value={stats.resolved} color="#16a34a" />
                        <StatCard title="Sanitation Issues" value={stats.breakdown['Sanitation'] || 0} color="#ea580c" />
                    </div>
                )}

                {/* FILTERS TOOLBAR */}
                <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-6 flex flex-wrap gap-4 items-center">
                    <div className="flex items-center gap-2 text-gray-500 mr-2">
                        <Filter size={18} />
                        <span className="text-sm font-medium">Filters:</span>
                    </div>

                    <select
                        className="bg-gray-50 border border-gray-300 text-sm rounded-lg p-2.5 focus:ring-blue-500 focus:border-blue-500"
                        value={selectedCategory} onChange={e => setSelectedCategory(e.target.value)}
                    >
                        <option value="">All Categories</option>
                        {filters.categories?.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>

                    <select
                        className="bg-gray-50 border border-gray-300 text-sm rounded-lg p-2.5 focus:ring-blue-500 focus:border-blue-500"
                        value={selectedStatus} onChange={e => setSelectedStatus(e.target.value)}
                    >
                        <option value="">All Statuses</option>
                        {filters.statuses?.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>

                    <select
                        className="bg-gray-50 border border-gray-300 text-sm rounded-lg p-2.5 focus:ring-blue-500 focus:border-blue-500"
                        value={selectedSeverity} onChange={e => setSelectedSeverity(e.target.value)}
                    >
                        <option value="">All Severities</option>
                        {filters.severities?.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>

                    <input
                        type="text"
                        placeholder="Search ID or Description..."
                        className="bg-gray-50 border border-gray-300 text-sm rounded-lg p-2.5 ml-auto w-64"
                        value={search} onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {/* VIEWS */}
                {loading ? (
                    <div className="text-center py-20 text-gray-500">Loading data...</div>
                ) : (
                    <>
                        {/* LIST VIEW */}
                        {view === 'list' && (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                                <table className="w-full text-sm text-left text-gray-500">
                                    <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b">
                                        <tr>
                                            <th className="px-6 py-3">Photo</th>
                                            <th className="px-6 py-3">Resolution</th>
                                            <th className="px-6 py-3">ID</th>
                                            <th className="px-6 py-3">Date</th>
                                            <th className="px-6 py-3">Category</th>
                                            <th className="px-6 py-3">Assigned To</th>
                                            <th className="px-6 py-3">Rating</th>
                                            <th className="px-6 py-3">Chat ID</th>
                                            <th className="px-6 py-3">Status</th>
                                            <th className="px-6 py-3">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {works.map((row, i) => {
                                            const escalation = getEscalationStatus(row);
                                            return (
                                                <tr key={i} className={`bg-white border-b hover:bg-gray-50 ${escalation?.isEscalated ? 'bg-red-50' : ''}`}>
                                                    <td className="px-6 py-4">
                                                        {row['PhotoID'] && row['PhotoID'] !== 'N/A' ? (
                                                            <div className="h-10 w-10">
                                                                <AuthImage
                                                                    src={`/image/${row['PhotoID']}`}
                                                                    alt="Thumb"
                                                                    className="h-full w-full rounded object-cover border border-gray-200"
                                                                />
                                                            </div>
                                                        ) : (
                                                            <div className="h-10 w-10 bg-gray-100 rounded flex items-center justify-center text-gray-300">
                                                                <span className="text-xs">No Img</span>
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        {row['After File ID'] && row['After File ID'] !== 'N/A' && row['After File ID'] !== '' ? (
                                                            <div className="h-10 w-10">
                                                                <AuthImage
                                                                    src={`/image/${row['After File ID']}`}
                                                                    alt="Resolved"
                                                                    className="h-full w-full rounded object-cover border border-green-200 ring-1 ring-green-400"
                                                                />
                                                            </div>
                                                        ) : (
                                                            <span className="text-gray-300 text-xs">-</span>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 font-medium text-gray-900">{row['Ticket ID']}</td>
                                                    <td className="px-6 py-4 text-xs text-gray-500">{new Date(row['Timestamp']).toLocaleDateString()}</td>
                                                    <td className="px-6 py-4">
                                                        <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded border border-blue-400">
                                                            {row['Category']}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="text-sm font-semibold">{row['Officer'] || 'Unassigned'}</div>
                                                        {escalation && (
                                                            <div className={`text-xs mt-1 ${escalation.isEscalated ? 'text-red-600 font-bold' : 'text-gray-500'}`}>
                                                                {escalation.message}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td className="px-6 py-4 text-yellow-500 font-bold">
                                                        {row['User Rating'] ? `⭐ ${row['User Rating']}` : '-'}
                                                    </td>
                                                    <td className="px-6 py-4 text-xs text-gray-500">
                                                        {row['Chat ID'] || row['citizen_chat_id'] || '-'}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <span className={`text-xs font-medium px-2.5 py-0.5 rounded border ${row['Status'] === 'Resolved' ? 'bg-green-100 text-green-800 border-green-400' :
                                                            'bg-gray-100 text-gray-800 border-gray-400'
                                                            }`}>
                                                            {row['Status']}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <a href={row['Map Link']} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline mr-2">Map</a>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                                {works.length === 0 && <div className="p-8 text-center text-gray-400">No records found.</div>}
                            </div>
                        )}

                        {/* MAP VIEW */}
                        {(view === 'map') && (
                            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden h-[600px] relative">
                                <MapContainer center={[18.89, 81.35]} zoom={10} style={{ height: '100%', width: '100%' }}>
                                    <TileLayer
                                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                    />
                                    {locations.map((loc, i) => (
                                        <Marker key={i} position={[loc.Lat, loc.Long]}>
                                            <Popup>
                                                <div className="p-2">
                                                    <h4 className="font-bold text-sm">{loc['Category']} - {loc['Ticket ID']}</h4>
                                                    <p className="text-xs text-gray-600 mt-1">{loc['Description']}</p>
                                                    <div className="mt-2 text-xs">
                                                        <span className="font-semibold">Status:</span> {loc['Status']}
                                                    </div>
                                                </div>
                                            </Popup>
                                        </Marker>
                                    ))}
                                </MapContainer>
                            </div>
                        )}
                    </>
                )}

            </main>
        </div>
    )
}

export default App;
