import http from 'k6/http';
import { check, sleep } from 'k6';

// 50 VUs concurrently queueing audits
export const options = {
    vus: 50,
    duration: '30s',
};

// You need a valid auth token to queue audits.
// Replace this with a valid token or generate one during setup.
const TOKEN = __ENV.AUTH_TOKEN || "test_token";
const BASE_URL = __ENV.API_URL || "http://localhost:8000";
const PROJECT_ID = __ENV.PROJECT_ID || "123e4567-e89b-12d3-a456-426614174000";

export default function () {
    const url = `${BASE_URL}/v1/projects/${PROJECT_ID}/audits`;
    
    const payload = JSON.stringify({
        root_url: 'https://example.com',
        mode: 'quick',
        page_limit: 5
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${TOKEN}`,
        },
    };

    const res = http.post(url, payload, params);

    check(res, {
        'status is 200': (r) => r.status === 200,
        'has audit id': (r) => JSON.parse(r.body).id !== undefined,
    });

    sleep(1);
}
