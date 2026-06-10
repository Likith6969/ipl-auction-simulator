const STORAGE_KEY = "ipl_auction_session";

export function saveSession(session) {
  const existing = loadSession();
  const payload = {
    sessionId: session.id,
    userTeamId: session.user_team_id,
    userTeam: session.user_team,
    phase: session.phase,
    initialPurseCr: session.initial_purse_cr,
    retentionConfirmed: existing?.retentionConfirmed ?? false,
    retentionSummary: existing?.retentionSummary ?? null,
    savedAt: new Date().toISOString(),
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  return payload;
}

export function updateRetentionSummary(summary, { phase } = {}) {
  const session = loadSession();
  if (!session) {
    return null;
  }
  session.retentionConfirmed = true;
  session.retentionSummary = summary;
  if (phase) {
    session.phase = phase;
  }
  session.savedAt = new Date().toISOString();
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  return session;
}

export function loadSession() {
  const raw = sessionStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function clearSession() {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function requireSession({ redirectTo = "/pages/team-select.html" } = {}) {
  const session = loadSession();
  if (!session?.sessionId) {
    window.location.href = redirectTo;
    return null;
  }
  return session;
}
