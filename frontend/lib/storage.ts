const ACCESS_TOKEN = "access_token";
const REFRESH_TOKEN = "refresh_token";
const USER_FIRST_NAME = "user_first_name";

export function saveTokens(access: string, refresh: string) {
  localStorage.setItem(ACCESS_TOKEN, access);
  localStorage.setItem(REFRESH_TOKEN, refresh);
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN);
  localStorage.removeItem(REFRESH_TOKEN);
}

// The login endpoint (SimpleJWT TokenObtainPairView) returns only tokens, no
// user data, so this is only ever populated right after registration, from
// the name the user just typed (see RegisterForm). Users who log in on a
// fresh session without registering here will have no stored name.
export function saveUserFirstName(name: string) {
  localStorage.setItem(USER_FIRST_NAME, name);
}

export function getUserFirstName() {
  return localStorage.getItem(USER_FIRST_NAME);
}

export function clearUserFirstName() {
  localStorage.removeItem(USER_FIRST_NAME);
}