// ============================================
// MailGuard-AI — Firebase auth glue layer
// ============================================
// Wraps chrome.identity.getAuthToken + Identity Toolkit REST API and persists
// the resulting session in chrome.storage.local. The backend issues its own
// JWT after we POST the Firebase ID token to /api/v1/auth/firebase/login.

import { BACKEND_BASE_URL, FIREBASE_CONFIG, STORAGE_KEYS } from "./firebase-config.js";
import {
  exchangeAccessTokenForFirebaseToken,
  getGoogleAccessToken,
  refreshFirebaseToken as refreshFirebaseIdToken,
  revokeGoogleAccessToken,
} from "./oauth.js";

const STORAGE = chrome.storage.local;

async function readStorage(keys) {
  return new Promise((resolve) => STORAGE.get(keys, resolve));
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
    const payload = JSON.parse(
      atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")),
    );
    return Number(payload.exp || 0) * 1000;
  } catch {
    return 0;
  }
}

async function isIdTokenFresh(idToken) {
  if (!idToken) return false;
  const exp = decodeJwtExpiry(idToken);
  if (!exp) return false;
  return Date.now() < exp - 60_000;
}

async function ensureFreshIdToken() {
  const stored = await readStorage([
    STORAGE_KEYS.ID_TOKEN,
    STORAGE_KEYS.REFRESH_TOKEN,
  ]);
  const idToken = stored[STORAGE_KEYS.ID_TOKEN];
  const refreshToken = stored[STORAGE_KEYS.REFRESH_TOKEN];
  if (await isIdTokenFresh(idToken)) {
    return { idToken, refreshed: false };
  }
  if (!refreshToken) {
    throw new Error("No Firebase refresh token; user must sign in again");
  }
  const refreshed = await refreshFirebaseIdToken({
    apiKey: FIREBASE_CONFIG.apiKey,
    refreshToken,
  });
  await writeStorage({
    [STORAGE_KEYS.ID_TOKEN]: refreshed.idToken,
    [STORAGE_KEYS.REFRESH_TOKEN]: refreshed.refreshToken,
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
  const googleAccessToken = await getGoogleAccessToken({ interactive: true });
  const firebaseTokens = await exchangeAccessTokenForFirebaseToken({
    apiKey: FIREBASE_CONFIG.apiKey,
    accessToken: googleAccessToken,
  });

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
    googleAccessToken,
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
    try {
      const backendToken = await exchangeForBackendToken(idToken);
      await writeStorage({
        [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
        [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
          Date.now() + backendToken.expires_in * 1000,
      });
    } catch (err) {
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
  const stored = await readStorage([STORAGE_KEYS.UID]);
  return Boolean(stored[STORAGE_KEYS.UID]);
}

export async function signOut() {
  const stored = await readStorage(["google_access_token"]);
  if (stored.google_access_token) {
    await revokeGoogleAccessToken(stored.google_access_token);
  }
  await clearStorage([
    ...Object.values(STORAGE_KEYS),
    "google_access_token",
  ]);
}