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
        {user?.role === "admin" && (
          <Link to="/admin" className="muted" style={{ marginRight: 12 }}>
            Admin
          </Link>
        )}
        <a href="/docs" target="_blank" className="muted" style={{ marginRight: 12 }}>
          Swagger
        </a>
        <a href="http://localhost:5555" target="_blank" className="muted" style={{ marginRight: 12 }}>
          Flower
        </a>
        <a href="http://localhost:9001" target="_blank" className="muted" style={{ marginRight: 12 }}>
          MinIO
        </a>
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
