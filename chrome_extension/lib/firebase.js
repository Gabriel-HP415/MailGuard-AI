// ============================================
// MailGuard-AI — Auth glue layer
// ============================================
//
// Unified session store over chrome.storage.local that exposes the same
// shape regardless of sign-in method:
//
//   - Firebase (Google OAuth via chrome.identity)
//   - Email + password (legacy / universal flow that needs no OAuth client)
//
// Both flows end up storing:
//   - backend_access_token / backend_access_token_expires_at
//   - firebase_uid (Firebase) OR user_id (email/password) — same field
//   - firebase_email / display_name / photo_url
//
// `signOut()` clears the entire session regardless of provider.

import {
  BACKEND_BASE_URL,
  FIREBASE_CONFIG,
  STORAGE_KEYS,
} from "./firebase-config.js";
import {
  exchangeAccessTokenForFirebaseToken,
  getGoogleAccessToken,
  refreshFirebaseToken as refreshFirebaseIdToken,
  signOut as signOutOauth,
} from "./oauth.js";

const STORAGE = chrome.storage.local;

function readStorage(keys) {
  return new Promise((resolve) => STORAGE.get(keys, resolve));
}

function writeStorage(values) {
  return new Promise((resolve) => STORAGE.set(values, resolve));
}

function clearStorage(keys) {
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
  try {
    const refreshed = await refreshFirebaseIdToken({
      apiKey: FIREBASE_CONFIG.apiKey,
      refreshToken,
    });
    await writeStorage({
      [STORAGE_KEYS.ID_TOKEN]: refreshed.idToken,
      [STORAGE_KEYS.REFRESH_TOKEN]: refreshed.refreshToken,
    });
    return { idToken: refreshed.idToken, refreshed: true };
  } catch (err) {
    await clearStorage(Object.values(STORAGE_KEYS));
    throw new Error(
      "Firebase session expired. Please sign in again. (" +
        (err.message || "refresh failed") +
        ")",
    );
  }
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
 * Persist a Firebase-derived session (used after Google sign-in).
 */
async function persistFirebaseSession({
  firebaseTokens,
  googleAccessToken,
  backendToken,
}) {
  await writeStorage({
    [STORAGE_KEYS.ID_TOKEN]: firebaseTokens.idToken,
    [STORAGE_KEYS.REFRESH_TOKEN]: firebaseTokens.refreshToken,
    [STORAGE_KEYS.UID]: firebaseTokens.uid,
    [STORAGE_KEYS.EMAIL]: firebaseTokens.email || "",
    [STORAGE_KEYS.DISPLAY_NAME]: firebaseTokens.displayName || "",
    [STORAGE_KEYS.PHOTO_URL]: firebaseTokens.photoUrl || "",
    [STORAGE_KEYS.SIGNED_IN_AT]: Date.now(),
    [STORAGE_KEYS.AUTH_PROVIDER]: "google",
    [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
    [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
      Date.now() + backendToken.expires_in * 1000,
    google_access_token: googleAccessToken,
  });
}

/**
 * Trigger the Google sign-in flow. Throws on any OAuth / Firebase error.
 * The popup converts these errors to user-friendly messages.
 */
export async function signInWithGoogle() {
  const googleAccessToken = await getGoogleAccessToken({ forceFresh: true });
  const firebaseTokens = await exchangeAccessTokenForFirebaseToken({
    apiKey: FIREBASE_CONFIG.apiKey,
    accessToken: googleAccessToken,
  });
  const backendToken = await exchangeForBackendToken(firebaseTokens.idToken);
  await persistFirebaseSession({
    firebaseTokens,
    googleAccessToken,
    backendToken,
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
 * Persist an email/password-derived session (used after /auth/register or
 * /auth/login). Returns the user profile as exposed by /auth/me.
 */
export async function persistBackendSession({ token, expiresIn, user }) {
  await writeStorage({
    [STORAGE_KEYS.BACKEND_TOKEN]: token,
    [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]: Date.now() + expiresIn * 1000,
    [STORAGE_KEYS.UID]: `email:${user?.id ?? user?.email ?? "unknown"}`,
    [STORAGE_KEYS.EMAIL]: user?.email || "",
    [STORAGE_KEYS.DISPLAY_NAME]:
      user?.full_name || user?.username || user?.email?.split("@")[0] || "User",
    [STORAGE_KEYS.PHOTO_URL]: user?.avatar_url || "",
    [STORAGE_KEYS.SIGNED_IN_AT]: Date.now(),
    [STORAGE_KEYS.AUTH_PROVIDER]: "email",
  });
  return user;
}

/**
 * Returns a valid Firebase ID token, refreshing it transparently when expired.
 * Throws when the user is not signed in via Firebase.
 */
export async function getIdToken() {
  const provider = (await readStorage([STORAGE_KEYS.AUTH_PROVIDER]))[
    STORAGE_KEYS.AUTH_PROVIDER
  ];
  if (provider !== "google") {
    throw new Error("Signed in with email/password — no Firebase ID token");
  }
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
  // Try to refresh via Firebase first; fall back to backend-only session.
  try {
    const firebaseToken = await getIdToken();
    const backendToken = await exchangeForBackendToken(firebaseToken);
    await writeStorage({
      [STORAGE_KEYS.BACKEND_TOKEN]: backendToken.access_token,
      [STORAGE_KEYS.BACKEND_TOKEN_EXPIRES_AT]:
        Date.now() + backendToken.expires_in * 1000,
    });
    return backendToken.access_token;
  } catch {
    throw new Error("Session expired. Please sign in again.");
  }
}

export async function getCurrentUser() {
  return readStorage([
    STORAGE_KEYS.UID,
    STORAGE_KEYS.EMAIL,
    STORAGE_KEYS.DISPLAY_NAME,
    STORAGE_KEYS.PHOTO_URL,
    STORAGE_KEYS.SIGNED_IN_AT,
    STORAGE_KEYS.AUTH_PROVIDER,
  ]);
}

export async function getAuthProvider() {
  const { [STORAGE_KEYS.AUTH_PROVIDER]: provider } = await readStorage([
    STORAGE_KEYS.AUTH_PROVIDER,
  ]);
  return provider || null;
}

export async function isSignedIn() {
  const stored = await readStorage([STORAGE_KEYS.UID, STORAGE_KEYS.BACKEND_TOKEN]);
  return Boolean(stored[STORAGE_KEYS.UID] && stored[STORAGE_KEYS.BACKEND_TOKEN]);
}

export async function signOut() {
  const stored = await readStorage(["google_access_token"]);
  try {
    await signOutOauth({
      apiKey: FIREBASE_CONFIG.apiKey,
      googleAccessToken: stored.google_access_token,
    });
  } catch (err) {
    console.warn("signOutOauth error:", err);
  }
  await clearStorage([
    ...Object.values(STORAGE_KEYS),
    "google_access_token",
    "mg_token",
    "mg_user",
  ]);
}