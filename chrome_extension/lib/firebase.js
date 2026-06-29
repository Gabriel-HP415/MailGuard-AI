// ============================================
// MailGuard-AI — Firebase auth glue layer
// ============================================
// Wraps chrome.identity OAuth + Identity Toolkit REST API and persists the
// resulting session in chrome.storage.local. The backend issues its own JWT
// after we POST the Firebase ID token to /api/v1/auth/firebase/login.

import { BACKEND_BASE_URL, STORAGE_KEYS } from "./firebase-config.js";
import { refreshFirebaseToken, startGoogleSignIn } from "./oauth.js";

const STORAGE = chrome.storage.local;

async function readStorage(keys) {
  return new Promise((resolve) => {
    STORAGE.get(keys, resolve);
  });
}

async function writeStorage(values) {
  return new Promise((resolve) => STORAGE.set(values, resolve));
}

async function clearStorage(keys) {
  return new Promise((resolve) => STORAGE.remove(keys, resolve));
}

function decodeJwtExpiry(idToken) {
  if (!idToken) return 0;
  const parts = idToken.split(".");
  if (parts.length < 2) return 0;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    return Number(payload.exp || 0) * 1000;
  } catch {
    return 0;
  }
}

async function isIdTokenFresh(idToken) {
  if (!idToken) return false;
  const exp = decodeJwtExpiry(idToken);
  if (!exp) return false;
  // Refresh 60s before expiry to avoid race conditions.
  return Date.now() < exp - 60_000;
}

async function ensureFreshIdToken() {
  const stored = await readStorage([
    STORAGE_KEYS.ID_TOKEN,
    STORAGE_KEYS.REFRESH_TOKEN,
    STORAGE_KEYS.UID,
  ]);
  const { [STORAGE_KEYS.ID_TOKEN]: idToken, [STORAGE_KEYS.REFRESH_TOKEN]: refreshToken } = stored;
  if (await isIdTokenFresh(idToken)) {
    return { idToken, refreshed: false };
  }
  if (!refreshToken) {
    throw new Error("No Firebase refresh token; user must sign in again");
  }
  const refreshed = await refreshFirebaseToken(refreshToken);
  await writeStorage({
    [STORAGE_KEYS.ID_TOKEN]: refreshed.idToken,
    [STORAGE_KEYS.REFRESH_TOKEN]: refreshed.refreshToken,
    [STORAGE_KEYS.UID]: refreshed.uid,
  });
  return { idToken: refreshed.idToken, refreshed: true };
}

async function exchangeForBackendToken(firebaseIdToken) {
  const resp = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/firebase/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: firebaseIdToken }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Backend login failed (${resp.status}): ${text}`);
  }
  return resp.json();
}

/**
 * Trigger the Google sign-in flow, persist Firebase tokens, exchange for
 * the backend JWT, and return the user profile.
 */
export async function signInWithGoogle() {
  const firebaseTokens = await startGoogleSignIn();

  await writeStorage({
    [STORAGE_KEYS.ID_TOKEN]: firebaseTokens.idToken,
    [STORAGE_KEYS.REFRESH_TOKEN]: firebaseTokens.refreshToken,
    [STORAGE_KEYS.UID]: firebaseTokens.uid,
    [STORAGE_KEYS.EMAIL]: firebaseTokens.email || "",
    [STORAGE_KEYS.DISPLAY_NAME]: firebaseTokens.displayName || "",
    [STORAGE_KEYS.PHOTO_URL]: firebaseTokens.photoUrl || "",
    [STORAGE_KEYS.SIGNED_IN_AT]: Date.now(),
  });

  const backendToken = await exchangeForBackendToken(firebaseTokens.idToken);
  await writeStorage({
    [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
    [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
      Date.now() + backendToken.expires_in * 1000,
  });

  return {
    uid: firebaseTokens.uid,
    email: firebaseTokens.email,
    displayName: firebaseTokens.displayName,
    photoUrl: firebaseTokens.photoUrl,
    backendToken,
  };
}

/**
 * Returns a valid Firebase ID token, refreshing it transparently when expired.
 * Throws when the user is not signed in.
 */
export async function getIdToken() {
  const { idToken, refreshed } = await ensureFreshIdToken();
  if (refreshed) {
    // Re-exchange with backend so it can rotate any session claims too.
    try {
      const backendToken = await exchangeForBackendToken(idToken);
      await writeStorage({
        [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
        [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
          Date.now() + backendToken.expires_in * 1000,
      });
    } catch (err) {
      // Backend unreachable / 5xx — keep using the refreshed Firebase token,
      // caller will surface a clearer error if the API call later fails.
      console.warn("Backend JWT refresh failed", err);
    }
  }
  return idToken;
}

export async function getBackendToken() {
  const stored = await readStorage([
    STORAGE_KEYS.BACKEND_TOKEN,
    STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT,
  ]);
  const token = stored[STORAGE_KEYS.BACKEND_TOKEN];
  const exp = stored[STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT] || 0;
  if (token && Date.now() < exp - 30_000) {
    return token;
  }
  // Refresh by re-exchanging Firebase ID token.
  const firebaseToken = await getIdToken();
  const backendToken = await exchangeForBackendToken(firebaseToken);
  await writeStorage({
    [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
    [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
      Date.now() + backendToken.expires_in * 1000,
  });
  return backendToken.access_token;
}

export async function getCurrentUser() {
  return readStorage([
    STORAGE_KEYS.UID,
    STORAGE_KEYS.EMAIL,
    STORAGE_KEYS.DISPLAY_NAME,
    STORAGE_KEYS.PHOTO_URL,
    STORAGE_KEYS.SIGNED_IN_AT,
  ]);
}

export async function isSignedIn() {
  const { [STORAGE_KEYS.UID]: uid } = await readStorage([STORAGE_KEYS.UID]);
  return Boolean(uid);
}

export async function signOut() {
  await clearStorage(Object.values(STORAGE_KEYS));
}