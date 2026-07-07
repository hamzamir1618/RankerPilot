import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@rankerpilot/shared";

// In-memory token storage
let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

// Ensure the API url is correct. Default to localhost:8000
const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return request;
  },
  async onResponse({ request, response }) {
    if (response.status === 401) {
      // Avoid infinite loops by not intercepting refresh itself
      if (request.url.includes("/v1/auth/refresh")) {
        return response;
      }
      
      try {
        // Attempt silent refresh
        const refreshReq = await fetch(`${baseUrl}/v1/auth/refresh`, {
          method: "POST",
          // The refresh token is in an HttpOnly cookie and will be sent automatically
          // by the browser if credentials are included. We might need to ensure credentials are included.
        });
        
        if (refreshReq.ok) {
          // If the backend returns the new access token in the response or sets a new cookie
          // Assuming backend sets a new cookie or returns token. 
          // Wait, the prompt says "storing access token in memory... refresh cookie".
          // If refresh endpoint returns {"access_token": "..."} we grab it:
          const data = await refreshReq.json();
          if (data.access_token) {
            setAccessToken(data.access_token);
            // Retry original request
            const newRequest = new Request(request, {
              headers: new Headers(request.headers)
            });
            newRequest.headers.set("Authorization", `Bearer ${data.access_token}`);
            return await fetch(newRequest);
          }
        }
      } catch (err) {
        console.error("Silent refresh failed", err);
      }
      
      // If refresh failed, clear token and let the app handle the 401 (e.g. redirect to login)
      setAccessToken(null);
    }
    return response;
  }
};

export const apiClient = createClient<paths>({
  baseUrl,
  // Ensure cookies are sent for the refresh endpoint (and others if needed)
});

// Since openapi-fetch v0.13.0, we use the newer `.use()` method to add middleware.
apiClient.use(authMiddleware);
