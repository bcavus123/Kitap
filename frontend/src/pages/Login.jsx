import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("demo@kitap.test");
  const [password, setPassword] = useState("sifre1234");
  const [fullName, setFullName] = useState("Demo Yazar");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "register") await register(email, password, fullName);
      await login(email, password);
      nav("/");
    } catch (ex) {
      setErr(ex.message || "Hata");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container" style={{ maxWidth: 420 }}>
      <div className="card" style={{ marginTop: 60 }}>
        <h2>Kitap Yazma</h2>
        <div className="tabs">
          <button className={"btn " + (mode === "login" ? "" : "ghost")} onClick={() => setMode("login")}>
            Giriş
          </button>
          <button className={"btn " + (mode === "register" ? "" : "ghost")} onClick={() => setMode("register")}>
            Kayıt
          </button>
        </div>
        <form onSubmit={submit}>
          {mode === "register" && (
            <>
              <label>Ad Soyad</label>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </>
          )}
          <label>E-posta</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Parola</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {err && <div className="err">{err}</div>}
          <div style={{ marginTop: 14 }}>
            <button className="btn" disabled={busy}>
              {busy ? "…" : mode === "login" ? "Giriş yap" : "Kayıt ol ve gir"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
