import type { AxiosAdapter } from 'axios';
import {
  DEMO_FACULTY,
  DEMO_GENERATION_BLOCKED,
  DEMO_LOADS,
  DEMO_LOAD_SUMMARY,
  DEMO_READINESS,
  DEMO_RESOURCES,
  DEMO_TERM,
  DEMO_TEMPLATE,
  DEMO_TIME_SLOTS,
  DEMO_TIMETABLE,
  DEMO_USER,
  DEMO_VERSION,
  DEMO_CLASS_SUMMARY,
  DEMO_SUBJECT_SUMMARY,
} from './fixtures';

const response = (config: Parameters<AxiosAdapter>[0], data: unknown, status = 200) => ({
  data,
  status,
  statusText: status === 200 ? 'OK' : 'Demo mode',
  headers: {},
  config,
});

const rejectMutation = (config: Parameters<AxiosAdapter>[0], detail: string) =>
  Promise.reject({
    config,
    response: { status: 409, statusText: 'Demo mode', headers: {}, config, data: { detail } },
  });

export const demoAdapter: AxiosAdapter = async (config) => {
  const path = (config.url ?? '').split('?')[0];
  const method = (config.method ?? 'get').toUpperCase();

  if (method !== 'GET') {
    if (method === 'POST' && path === '/timetable') {
      return response(config, DEMO_TIMETABLE);
    }
    if (path.includes('/generate-source') || path.includes('/generate')) {
      return Promise.reject({
        config,
        response: {
          status: 409,
          statusText: 'Demo mode',
          headers: {},
          config,
          data: { detail: DEMO_GENERATION_BLOCKED },
        },
      });
    }
    return rejectMutation(config, 'This action is disabled in local demo mode. No database write was attempted.');
  }

  if (path === '/auth/me') return response(config, DEMO_USER);
  if (path === '/academic-terms/current') return response(config, DEMO_TERM);
  if (path === '/academic-terms') return response(config, { items: [DEMO_TERM], total: 1, page: 1, page_size: 20 });
  if (path === '/faculty') return response(config, { items: DEMO_FACULTY, total: DEMO_FACULTY.length, page: 1, page_size: 100 });
  if (path === '/resources') return response(config, { items: DEMO_RESOURCES, total: DEMO_RESOURCES.length, page: 1, page_size: 20 });
  if (path === '/load/reports/load-summary') return response(config, DEMO_LOAD_SUMMARY);
  if (path === '/reports/faculty-load') return response(config, { academic_term_id: DEMO_TERM.id, summary: DEMO_LOAD_SUMMARY.faculty_summary });
  if (path === '/reports/timetable-summary') return response(config, {
    timetable_id: DEMO_TIMETABLE.id,
    timetable_name: DEMO_TIMETABLE.name,
    version_number: DEMO_VERSION.version_number,
    version_status: DEMO_VERSION.status,
    total_entries: DEMO_VERSION.entries.length,
    entries_by_type: {},
    entries_by_section: {},
    entries_by_faculty: {},
    entries_by_resource: {},
  });
  if (path === '/reports/resource-utilization') return response(config, {
    timetable_id: DEMO_TIMETABLE.id,
    total_resources: DEMO_RESOURCES.length,
    total_time_slots: DEMO_TIME_SLOTS.length,
    utilization: DEMO_RESOURCES.map((resource) => ({
      resource_id: resource.id,
      resource_name: resource.name,
      resource_type: resource.resource_type,
      capacity: resource.capacity,
      used_slots: DEMO_VERSION.entries.filter((entry) => entry.resource_id === resource.id).length,
      total_slots: DEMO_TIME_SLOTS.length / 6,
      utilization_percent: Math.round((DEMO_VERSION.entries.filter((entry) => entry.resource_id === resource.id).length / (DEMO_TIME_SLOTS.length / 6)) * 100),
    })),
  });
  if (path === '/reports/conflicts') return response(config, {
    timetable_id: DEMO_TIMETABLE.id,
    version_number: DEMO_VERSION.version_number,
    is_valid: true,
    errors: [],
    warnings: [],
    violations: {},
  });
  if (path === '/reports/validation') return response(config, {
    timetable_id: DEMO_TIMETABLE.id,
    version_number: DEMO_VERSION.version_number,
    status: 'PASS',
    is_valid: true,
    errors: [],
    warnings: [],
    violations: {},
    total_entries: DEMO_VERSION.entries.length,
  });
  if (path === '/load/reports/class-summary') return response(config, { academic_term_id: DEMO_TERM.id, summary: DEMO_CLASS_SUMMARY });
  if (path === '/load/reports/subject-summary') return response(config, { academic_term_id: DEMO_TERM.id, summary: DEMO_SUBJECT_SUMMARY });
  if (path === '/load') return response(config, { items: DEMO_LOADS, total: DEMO_LOADS.length, page: 1, page_size: 100 });
  if (path === '/templates') return response(config, [DEMO_TEMPLATE]);
  if (path === '/timetable') return response(config, { timetables: [DEMO_TIMETABLE] });
  if (/\/timetable\/[^/]+$/.test(path)) return response(config, DEMO_TIMETABLE);
  if (/\/templates\/[^/]+\/time-slots$/.test(path)) return response(config, DEMO_TIME_SLOTS);
  if (/\/timetable\/[^/]+\/workbook-readiness$/.test(path)) return response(config, DEMO_READINESS);
  if (/\/timetable\/[^/]+\/versions\/[^/]+$/.test(path)) return response(config, DEMO_VERSION);
  if (/\/timetable\/[^/]+\/versions$/.test(path)) return response(config, { versions: [DEMO_VERSION] });
  if (/\/timetable\/[^/]+\/readiness$/.test(path)) return response(config, { timetable_id: DEMO_TIMETABLE.id, ready: true, errors: [], warnings: [], checks: [] });
  if (path === '/leave') return response(config, { leaves: [] });
  if (path === '/substitutions' || path === '/leave/substitutions') return response(config, { substitutions: [] });
  if (path === '/notifications') return response(config, { notifications: [] });
  if (path === '/assignments') return response(config, []);

  return response(config, []);
};
