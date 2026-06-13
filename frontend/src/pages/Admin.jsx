import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Admin() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const r = await api("GET", "/admin/dead-letter");
      setItems(r.items || []);
    } catch (e) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function requeue(cid) {
    setErr("");
    try {
      await api("POST", "/admin/dead-letter/" + cid + "/requeue");
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function drop(cid) {
    setErr("");
    try {
      await api("DELETE", "/admin/dead-letter/" + cid);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h2>Admin — Dead-Letter Yönetimi</h2>
      <div className="card">
        <h3>
          Başarısız görevler ({items.length})
          <button className="btn ghost" style={{ float: "right", margin: 0 }} onClick={load}>
            Yenile
          </button>
        </h3>
        {err && <div className="err">{err}</div>}
        <div className="list">
          {items.length === 0 && <div className="muted">Dead-letter listesi boş.</div>}
          {items.map((item, i) => (
            <div key={i} className="item">
              <span className="meta">{item.chapter_id.slice(0, 8)}</span>
              <span className="muted" style={{ fontSize: 12 }}>
                {item.error.slice(0, 60)}
              </span>
              <span style={{ marginLeft: "auto" }} />
              <button className="btn ghost" onClick={() => requeue(item.chapter_id)}>
                Requeue
              </button>
              <button className="btn ghost" onClick={() => drop(item.chapter_id)}>
                Sil
              </button>
            </div>
          ))}
        </div>
        <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
          Not: Redis erişilemezse liste boş görünür (guarded).
        </div>
      </div>
    </div>
  );
}
