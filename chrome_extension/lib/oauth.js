// ============================================
// MailGuard-AI — Google OAuth via chrome.identity
// ============================================
// Two-tier strategy:
//   1. `chrome.identity.getAuthToken` (Chrome's built-in flow — requires a
//      Chrome Extension OAuth client whose Application ID matches the
//      extension ID).
//   2. Fallback: `launchWebAuthFlow` with the Web OAuth client + PKCE —
//      works with any Web OAuth client registered in the same Google Cloud
//      project, doesn't require a separate Chrome Extension client.
//
// We start at tier (1) for the simpler UX (no popup redirect) and fall back
// to (2) automatically when tier (1) fails because the OAuth client type
// doesn't match the manifest.
//
// Reference: https://developer.chrome.com/docs/extensions/reference/api/identity
// Reference: https://firebase.google.com/docs/reference/rest/auth#section-signinwithidp

import { OAUTH_CLIENT_ID } from "./firebase-config.js";

const IdentityToolkit = {
  signInWithIdp: (apiKey, providerId) =>
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${apiKey}`,
  refreshToken: (apiKey) =>
    `https://securetoken.googleapis.com/v1/token?key=${apiKey}`,
  revokeToken: () => `https://oauth2.googleapis.com/revoke`,
  tokenInfo: (token) =>
    `https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=${encodeURIComponent(
      token,
    )}`,
};

function isOAuthClientError(message) {
  return /invalid.*client|unregistered|oauth.*client.*id|redirect_uri_mismatch/i.test(
    String(message || ""),
  );
}

function isUserCancelled(message) {
  return /cancel|denied|approve|user did not/i.test(String(message || ""));
}

// ---------- Tier 1: chrome.identity.getAuthToken ----------

async function clearAllCachedTokens() {
  return new Promise((resolve) => {
    if (!chrome.identity?.clearAllCachedAuthTokens) {
      resolve();
      return;
    }
    chrome.identity.clearAllCachedAuthTokens(() => resolve());
  });
}

async function isGoogleTokenValid(token) {
  try {
    const resp = await fetch(IdentityToolkit.tokenInfo(token));
    if (!resp.ok) return false;
    const info = await resp.json();
    return info?.expires_in > 0 && !info?.error;
  } catch {
    return false;
  }
}

async function tryGetAuthToken({ forceFresh = true } = {}) {
  if (!chrome.identity?.getAuthToken) {
    throw new Error("chrome.identity API unavailable");
  }

  // 1) Peek cached token; reuse if still valid.
  const cached = await new Promise((resolve) =>
    chrome.identity.getAuthToken({ interactive: false }, (t) =>
      resolve(chrome.runtime.lastError ? null : t),
    ),
  );
  if (cached) {
    if (await isGoogleTokenValid(cached)) return { token: cached, source: "cache" };
    await new Promise((resolve) =>
      chrome.identity.removeCachedAuthToken({ token: cached }, resolve),
    );
  }

  if (forceFresh) await clearAllCachedTokens();

  // 2) Interactive flow.
  const token = await new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive: true }, (t) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message || "unknown"));
        return;
      }
      if (!t) {
        reject(new Error("Chrome returned no token"));
        return;
      }
      resolve(t);
    });
  });

  return { token, source: "getAuthToken" };
}

// ---------- Tier 2: launchWebAuthFlow + PKCE ----------

function generateCodeVerifier() {
  const arr = new Uint8Array(64);
  crypto.getRandomValues(arr);
  return base64UrlEncode(arr);
}

async function generateCodeChallenge(verifier) {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}

function base64UrlEncode(bytes) {
  let str = "";
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function tryLaunchWebAuthFlow({ forceFresh = true } = {}) {
  if (!chrome.identity?.launchWebAuthFlow) {
    throw new Error("launchWebAuthFlow unavailable");
  }

  const redirectUri = chrome.identity.getRedirectURL("oauth2");
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);

  const params = new URLSearchParams({
    client_id: OAUTH_CLIENT_ID,
    response_type: "code",
    redirect_uri: redirectUri,
    scope: "openid email profile",
    code_challenge: challenge,
    code_challenge_method: "S256",
    access_type: "offline",
    prompt: forceFresh ? "consent" : "select_account",
    include_granted_scopes: "true",
  });
  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

  const finalUrl = await new Promise((resolve, reject) => {
    chrome.identity.launchWebAuthFlow(
      { url: authUrl, interactive: true },
      (respUrl) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message || "unknown"));
          return;
        }
        if (!respUrl) {
          reject(new Error("OAuth flow returned no URL"));
          return;
        }
        resolve(respUrl);
      },
    );
  });

  const url = new URL(finalUrl);
  const error = url.searchParams.get("error");
  if (error) {
    throw new Error(`OAuth error: ${error}`);
  }
  const code = url.searchParams.get("code");
  if (!code) {
    throw new Error("OAuth flow did not return code: " + finalUrl);
  }

  // Exchange code → access_token. The Web OAuth client requires client_id
  // and (if configured) client_secret. For SPAs without a secret we use
  // PKCE-only exchange, which Google supports for public clients.
  const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: OAUTH_CLIENT_ID,
      redirect_uri: redirectUri,
      grant_type: "authorization_code",
      code_verifier: verifier,
    }).toString(),
  });

  const tokenText = await tokenResp.text();
  if (!tokenResp.ok) {
    throw new Error(
      `Token exchange failed (${tokenResp.status}): ${tokenText}`,
    );
  }
  const tokenData = JSON.parse(tokenText);
  if (!tokenData.access_token) {
    throw new Error("Token response missing access_token: " + tokenText);
  }
  return { token: tokenData.access_token, source: "launchWebAuthFlow" };
}

