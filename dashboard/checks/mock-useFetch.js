// Stand-in for hooks/useFetch used by the Complaints SSR regression test.
// Returns data immediately so the page renders the table and the drawer
// reference (the line that crashed) is actually executed.
export function useFetch(loader) {
  const source = String(loader);
  if (source.includes('categories')) {
    return { data: [], loading: false, error: '', reload() {}, setData() {} };
  }
  if (source.includes('DepartmentApi.list')) {
    return {
      data: [{ id: 'd1', code: 'PWD', name: 'Public Works Department' }],
      loading: false, error: '', reload() {}, setData() {},
    };
  }
  if (source.includes('OfficerApi.list')) {
    return { data: [], loading: false, error: '', reload() {}, setData() {} };
  }
  return {
    data: {
      total: 1,
      items: [{
        id: 'c1', ticket_ref: 'GRV-2026-000001', category: 'Potholes',
        department: 'Public Works Department', area: 'Ward 7', ward: 'Ward 7',
        pincode: '493773', severity: 'High', status: 'ASSIGNED', level: 1,
        assigned_officer: 'Mohan Yadav', created_at: '2026-11-20T10:00:00Z',
        minutes_remaining: 1200, overdue: false, images: [],
        resolution_verification: '', description: 'Deep pothole near the school',
      }],
    },
    loading: false, error: '', reload() {}, setData() {},
  };
}
