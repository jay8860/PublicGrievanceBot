import axios from 'axios';

// In production, we are served by the same backend, so use relative path
export const API_BASE = import.meta.env.PROD ? '/api' : (import.meta.env.VITE_API_URL || 'http://localhost:8000/api');

const api = axios.create({ baseURL: API_BASE });

// Attach the JWT (obtained from POST /api/login) to every outgoing request.
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// If the token is missing/expired, the backend returns 401 - clear it and
// bounce back to the Login screen (App.jsx's auth guard).
// Paths that must NEVER trigger that logout:
// - 'login'  : a wrong password also returns 401, and Login.jsx shows the error.
// - 'health' : public no-auth probe App.jsx uses to detect the temporary
//              BYPASS_LOGIN; a plain <img>/401 here must not log the user out.
const AUTH_EXEMPT_PATHS = ['login', 'health'];

// Event App.jsx listens to for "the API rejected our token, show Login again".
export const AUTH_EXPIRED_EVENT = 'auth:expired';

// A request the browser itself cancelled - page navigation, tab close, a
// refresh (F5) while a slow endpoint such as /api/works is still running - is
// reported by axios as ECONNABORTED / "Request aborted". That is NOT an API
// failure: there is no error.response, nothing reached the server, and the
// answer is simply lost. Callers use this helper to stay quiet instead of
// logging it as a data error.
export const isAbortedRequest = (error) =>
    !!error && !error.response && (
        error.code === 'ECONNABORTED' ||
        error.code === 'ERR_CANCELED' ||
        error.name === 'CanceledError' ||
        error.message === 'Request aborted'
    );

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const path = error.config && error.config.url ? error.config.url.replace(/^\//, '') : '';
        const isAuthExempt = AUTH_EXEMPT_PATHS.includes(path);
        // Only a real 401 *response* means the token is bad. A network error or
        // an aborted request has no `response` and must not log the user out.
        if (error.response && error.response.status === 401 && !isAuthExempt) {
            localStorage.removeItem('token');
            // This used to be window.location.reload(). Because the dashboard
            // fires /stats, /filters, /officers and /works at the same time,
            // the reload killed the requests still in flight and the browser
            // aborted them - each one then showed up in the console as
            // "Data Error / Request aborted" (ECONNABORTED). App.jsx now
            // listens for this event and renders the Login screen in-place.
            window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
        }
        return Promise.reject(error);
    }
);

export default api;
