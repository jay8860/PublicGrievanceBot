import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { LayoutDashboard, Map as MapIcon, Table as TableIcon, Filter, RefreshCcw } from 'lucide-react';
import L from 'leaflet';

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

// --- CONSTANTS ---
// In production, we are served by the same backend, so use relative path
const API_BASE = import.meta.env.PROD ? '/api' : (import.meta.env.VITE_API_URL || 'http://localhost:8000/api');

function App() {
    const [view, setView] = useState('dashboard'); // dashboard, map, list
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

    // Initial Fetch
    useEffect(() => {
        fetchStats();
        fetchFilters();
        fetchData(); // Works & Locations
    }, []);

    // Re-fetch when filters change
    useEffect(() => {
        fetchData();
    }, [selectedCategory, selectedStatus, selectedSeverity, search]);

    const fetchStats = async () => {
        try {
            const res = await axios.get(`${API_BASE}/stats`);
            setStats(res.data);
        } catch (e) { console.error("Stats Error", e); }
    };

    const fetchFilters = async () => {
        try {
            const res = await axios.get(`${API_BASE}/filters`);
            setFilters(res.data);
        } catch (e) { console.error("Filters Error", e); }
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

            const worksRes = await axios.get(`${API_BASE}/works`, { params });
            setWorks(worksRes.data);

            // For map, we use the same filtered dataset for consistency
            // Or fetch from /locations if we want strict geo only. 
            // Let's us worksRes data as it has all info
            setLocations(worksRes.data.filter(w => w.Lat && w.Long));

        } catch (e) { console.error("Data Error", e); }
        setLoading(false);
    };

    // --- COMPONENTS ---

    const StatCard = ({ title, value, color }) => (
        <div className={`p-4 rounded-xl shadow-sm border border-gray-100 bg-white`}>
            <p className="text-gray-500 text-sm font-medium">{title}</p>
            <h3 className={`text-2xl font-bold mt-1`} style={{ color: color }}>{value}</h3>
        </div>
    );

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
                            onClick={() => setView('dashboard')}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${view === 'dashboard' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-100'}`}
                        >
                            Overview
                        </button>
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
                        <button onClick={fetchData} className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg">
                            <RefreshCcw size={18} />
                        </button>
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
                                            <th className="px-6 py-3">ID</th>
                                            <th className="px-6 py-3">Date</th>
                                            <th className="px-6 py-3">Category</th>
                                            <th className="px-6 py-3">Description</th>
                                            <th className="px-6 py-3">Severity</th>
                                            <th className="px-6 py-3">Status</th>
                                            <th className="px-6 py-3">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {works.map((row, i) => (
                                            <tr key={i} className="bg-white border-b hover:bg-gray-50">
                                                <td className="px-6 py-4 font-medium text-gray-900">{row['Ticket ID']}</td>
                                                <td className="px-6 py-4">{row['Timestamp']}</td>
                                                <td className="px-6 py-4">
                                                    <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-0.5 rounded border border-blue-400">
                                                        {row['Category']}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 max-w-xs truncate" title={row['Description']}>{row['Description']}</td>
                                                <td className="px-6 py-4">
                                                    <span className={`text-xs font-medium px-2.5 py-0.5 rounded border ${row['Severity'] === 'High' ? 'bg-red-100 text-red-800 border-red-400' :
                                                        'bg-yellow-100 text-yellow-800 border-yellow-400'
                                                        }`}>
                                                        {row['Severity']}
                                                    </span>
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
                                        ))}
                                    </tbody>
                                </table>
                                {works.length === 0 && <div className="p-8 text-center text-gray-400">No records found.</div>}
                            </div>
                        )}

                        {/* MAP VIEW */}
                        {(view === 'map' || view === 'dashboard') && (
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

export default App
