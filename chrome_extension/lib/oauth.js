// ============================================
// MailGuard-AI — Google OAuth via chrome.identity
// ============================================
// Runs the Authorization Code flow against Google's OAuth endpoint using
// chrome.identity.launchWebAuthFlow, then exchanges the resulting code for a
// Firebase ID token via the Identity Toolkit REST API.
//
// Reference: https://developer.chrome.com/docs/extensions/reference/api/identity#method-launchWebAuthFlow

import { FIREBASE_CONFIG, OAUTH_CLIENT_ID, OAUTH_SCOPES } from "./firebase-config.js";

const GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";
const FIREBASE_IDP_URL = (apiKey) =>
  `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${apiKey}`;

/**
 * Returns the OAuth redirect URL Chrome expects for this extension ID.
 * Always of the form `https://<EXT_ID>.chromiumapp.org/oauth2`.
 */
export function getRedirectURL() {
  return chrome.identity.getRedirectURL("oauth2");
}

/**
 * Build the Google OAuth consent URL.
 */
export function buildAuthURL(state = "") {
  const url = new URL(GOOGLE_AUTH_ENDPOINT);
  url.searchParams.set("client_id", OAUTH_CLIENT_ID);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("redirect_uri", getRedirectURL());
  url.searchParams.set("scope", OAUTH_SCOPES.join(" "));
  url.searchParams.set("access_type", "offline");
  url.searchParams.set("include_granted_scopes", "true");
  url.searchParams.set("prompt", "consent");
  if (state) url.searchParams.set("state", state);
  return url.toString();
}

/**
 * Exchange a Google authorization code for a Firebase ID token + refresh
 * token by calling the Identity Toolkit `signInWithIdp` endpoint with
 * `google.com` as the provider.
 */
export async function exchangeCodeForFirebaseToken(code) {
  const redirectUri = getRedirectURL();
  const postBody = new URLSearchParams({
    code,
    client_id: OAUTH_CLIENT_ID,
    client_secret: "", // Public client (Chrome extension) — leave empty.
    grant_type: "authorization_code",
    redirect_uri: redirectUri,
  }).toString();

  const resp = await fetch(FIREBASE_IDP_URL(FIREBASE_CONFIG.apiKey), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      postBody,
      requestUri: redirectUri,
      returnIdpCredential: true,
      returnSecureToken: true,
    }),
  });

  if (!resp.ok) {
    const errBody = await resp.text();
    throw new Error(`Firebase token exchange failed (${resp.status}): ${errBody}`);
  }

  const data = await resp.json();
  // data shape:
  //   { idToken, refreshToken, expiresIn, localId (uid), email, ... }
  if (!data.idToken) {
    throw new Error("Firebase token exchange returned no idToken");
  }
  return {
    idToken: data.idToken,
    refreshToken: data.refreshToken,
    expiresIn: data.expiresIn,
    uid: data.localId,
    email: data.email,
    displayName: data.displayName,
    photoUrl: data.photoUrl,
    raw: data,
  };
}

/**
 * Refresh the Firebase ID token using the stored refresh token.
 */
export async function refreshFirebaseToken(refreshToken) {
  const url = `https://securetoken.googleapis.com/v1/token?key=${FIREBASE_CONFIG.apiKey}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
    }).toString(),
  });
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
 * High-level helper: launch the OAuth consent flow and return Firebase tokens.
 */
export async function startGoogleSignIn() {
  const authUrl = buildAuthURL();
  const finalUrl = await chrome.identity.launchWebAuthFlow({
    url: authUrl,
    interactive: true,
  });

  if (!finalUrl) {
    throw new Error("OAuth flow returned no URL (user cancelled?)");
  }

  const params = new URL(finalUrl).searchParams;
  const error = params.get("error");
  if (error) {
    throw new Error(`Google OAuth error: ${error} ${params.get("error_description") || ""}`);
  }
  const code = params.get("code");
  if (!code) {
    throw new Error("OAuth flow returned no authorization code");
  }

  return exchangeCodeForFirebaseToken(code);
}