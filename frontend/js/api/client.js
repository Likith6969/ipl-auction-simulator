const API_BASE = "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  getTeams() {
    return request("/teams");
  },

  createSession(userTeamId) {
    return request("/sessions", {
      method: "POST",
      body: JSON.stringify({ user_team_id: userTeamId }),
    });
  },

  getSession(sessionId) {
    return request(`/sessions/${sessionId}`);
  },

  getRetention(sessionId) {
    return request(`/sessions/${sessionId}/retention`);
  },

  confirmRetention(sessionId, retentions) {
    return request(`/sessions/${sessionId}/retention`, {
      method: "POST",
      body: JSON.stringify({ retentions }),
    });
  },

  getAllRetentions(sessionId) {
    return request(`/sessions/${sessionId}/retention/all`);
  },
};
