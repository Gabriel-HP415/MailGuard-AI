// ============================================
// MailGuard-AI — Firebase runtime configuration
// ============================================
// Public values only. The Web API key is intentionally embedded; security is
// enforced by Firebase Authentication rules, App Check, and the backend
// verifying the ID token via firebase-admin.

export const FIREBASE_CONFIG = Object.freeze({
  apiKey: "AIzaSyDKmMoGt3dmnpbCtFura-GOx_Hg-8M7--8",
  authDomain: "mailguard-ai-a7f0a.firebaseapp.com",
  projectId: "mailguard-ai-a7f0a",
});

// OAuth client registered as a Web application whose redirect URI matches
// `https://<EXT_ID>.chromiumapp.org/oauth2`. Update this constant whenever
// you change the Chrome extension ID (e.g. when shipping to production).
export const OAUTH_CLIENT_ID =
  "431641720493-co8nefc95oub7k7gvha196kjl8i7ia6e.apps.googleusercontent.com";

// Scopes requested from Google. Keep minimal — do NOT add gmail.readonly until
// the OAuth consent screen has been verified by Google.
export const OAUTH_SCOPES = [
  "openid",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
];

export const BACKEND_BASE_URL = "https://mailguard-ai-y0nh.onrender.com";

// chrome.storage.local keys — keep in sync with backend field names.
export const STORAGE_KEYS = Object.freeze({
  ID_TOKEN: "firebase_id_token",
  REFRESH_TOKEN: "firebase_refresh_token",
  UID: "firebase_uid",
  EMAIL: "firebase_email",
  DISPLAY_NAME: "firebase_display_name",
  PHOTO_URL: "firebase_photo_url",
  BACKEND_TOKEN: "backend_access_token",
  BACKEND_TOKEN_EXPIRES_AT: "backend_access_token_expires_at",
  SIGNED_IN_AT: "firebase_signed_in_at",
});