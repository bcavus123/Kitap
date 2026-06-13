import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [title, setTitle] = useState("Yapay Zeka ve Toplum");
  const [format, setFormat] = useState("6x9");
  const [cite, setCite] = useState("APA");
  const [words, setWords] = useState(60000);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const r = await api("GET", "/projects");
      setProjects(r.items || []);
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e) {
    e.preventDefault();
    setErr("");
    try {
      await api("POST", "/projects", {
        title,
        kdp_format: format,
        citation_style: cite,
        language: "tr",
        target_word_count: Number(words),
      });
      await load();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div className="grid cols2">
      <div className="card">
        <h3>Yeni Proje</h3>
        <form onSubmit={create}>
          <label>Başlık</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="row">
            <div style={{ flex: 1 }}>
              <label>KDP Format</label>
              <select value={format} onChange={(e) => setFormat(e.target.value)}>
                {["6x9", "5x8", "7x10", "8.5x11"].map((f) => (
                  <option key={f}>{f}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label>Atıf</label>
              <select value={cite} onChange={(e) => setCite(e.target.value)}>
                {["APA", "Chicago", "MLA", "Vancouver", "Harvard"].map((f) => (
                  <option key={f}>{f}</option>
                ))}
              </select>
            </div>
          </div>
          <label>Hedef kelime</label>
          <input type="number" value={words} onChange={(e) => setWords(e.target.value)} />
          {err && <div className="err">{err}</div>}
          <div style={{ marginTop: 12 }}>
            <button className="btn">Oluştur</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h3>Projelerim ({projects.length})</h3>
        <div className="list">
          {projects.length === 0 && <div className="muted">Henüz proje yok.</div>}
          {projects.map((p) => (
            <Link key={p.id} to={"/projects/" + p.id} className="item">
              <b>{p.title}</b>
              <span className="meta">
                {p.kdp_format} · {p.chapter_count} bölüm
              </span>
              <span className={"pill " + p.status} style={{ marginLeft: "auto" }}>
                {p.status}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
