import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { LayoutDashboard, Map as MapIcon, Table as TableIcon, Filter, RefreshCcw, LogOut } from 'lucide-react';
import L from 'leaflet';
import Login from './Login'; // Import Login

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
    const [token, setToken] = useState(localStorage.getItem('token') || null); // Auth State
    const [view, setView] = useState('map'); // map, list
    const [stats, setStats] = useState(null);
    const [filters, setFilters] = useState({});
    const [works, setWorks] = useState([]);
    const [locations, setLocations] = useState([]);
    const [officerMap, setOfficerMap] = useState({});

    // --- EFFECTS ---

    // 1. Initial Auth Check
    useEffect(() => {
        const storedToken = localStorage.getItem('token');
        if (storedToken) setToken(storedToken);
    }, []);

    // 2. Fetch Data on Auth or Load
    useEffect(() => {
        if (token) {
            fetchStats();
            fetchFilters();
            fetchData();
            fetchOfficerMap();
        }
    }, [token]);

    // ... (Filter Effect) ...

    const fetchOfficerMap = async () => {
        try {
            const res = await axios.get(`${API_BASE}/officers`);
            setOfficerMap(res.data);
        } catch (e) { console.error("Officer Map Error", e); }
    };

    // ... (Other fetch functions) ...

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

   // ... (Render) ...

                                    <thead className="text-xs text-gray-700 uppercase bg-gray-50 border-b">
                                        <tr>
                                            <th className="px-6 py-3">ID</th>
                                            <th className="px-6 py-3">Date</th>
                                            <th className="px-6 py-3">Category</th>
                                            <th className="px-6 py-3">Assigned To</th>
                                            <th className="px-6 py-3">Status</th>
                                            <th className="px-6 py-3">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {works.map((row, i) => {
                                            const escalation = getEscalationStatus(row);
                                            return (
                                                <tr key={i} className={`bg-white border-b hover:bg-gray-50 ${escalation?.isEscalated ? 'bg-red-50' : ''}`}>
                                                    <td className="px-6 py-4 font-medium text-gray-900">{row['Ticket ID']}</td>
                                                    <td className="px-6 py-4">{row['Timestamp']}</td>
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
                                </table >
        { works.length === 0 && <div className="p-8 text-center text-gray-400">No records found.</div> }
                            </div >
                        )
}

{/* MAP VIEW */ }
{
    (view === 'map') && (
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
    )
}
                    </>
                )
}

            </main >
        </div >
    )
}

export default App
