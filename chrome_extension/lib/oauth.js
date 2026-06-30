// ============================================
// MailGuard-AI — Google OAuth via chrome.identity
// ============================================
// Uses `chrome.identity.getAuthToken` which delegates to Chrome's built-in
// extension OAuth client. Chrome signs the request with the extension's own
// OAuth client whose Application ID == Extension ID, so Cloud Console
// verification is automatic — no `oauth2` block in manifest.json needed
// (and having one with a mismatched client_id causes "user did not approve
// access" because Chrome shows an unverified-app warning).
//
// Reference: https://developer.chrome.com/docs/extensions/reference/api/identity

const IdentityToolkit = {
  signInWithIdp: (apiKey, providerId) =>
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${apiKey}`,
  refreshToken: (apiKey) =>
    `https://securetoken.googleapis.com/v1/token?key=${apiKey}`,
  revokeToken: (apiKey, token) =>
    `https://oauth2.googleapis.com/revoke?key=${apiKey}`,
};

/**
 * Acquire a Google OAuth2 access token via Chrome's Identity API.
 *
 * Always clears the cached token first to surface the account-picker every
 * time, which avoids stale cookies / wrong-account confusion. Set
 * `forceFresh=false` only when you already validated freshness.
 */
export async function getGoogleAccessToken({ forceFresh = true } = {}) {
  if (!chrome.identity?.getAuthToken) {
    throw new Error("chrome.identity API unavailable in this context");
  }

  // 1) Try to peek a cached token. If stale, drop it.
  const cached = await new Promise((resolve) =>
    chrome.identity.getAuthToken({ interactive: false }, (t) =>
      resolve(chrome.runtime.lastError ? null : t),
    ),
  );
  if (cached) {
    try {
      const stillValid = await isGoogleTokenValid(cached);
      if (stillValid) return cached;
    } catch {
      // fall through to clear+re-fetch
    }
    await new Promise((resolve) =>
      chrome.identity.removeCachedAuthToken({ token: cached }, resolve),
    );
  }

  // 2) When forcing a fresh pick we wipe everything of the same scopes first.
  if (forceFresh) {
    await clearAllCachedTokens();
  }

  // 3) Interactive pick.
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive: true }, (token) => {
      if (chrome.runtime.lastError) {
        const msg = chrome.runtime.lastError.message || "unknown";
        // Friendly message for the common "user cancelled" case.
        if (/cancel|denied|approve|user/i.test(msg)) {
          reject(
            new Error(
              "Google sign-in cancelled. If the popup showed an unverified-app warning, see DEPLOY.md > OAuth client setup.",
            ),
          );
          return;
        }
        reject(new Error(`chrome.identity error: ${msg}`));
        return;
      }
      if (!token) {
        reject(new Error("Chrome returned no token"));
        return;
      }
      resolve(token);
    });
  });
}

async function clearAllCachedTokens() {
  return new Promise((resolve) => {
    chrome.identity.clearAllCachedAuthTokens(() => resolve());
  });
}

async function revokeGoogleToken(token, apiKey) {
  // Best-effort: token revocation failure shouldn't block sign-out.
  try {
    const url = `https://oauth2.googleapis.com/revoke?token=${encodeURIComponent(
      token,
    )}${apiKey ? `&key=${encodeURIComponent(apiKey)}` : ""}`;
    await fetch(url, { method: "POST" });
  } catch (err) {
    console.warn("Revoke failed:", err);
  } finally {
    await new Promise((resolve) =>
      chrome.identity.removeCachedAuthToken({ token }, resolve),
    );
  }
}

async function isGoogleTokenValid(token) {
  try {
    const resp = await fetch(
      `https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=${encodeURIComponent(
        token,
      )}`,
    );
    if (!resp.ok) return false;
    const info = await resp.json();
    // 0 means still valid, anything else means expired/revoked
    return info.expires_in > 0 && info.error == null;
  } catch {
    return false;
  }
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
    // Most common: FirebaseAuthError: UNREGISTERED_IDP (wrong project), or
    // OPERATION_NOT_ALLOWED (Google sign-in not enabled in Firebase console).
    const message =
      data?.error?.message || text || `HTTP ${resp.status}`;
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
export async function signOut({ apiKey, googleAccessToken } = {}) {
  await clearAllCachedTokens();
  if (googleAccessToken) {
    await revokeGoogleToken(googleAccessToken, apiKey);
  }
}