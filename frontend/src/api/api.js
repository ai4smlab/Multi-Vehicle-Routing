// /lib/api.js
import axios from 'axios';

function extractErrorMessage(err) {
  const data = err.response?.data;
  const detail = data?.detail;

  // Pydantic style: detail is array of objects
  if (Array.isArray(detail)) {
    // e.g. [{"loc":["body","matrix"],"msg":"field required","type":"value_error.missing"}, ...]
    return detail.map(d => {
      const where = Array.isArray(d.loc) ? d.loc.join('.') : d.loc;
      return `${where ?? 'error'}: ${d.msg ?? d.message ?? JSON.stringify(d)}`;
    }).join('\n');
  }

  // detail is object
  if (detail && typeof detail === 'object') {
    try { return JSON.stringify(detail); } catch { /* ignore */ }
  }

  // detail is string
  if (typeof detail === 'string') return detail;

  // other common fields
  if (typeof data?.message === 'string') return data.message;

  // fallback
  return err.message || 'Request failed';
}

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  timeout: 910000,
});

api.interceptors.response.use(
  (res) => res,
  (err) => Promise.reject(new Error(extractErrorMessage(err)))
);

export default api;