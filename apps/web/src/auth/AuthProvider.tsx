import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { User, UserManager, WebStorageStateStore } from "oidc-client-ts";

type AuthContextValue = {
  loading: boolean;
  authenticated: boolean;
  error: string;
  accessToken: string;
  displayName: string;
  email: string;
  roles: string[];
  login: () => Promise<void>;
  logout: () => Promise<void>;
  hasAnyRole: (allowed: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const authority = import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/realms/resolveai";
const clientId = import.meta.env.VITE_OIDC_CLIENT_ID ?? "resolveai-api";
const appOrigin = window.location.origin;
const manager = new UserManager({
  authority,
  client_id: clientId,
  redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI ?? `${appOrigin}/auth/callback`,
  post_logout_redirect_uri:
    import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI ?? `${appOrigin}/`,
  response_type: "code",
  scope: "openid profile email",
  automaticSilentRenew: true,
  monitorSession: true,
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
});

let initialUserPromise: Promise<User | null> | null = null;

function loadInitialUser(): Promise<User | null> {
  if (initialUserPromise) return initialUserPromise;
  const isCallback = window.location.pathname === "/auth/callback";
  initialUserPromise = (isCallback
    ? manager.signinRedirectCallback()
    : manager.getUser()
  ).then((next) => {
    if (isCallback) {
      const state = next?.state as { returnTo?: unknown } | undefined;
      const returnTo =
        typeof state?.returnTo === "string" && state.returnTo.startsWith("/")
          ? state.returnTo
          : "/";
      window.history.replaceState({}, document.title, returnTo);
    }
    return next;
  });
  return initialUserPromise;
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string");
  return typeof value === "string" ? [value] : [];
}

function userRoles(user: User | null): string[] {
  if (!user) return [];
  const direct = stringList(user.profile.roles);
  const realmAccess = user.profile.realm_access as { roles?: unknown } | undefined;
  const accessTokenRoles = accessTokenClaims(user.access_token)?.realm_access?.roles;
  return [
    ...new Set([...direct, ...stringList(realmAccess?.roles), ...stringList(accessTokenRoles)]),
  ];
}

function accessTokenClaims(token: string): { realm_access?: { roles?: unknown } } | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(atob(padded)) as { realm_access?: { roles?: unknown } };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const syncUser = (next: User | null) => setUser(next && !next.expired ? next : null);
    const clearUser = () => syncUser(null);
    manager.events.addUserLoaded(syncUser);
    manager.events.addUserUnloaded(clearUser);
    manager.events.addSilentRenewError(clearUser);

    const initialize = async () => {
      try {
        const next = await loadInitialUser();
        syncUser(next);
      } catch (cause) {
        console.error("OIDC session initialization failed", cause);
        setError("The secure session could not be restored. Please sign in again.");
        window.history.replaceState({}, document.title, "/");
      } finally {
        setLoading(false);
      }
    };
    void initialize();

    return () => {
      manager.events.removeUserLoaded(syncUser);
      manager.events.removeUserUnloaded(clearUser);
      manager.events.removeSilentRenewError(clearUser);
    };
  }, []);

  const login = useCallback(
    () => manager.signinRedirect({ state: { returnTo: window.location.pathname } }),
    [],
  );
  const logout = useCallback(() => manager.signoutRedirect(), []);
  const roles = useMemo(() => userRoles(user), [user]);
  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      authenticated: Boolean(user && !user.expired),
      error,
      accessToken: user?.access_token ?? "",
      displayName: user?.profile.name ?? user?.profile.preferred_username ?? "ResolveAI user",
      email: user?.profile.email ?? "",
      roles,
      login,
      logout,
      hasAnyRole: (allowed) => allowed.length === 0 || allowed.some((role) => roles.includes(role)),
    }),
    [loading, error, user, roles, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
