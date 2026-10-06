/** Top navigation bar and the per-repository sub navigation. */
import { Link, NavLink } from "react-router-dom";
import type { RepoInfo } from "../types";
import { StatusBadge } from "./ui";

export function NavBar() {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">
          <span className="brand-mark">R</span> Repo Analysis Tool
        </Link>
        <nav className="nav-links">
          <NavLink to="/" end className="nav-link">
            Repositories
          </NavLink>
        </nav>
        <div className="nav-spacer" />
        <span className="faint small">Streamed git indexing · SQLite metrics</span>
      </div>
    </header>
  );
}

/** Breadcrumb + page links shown on repo-scoped pages. */
export function RepoNav({ repo, active }: { repo: RepoInfo; active: "dashboard" | "authors" }) {
  return (
    <div className="row wrap" style={{ marginBottom: 14 }}>
      <Link to="/" className="muted small">
        ← All repositories
      </Link>
      <span className="nav-sep">/</span>
      <span className="nav-repo">{repo.name}</span>
      <StatusBadge status={repo.status} />
      <div className="nav-spacer" />
      <nav className="nav-links">
        <NavLink
          to={`/repos/${repo.id}/dashboard`}
          className={({ isActive }) => `nav-link${isActive || active === "dashboard" ? " active" : ""}`}
        >
          Dashboard
        </NavLink>
        <NavLink
          to={`/repos/${repo.id}/authors`}
          className={({ isActive }) => `nav-link${isActive || active === "authors" ? " active" : ""}`}
        >
          Author merging
        </NavLink>
      </nav>
    </div>
  );
}
