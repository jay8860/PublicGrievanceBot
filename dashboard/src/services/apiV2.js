// Single API layer for the platform pages.
// Reuses the existing axios instance (JWT header + soft logout on 401).
import api from '../api';

const V2 = '/v2';

function unwrap(promise) {
  return promise.then((res) => res.data);
}

export function apiErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(', ');
  }
  if (error?.message) return error.message;
  return 'Something went wrong';
}

export const http = {
  get: (path, config) => unwrap(api.get(`${V2}${path}`, config)),
  post: (path, body, config) => unwrap(api.post(`${V2}${path}`, body, config)),
  patch: (path, body) => unwrap(api.patch(`${V2}${path}`, body)),
  put: (path, body) => unwrap(api.put(`${V2}${path}`, body)),
};

export const AuthApi = {
  me: () => http.get('/me'),
  changePassword: (body) => http.post('/admins/me/password', body),
};

export const SecurityApi = {
  status: () => http.get('/security-status'),
};

export const AdminApi = {
  list: () => http.get('/admins'),
  create: (body) => http.post('/admins', body),
  deactivate: (id) => http.post(`/admins/${id}/deactivate`),
};

export const DepartmentApi = {
  list: () => http.get('/departments'),
  create: (body) => http.post('/departments', body),
  update: (id, body) => http.patch(`/departments/${id}`, body),
  categories: (id) => http.get(`/departments/${id}/categories`),
  createCategory: (body) => http.post('/categories', body),
  updateCategory: (id, body) => http.patch(`/categories/${id}`, body),
};

export const RuleApi = {
  list: () => http.get('/escalation-rules'),
  upsert: (departmentId, body) => http.put(`/escalation-rules/${departmentId}`, body),
};

export const OfficerApi = {
  list: (params) => http.get('/officers', { params }),
  get: (id) => http.get(`/officers/${id}`),
  create: (body) => http.post('/officers', body),
  update: (id, body) => http.patch(`/officers/${id}`, body),
  invite: (id, ttlHours = 48) => http.post(`/officers/${id}/invitation`, { ttl_hours: ttlHours }),
  revokeTelegram: (id) => http.post(`/officers/${id}/revoke-telegram`),
  codes: (id) => http.get(`/officers/${id}/codes`),
};

export const ComplaintApi = {
  list: (params) => http.get('/complaints', { params }),
  get: (id) => http.get(`/complaints/${id}`),
  assign: (id, body) => http.post(`/complaints/${id}/assign`, body),
  acknowledge: (id) => http.post(`/complaints/${id}/acknowledge`),
  progress: (id, note) => http.post(`/complaints/${id}/progress`, { note }),
  escalate: (id, note = '') => http.post(`/complaints/${id}/escalate`, { note }),
  pause: (id, reason) => http.post(`/complaints/${id}/pause`, { reason }),
  resume: (id) => http.post(`/complaints/${id}/resume`),
  resolve: (id, body) => http.post(`/complaints/${id}/resolve`, body),
  reopen: (id, note) => http.post(`/complaints/${id}/reopen`, { note }),
  feedback: (id, body) => http.post(`/complaints/${id}/feedback`, body),
  verify: (id, body) => http.post(`/complaints/${id}/verification`, body),
};

export const AnalyticsApi = {
  dashboard: (days = 14) => http.get('/analytics/dashboard', { params: { days } }),
  overview: () => http.get('/analytics/overview'),
  officers: () => http.get('/analytics/officers'),
  performance: () => http.get('/analytics/officer-performance'),
  wards: () => http.get('/analytics/wards'),
  trends: (months = 6) => http.get('/analytics/trends', { params: { months } }),
  geo: (params) => http.get('/analytics/geo', { params }),
};

export const EscalationApi = {
  centre: () => http.get('/escalation-centre'),
};

export const VerificationApi = {
  list: (verdict) => http.get('/verifications', { params: verdict ? { verdict } : {} }),
};

export const AuditApi = {
  logs: (params) => http.get('/audit-logs', { params }),
};

export const ReportApi = {
  async exportComplaints(format, params = {}) {
    const res = await api.get(`${V2}/reports/complaints`, {
      params: { format, ...params },
      responseType: 'blob',
    });
    return res.data;
  },
};