// ---------- Public API ----------

/**
 * Acquire a Google OAuth2 access token. Tries `getAuthToken` first, falls
 * back to `launchWebAuthFlow + PKCE` automatically.
 */
export async function getGoogleAccessToken({ forceFresh = true } = {}) {
  try {
    return await tryGetAuthToken({ forceFresh });
  } catch (err) {
    if (isUserCancelled(err.message)) {
      throw new Error("Google sign-in cancelled.");
    }
    console.warn("getAuthToken failed, trying launchWebAuthFlow fallback:", err);
    try {
      return await tryLaunchWebAuthFlow({ forceFresh });
    } catch (fallbackErr) {
      if (isUserCancelled(fallbackErr.message)) {
        throw new Error("Google sign-in cancelled.");
      }
      throw new Error(
        `Both OAuth flows failed. Primary: ${err.message}. Fallback: ${fallbackErr.message}`,
      );
    }
  }
}

/**
 * Revoke the cached Google OAuth2 access token (sign-out cleanup).
 */
export async function revokeGoogleAccessToken(token) {
  try {
    await fetch(IdentityToolkit.revokeToken(), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ token }).toString(),
    });
  } catch (err) {
    console.warn("Revoke failed:", err);
  }
  await new Promise((resolve) =>
    chrome.identity.removeCachedAuthToken?.({ token }, () => resolve()),
  );
  await clearAllCachedTokens();
}

/**
 * Trade a Google OAuth2 access token for a Firebase ID token + refresh token
 * via the Identity Toolkit `signInWithIdp` endpoint.
 */
export async function exchangeAccessTokenForFirebaseToken({
  apiKey,
  accessToken,
  providerId = "google.com",
  requestUri = "https://localhost",
}) {
  const postBody = new URLSearchParams({
    access_token: accessToken,
    providerId,
  }).toString();

  let resp;
  try {
    resp = await fetch(IdentityToolkit.signInWithIdp(apiKey, providerId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        postBody,
        requestUri,
        returnIdpCredential: true,
        returnSecureToken: true,
      }),
    });
  } catch (err) {
    throw new Error(
      "Network error while exchanging Google token with Firebase: " +
        err.message,
    );
  }

  const text = await resp.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error(`Non-JSON response from Firebase (${resp.status}): ${text}`);
  }

  if (!resp.ok || !data.idToken) {
    const message = data?.error?.message || text || `HTTP ${resp.status}`;
    throw new Error(
      `Firebase refused the Google credential (${resp.status}): ${message}`,
    );
  }

  return {
    idToken: data.idToken,
    refreshToken: data.refreshToken,
    expiresIn: data.expiresIn,
    uid: data.localId,
    email: data.email,
    displayName: data.displayName || data.fullName || "",
    photoUrl: data.photoUrl || "",
    raw: data,
  };
}

/**
 * Refresh the Firebase ID token using the stored refresh token.
 */
export async function refreshFirebaseToken({ apiKey, refreshToken }) {
  let resp;
  try {
    resp = await fetch(IdentityToolkit.refreshToken(apiKey), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
      }).toString(),
    });
  } catch (err) {
    throw new Error("Network error refreshing Firebase token: " + err.message);
  }

  if (!resp.ok) {
    const errBody = await resp.text();
    throw new Error(`Firebase refresh failed (${resp.status}): ${errBody}`);
  }
  const data = await resp.json();
  return {
    idToken: data.id_token,
    refreshToken: data.refresh_token,
    expiresIn: data.expires_in,
    uid: data.user_id,
    email: data.email,
    raw: data,
  };
}

/**
 * Drop all Google/Firebase state on sign-out.
 */
export async function signOut({ googleAccessToken } = {}) {
  await clearAllCachedTokens();
  if (googleAccessToken) {
    await revokeGoogleAccessToken(googleAccessToken);
  }
}