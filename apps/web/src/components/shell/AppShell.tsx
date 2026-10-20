import { useEffect, useMemo, useState } from "react";
import { Command, LogOut, Menu, Moon, Search, Sun, X } from "../Icons";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useUiStore } from "../../store/ui";
import { allNavigation, navigation } from "./navigation";
import { useAuth } from "../../auth/AuthProvider";

export function AppShell() {
  const { theme, setTheme, sidebarOpen, toggleSidebar, setSidebarOpen, paletteOpen, setPaletteOpen } = useUiStore();
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const permittedNavigation = useMemo(
    () => navigation.map((group) => ({
      ...group,
      items: group.items.filter((item) => !item.roles || auth.hasAnyRole(item.roles)),
    })).filter((group) => group.items.length > 0),
    [auth],
  );
  const permittedItems = useMemo(() => permittedNavigation.flatMap((group) => group.items), [permittedNavigation]);
  const active = allNavigation.find((item) => item.path === location.pathname);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(!paletteOpen);
      }
      if (event.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [paletteOpen, setPaletteOpen]);

  const results = useMemo(
    () => permittedItems.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())).slice(0, 8),
    [query, permittedItems],
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <span className="sky-cloud cloud-one" aria-hidden="true" />
      <span className="sky-cloud cloud-two" aria-hidden="true" />
      <span className="sky-cloud cloud-three" aria-hidden="true" />
      <div className={`sidebar-scrim ${sidebarOpen ? "visible" : ""}`} onClick={() => setSidebarOpen(false)} />
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand-lockup">
          <span className="brand-mark">R</span>
          <div><strong>ResolveAI</strong><small>Operations control plane</small></div>
          <button className="sidebar-close icon-button" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {permittedNavigation.map((group) => (
            <section key={group.label}>
              <p>{group.label}</p>
              {group.items.map(({ label, path, icon: Icon }) => (
                <NavLink key={path} to={path} end={path === "/"} onClick={() => setSidebarOpen(false)}>
                  <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
                </NavLink>
              ))}
            </section>
          ))}
        </nav>
        <div className="environment"><span /> Local environment<small>Synthetic data only</small></div>
      </aside>

      <main className="main-column" id="main-content" tabIndex={-1}>
        <header className="topbar">
          <div className="floating-nav">
            <NavLink to="/" className="top-brand"><span className="brand-spark">R</span><strong>ResolveAI</strong></NavLink>
            <nav className="top-links" aria-label="Product navigation">
              <NavLink to="/" end>Overview</NavLink>
              <NavLink to="/resolution">Resolve</NavLink>
              <NavLink to="/signals">Intelligence</NavLink>
              <NavLink to="/traces">AI operations</NavLink>
              <NavLink to="/policies">Governance</NavLink>
            </nav>
            <div className="topbar-actions">
              <button className="search-trigger" onClick={() => setPaletteOpen(true)} aria-label="Search workspace"><Search size={16} /><span>Search</span><kbd>⌘K</kbd></button>
              <span className="live-environment"><i /> {auth.roles[0]?.replaceAll("_", " ") ?? "Local"}</span>
              <button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle theme">
                {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              </button>
              <button className="nav-menu-button" onClick={toggleSidebar} aria-label="Open all product areas"><Menu size={18} /></button>
              <button className="icon-button" onClick={() => void auth.logout()} aria-label={`Sign out ${auth.displayName}`}><LogOut size={17} /></button>
            </div>
          </div>
        </header>
        <div className="page-breadcrumb"><span>ACME COMMERCE</span><i>/</i><strong>{active?.label ?? "ResolveAI"}</strong><div className="operator-avatar" title={auth.displayName}>{initials(auth.displayName)}</div></div>
        <div className="page-container"><Outlet /></div>
      </main>

      {paletteOpen && (
          <div className="command-layer" onMouseDown={() => setPaletteOpen(false)}>
            <div className="command-palette" role="dialog" aria-modal="true" aria-label="Navigate workspace" onMouseDown={(event) => event.stopPropagation()}>
              <label><Command size={18} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Navigate to a workspace…" /></label>
              <div className="command-results">
                {results.map(({ label, path, icon: Icon }) => <button key={path} onClick={() => { navigate(path); setPaletteOpen(false); setQuery(""); }}><Icon size={17} /><span>{label}</span><small>Open</small></button>)}
              </div>
            </div>
          </div>
      )}
    </div>
  );
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "RA";
}
