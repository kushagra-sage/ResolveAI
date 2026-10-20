import type { ReactNode } from "react";
import { KeyRound, LoaderCircle, ShieldCheck, Sparkles } from "../components/Icons";
import { useAuth } from "./AuthProvider";

export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (auth.loading) {
    return <main className="auth-screen"><LoaderCircle className="spin" size={30} /><h1>Restoring secure session</h1></main>;
  }
  if (auth.authenticated) return children;

  return <main className="auth-screen">
    <section className="auth-card">
      <div className="auth-brand"><span>R</span><div><strong>ResolveAI</strong><small>Operations control plane</small></div></div>
      <p className="eyebrow">SECURE WORKSPACE</p>
      <h1>Sign in to resolve with evidence.</h1>
      <p>Keycloak Authorization Code flow with PKCE protects this local workspace. Your role controls which operational surfaces and actions are available.</p>
      {auth.error && <div className="inline-error" role="alert">{auth.error}</div>}
      <button className="button primary auth-login" onClick={() => void auth.login()}><KeyRound size={17} /> Sign in with Keycloak</button>
      <div className="auth-assurance"><ShieldCheck size={18} /><span><strong>No pasted bearer tokens</strong><small>Short-lived access tokens, automatic renewal, and server-side authorization.</small></span></div>
      <div className="auth-demo"><Sparkles size={16} /><span>Local demo users: customer, agent, supervisor, or admin</span><code>password: resolveai-local</code></div>
    </section>
  </main>;
}
