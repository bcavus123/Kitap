import { Outlet, Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <>
      <div className="header">
        <Link to="/" className="brand">
          Kitap Yazma<span className="badge">v2.1</span>
        </Link>
        <div className="spacer" />
        <span className="muted">
          {user?.email} · {user?.plan}
        </span>
        <button className="btn ghost" onClick={logout}>
          Çıkış
        </button>
      </div>
      <div className="container">
        <Outlet />
      </div>
    </>
  );
}
