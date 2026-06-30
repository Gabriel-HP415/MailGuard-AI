// ============================================
// MailGuard-AI — Google OAuth via chrome.identity
// ============================================
// Uses `chrome.identity.getAuthToken` (Chrome's built-in OAuth flow for
// extensions) to obtain a Google OAuth2 access token, then exchanges it for a
// Firebase ID token via the Identity Toolkit REST API.
//
// Reference: https://developer.chrome.com/docs/extensions/reference/api/identity
// Reference: https://firebase.google.com/docs/reference/rest/auth#section-signinwithidp

const FIREBASE_IDP_URL = (apiKey, providerId) =>
  `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${apiKey}`;

/**
 * Acquire a Google OAuth2 access token via the Chrome Identity API.
 *
 * Chrome shows a native account picker when needed (silent otherwise). The
 * token is cached by Chrome and revoked on signOut().
 */
export async function getGoogleAccessToken({ interactive = true } = {}) {
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive }, (token) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (!token) {
        reject(new Error("Chrome did not return an access token"));
        return;
      }
      resolve(token);
    });
  });
}

/**
 * Revoke the cached Google OAuth2 access token (sign-out cleanup).
 */
export async function revokeGoogleAccessToken(token) {
  return new Promise((resolve) => {
    chrome.identity.removeCachedAuthToken({ token }, () => resolve());
  });
}

/**
 * Trade a Google OAuth2 access token for a Firebase ID token + refresh token
 * via the Identity Toolkit `signInWithIdp` endpoint.
 */
export async function exchangeAccessTokenForFirebaseToken({
  apiKey,
  accessToken,
  providerId = "google.com",
  requestUri = "http://localhost",
}) {
  const postBody = new URLSearchParams({
    access_token: accessToken,
    providerId,
  }).toString();

  const resp = await fetch(FIREBASE_IDP_URL(apiKey, providerId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      postBody,
      requestUri,
      returnIdpCredential: true,
      returnSecureToken: true,
    }),
  });

  const text = await resp.text();
  if (!resp.ok) {
    throw new Error(`Firebase token exchange failed (${resp.status}): ${text}`);
  }
  const data = JSON.parse(text);
  if (!data.idToken) {
    throw new Error("Firebase response missing idToken: " + text);
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
  const url = `https://securetoken.googleapis.com/v1/token?key=${apiKey}`;
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