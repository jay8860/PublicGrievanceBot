import React, { useState } from 'react';
import api, { API_BASE } from './api';
import { Button, Field, Input } from './components/controls';

const Login = ({ onLogin, notice = '' }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await api.post('/login', { username, password });
      if (res.data.access_token) {
        localStorage.setItem('token', res.data.access_token);
        onLogin(res.data.access_token);
      }
    } catch (err) {
      const status = err.response && err.response.status;
      const detail = err.response && err.response.data && err.response.data.detail;
      if (status === 401) setError(detail || 'Incorrect username or password');
      else if (status) setError(`Sign-in failed (HTTP ${status}). ${detail || ''}`.trim());
      else setError(`Cannot reach the API at ${API_BASE}.`);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-5">
          <p className="font-serif text-[20px] leading-tight text-slate-900">Grievance Register</p>
          <p className="text-[11px] text-slate-500">District administration</p>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="px-5 py-3.5 border-b border-slate-200">
            <h1 className="text-[14px] font-semibold text-slate-900">Sign in</h1>
            <p className="text-[11px] text-slate-500 mt-0.5">Administrator access</p>
          </div>

          <form onSubmit={handleLogin} className="px-5 py-4 space-y-3">
            {notice && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[11px] text-amber-800">
                {notice}
              </div>
            )}
            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-[11px] text-red-800">
                {error}
              </div>
            )}

            <Field label="Username">
              <Input value={username} autoComplete="username" autoFocus
                onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="Password">
              <Input type="password" value={password} autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)} />
            </Field>

            <Button type="submit" loading={loading} className="w-full" size="lg">
              {loading ? 'Signing in' : 'Sign in'}
            </Button>
          </form>
        </div>

        <p className="mt-4 text-[11px] text-slate-500">
          Sessions last 24 hours. Contact the district administrator if your access has lapsed.
        </p>
      </div>
    </div>
  );
};

export default Login;
