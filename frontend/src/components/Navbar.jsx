import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "./Icon.jsx";
import ThaliMark from "./ThaliMark.jsx";

const APP_LINKS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/generate", label: "Generate plan" },
  { to: "/plans", label: "Saved plans" },
  { to: "/files", label: "Cloud files" },
  { to: "/profile", label: "Profile" },
];

export default function Navbar() {
  const { status, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const authenticated = status === "authenticated";

  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <header className="topbar">
      <div className="topbar__inner container">
        <Link to={authenticated ? "/dashboard" : "/"} className="brand">
          <ThaliMark />
          <span className="brand__name">AI Diet Planner</span>
        </Link>

        {authenticated ? (
          <>
            <button
              type="button"
              className="topbar__toggle"
              aria-expanded={open}
              aria-controls="primary-nav"
              onClick={() => setOpen((value) => !value)}
            >
              <Icon name={open ? "x" : "menu"} />
              <span className="sr-only">Menu</span>
            </button>
            <nav id="primary-nav" className={`topbar__nav${open ? " is-open" : ""}`} aria-label="Main">
              {APP_LINKS.map((link) => (
                <NavLink key={link.to} to={link.to} className="topbar__link">
                  {link.label}
                </NavLink>
              ))}
              <button type="button" className="btn btn--ghost btn--small topbar__logout" onClick={logout}>
                <Icon name="logout" size={16} />
                Log out
              </button>
            </nav>
          </>
        ) : (
          <nav className="topbar__nav topbar__nav--public" aria-label="Account">
            <NavLink to="/login" className="topbar__link">
              Log in
            </NavLink>
            <Link to="/register" className="btn btn--primary btn--small">
              Create account
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
