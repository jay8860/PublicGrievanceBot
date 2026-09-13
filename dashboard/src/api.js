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
// bounce back to the Login screen (App.jsx's `if (!token) return <Login ... />` gate).
// Skip this for the login request itself: a wrong password also returns 401,
// and that should show "Invalid credentials" in Login.jsx, not reload the page.
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const isLoginRequest = error.config && error.config.url && error.config.url.replace(/^\//, '') === 'login';
        if (error.response && error.response.status === 401 && !isLoginRequest) {
            localStorage.removeItem('token');
            window.location.reload();
        }
        return Promise.reject(error);
    }
);

export default api;
