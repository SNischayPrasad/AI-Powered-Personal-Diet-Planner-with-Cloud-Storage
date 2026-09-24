import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { onUnauthorized, tokenStore } from "../services/apiClient.js";
import * as authService from "../services/authService.js";
import { getProfile } from "../services/profileService.js";

const AuthContext = createContext(null);

const EXPIRED_MESSAGES = {
  token_revoked: "You were logged out. Please log in again.",
  token_expired: "Your session has expired. Please log in again.",
};

// Holds the logged-in user for the whole app. The JWT itself lives in tokenStore; on page
// load it is validated by fetching the profile (a stateless API has no "session" to ask).
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(() => (tokenStore.get() ? "loading" : "anonymous"));
  const [notice, setNotice] = useState(null);
  // Where to go right after logging in or registering ({ to, state }). The public-only route
  // guard performs the redirect, so there is exactly one navigation and no race.
  const [redirectTo, setRedirectTo] = useState(null);

  const endSession = useCallback((message = null) => {
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
    setNotice(message);
    setRedirectTo(null);
  }, []);

  useEffect(() => {
    onUnauthorized((code) => endSession(EXPIRED_MESSAGES[code] ?? EXPIRED_MESSAGES.token_expired));
    return () => onUnauthorized(null);
  }, [endSession]);

  useEffect(() => {
    if (!tokenStore.get()) return undefined;
    let cancelled = false;
    getProfile()
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setStatus("authenticated");
      })
      .catch((error) => {
        if (cancelled) return;
        if (error.status === 401) {
          endSession(EXPIRED_MESSAGES[error.code] ?? EXPIRED_MESSAGES.token_expired);
        } else {
          setStatus("anonymous");
          setNotice(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [endSession]);

  const startSession = useCallback((response) => {
    tokenStore.set(response.access_token);
    setUser(response.user);
    setStatus("authenticated");
    setNotice(null);
    return response.user;
  }, []);

  const login = useCallback(
    async (credentials, { redirectTo: destination = null } = {}) => {
      const response = await authService.login(credentials);
      setRedirectTo(destination);
      return startSession(response);
    },
    [startSession],
  );

  const register = useCallback(
    async (details, { redirectTo: destination = null } = {}) => {
      const response = await authService.register(details);
      setRedirectTo(destination);
      return startSession(response);
    },
    [startSession],
  );

  const logout = useCallback(async () => {
    try {
      await authService.logout(); // revoke the token server-side
    } catch {
      // Already expired or the server is unreachable: forget the token locally anyway.
    } finally {
      endSession("You have been logged out.");
    }
  }, [endSession]);

  const refreshUser = useCallback(async () => {
    const profile = await getProfile();
    setUser(profile);
    return profile;
  }, []);

  const clearNotice = useCallback(() => setNotice(null), []);

  const value = useMemo(
    () => ({
      user,
      status,
      notice,
      redirectTo,
      login,
      register,
      logout,
      refreshUser,
      setUser,
      clearNotice,
    }),
    [user, status, notice, redirectTo, login, register, logout, refreshUser, clearNotice],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
