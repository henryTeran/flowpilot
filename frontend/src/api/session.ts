const SESSION_KEY = "flowpilot.access_token";

export function getAccessToken() {
  return sessionStorage.getItem(SESSION_KEY);
}

export function setAccessToken(token: string | null) {
  if (token) sessionStorage.setItem(SESSION_KEY, token);
  else sessionStorage.removeItem(SESSION_KEY);
}
