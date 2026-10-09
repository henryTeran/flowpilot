const SESSION_KEY = "flowpilot.access_token";

export function getAccessToken() {
  return sessionStorage.getItem(SESSION_KEY);
}

export function setAccessToken(token: string | null) {
  if (token) sessionStorage.setItem(SESSION_KEY, token);
  else sessionStorage.removeItem(SESSION_KEY);
}

// Presentation only; the API remains authoritative for permission checks.
export function getOperatorRole() {
  try {
    const claims = JSON.parse(atob((getAccessToken() || "").split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof claims.role === "string" ? claims.role : undefined;
  } catch { return undefined; }
}

// Presentation/recovery scoping only; grants are authorized by the API.
export function getOperatorSubject() {
  try {
    const claims = JSON.parse(atob((getAccessToken() || "").split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof claims.sub === "string" && claims.sub.trim() ? claims.sub : undefined;
  } catch { return undefined; }
}

// Presentation only; institute authorization remains on the server.
export function getOperatorInstitute() {
  try {
    const claims = JSON.parse(atob((getAccessToken() || "").split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof claims.institute_id === "string" && claims.institute_id.trim() === claims.institute_id ? claims.institute_id : undefined;
  } catch { return undefined; }
}
