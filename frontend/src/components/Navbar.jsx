import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const linkClass = ({ isActive }) =>
    `text-sm transition-colors ${isActive ? "text-slate-50" : "text-slate-400 hover:text-slate-200"}`;

  return (
    <header className="border-b border-surface-border bg-surface-raised">
      <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
        <span className="text-sm font-semibold tracking-tight text-slate-50">
          Interview Assistant
        </span>
        <nav className="flex items-center gap-5">
          <NavLink to="/home" className={linkClass}>
            Home
          </NavLink>
          <NavLink to="/assistant" className={linkClass}>
            Assistant
          </NavLink>
          <NavLink to="/history" className={linkClass}>
            History
          </NavLink>
          <NavLink to="/dashboard" className={linkClass}>
            Profile
          </NavLink>
          <NavLink to="/change-password" className={linkClass}>
            Password
          </NavLink>
          {user && (
            <span className="hidden text-sm text-slate-500 sm:inline">{user.name}</span>
          )}
          <button
            onClick={handleLogout}
            className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-red-500/40 hover:text-red-400"
          >
            Log out
          </button>
        </nav>
      </div>
    </header>
  );
}
