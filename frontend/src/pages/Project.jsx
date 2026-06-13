import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, wsUrl } from "../api.js";

export default function Project() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [progress, setProgress] = useState(null);
  const [chapters, setChapters] = useState([]);
  const [exportJobs, setExportJobs] = useState([]);
  const [toc, setToc] = useState("Giriş\nTemel Kavramlar\nYöntem\nBulgular\nSonuç");
  const [viewing, setViewing] = useState(null);
  const [editing, setEditing] = useState(null);
  const [citations, setCitations] = useState([]);
  const [mediaAssets, setMediaAssets] = useState([]);
  const [events, setEvents] = useState([]);
  const [exFormat, setExFormat] = useState("docx");
  const [err, setErr] = useState("");
  const wsRef = useRef(null);

  const loadProject = useCallback(async () => {
    try {
      setProject(await api("GET", "/projects/" + id));
    } catch (e) {
      setErr(e.message);
    }
  }, [id]);
  const loadProgress = useCallback(async () => {
    try {
      setProgress(await api("GET", "/projects/" + id + "/progress"));
    } catch (e) {
      /* sessiz */
    }
  }, [id]);
  const loadChapters = useCallback(async () => {
    try {
      setChapters(await api("GET", "/projects/" + id + "/chapters"));
    } catch (e) {
      /* sessiz */
    }
  }, [id]);
  const loadExports = useCallback(async () => {
    try {
      setExportJobs(await api("GET", "/projects/" + id + "/exports"));
    } catch (e) {
      /* sessiz */
    }
  }, [id]);

  useEffect(() => {
    loadProject();
    loadProgress();
    loadChapters();
    loadExports();
  }, [loadProject, loadProgress, loadChapters, loadExports]);

  // WebSocket — canlı bölüm/export güncellemeleri
  useEffect(() => {
    let ws;
    try {
      ws = new WebSocket(wsUrl(id));
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.event === "ping") return;
        const tag = `${msg.event} · ${msg.status || ""} ${msg.chapter_id ? msg.chapter_id.slice(0, 8) : ""}`;
        setEvents((e) => [tag, ...e].slice(0, 50));
        if (msg.event === "chapter_update") {
          loadChapters();
          loadProgress();
        }
        if (msg.event === "export_done") loadExports();
      };
    } catch {
      /* WS açılamadıysa yoksay */
    }
    return () => {
      try {
        ws && ws.close();
      } catch {
        /* yoksay */
      }
    };
  }, [id, loadChapters, loadProgress, loadExports]);

  async function uploadTOC() {
    setErr("");
    const lines = toc.split("\n").map((s) => s.trim()).filter(Boolean);
    const body = { chapters: lines.map((t, i) => ({ order_index: i + 1, title: t })) };
    try {
      await api("POST", "/projects/" + id + "/chapters/toc", body);
      await loadChapters();
      await loadProgress();
      await loadProject();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function generate(cid) {
    setErr("");
    try {
      await api("POST", "/projects/" + id + "/chapters/" + cid + "/generate", { force: false });
      await loadChapters();
    } catch (e) {
      setErr(e.message);
    }
  }
  async function viewChapter(cid) {
    try {
      const ch = await api("GET", "/projects/" + id + "/chapters/" + cid);
      setViewing(ch);
      // Atıf + media yükle (şu an backend'de liste endpoint'i yok, gelecekte eklenir)
      // setCitations(await api("GET", "/projects/" + id + "/chapters/" + cid + "/citations"));
      // setMediaAssets(await api("GET", "/projects/" + id + "/chapters/" + cid + "/media"));
    } catch (e) {
      setErr(e.message);
    }
  }
  async function editChapter(ch) {
    setEditing({ ...ch });
  }
  async function saveEdit() {
    if (!editing) return;
    setErr("");
    try {
      await api("PATCH", "/projects/" + id + "/chapters/" + editing.id, {
        title: editing.title,
        description: editing.description,
        content: editing.content,
        target_word_count: editing.target_word_count,
      });
      await loadChapters();
      setEditing(null);
    } catch (e) {
      setErr(e.message);
    }
  }
  async function createExport() {
    setErr("");
    try {
      await api("POST", "/projects/" + id + "/exports", { format: exFormat });
      setTimeout(loadExports, 1000);
    } catch (e) {
      setErr(e.message);
    }
  }
  async function pauseResume(action) {
    setErr("");
    try {
      await api("POST", "/projects/" + id + "/" + action);
      await loadProject();
    } catch (e) {
      setErr(e.message);
    }
  }

  if (!project) return <div className="center">Yükleniyor…</div>;

  return (
    <div>
      <Link to="/" className="back muted">
        ← Projeler
      </Link>
      <h2>
        {project.title} <span className={"pill " + project.status}>{project.status}</span>
        <Link to={"/projects/" + id + "/settings"} className="btn ghost" style={{ marginLeft: 12, fontSize: 13 }}>
          Ayarlar
        </Link>
      </h2>

      <div className="grid cols2">
        <div className="card">
          <h3>İlerleme</h3>
          {progress && (
            <>
              <div className="muted">
                Kelime: %{progress.word_pct} · Bölüm: %{progress.chapter_pct}
              </div>
              <div className="bar" style={{ margin: "8px 0" }}>
                <span style={{ width: progress.chapter_pct + "%" }} />
              </div>
              <div className="muted">
                done {progress.chapters_done} · pending {progress.chapters_pending} · error{" "}
                {progress.chapters_error} / {progress.chapter_count}
              </div>
            </>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn ghost" onClick={() => pauseResume("pause")}>
              Duraklat
            </button>
            <button className="btn ghost" onClick={() => pauseResume("resume")}>
              Sürdür
            </button>
            <button
              className="btn ghost"
              onClick={() => {
                loadProject();
                loadProgress();
                loadChapters();
              }}
            >
              Yenile
            </button>
          </div>
          <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
            Ayarlar: {project.settings?.tone_profile} · {project.settings?.audience_level} ·{" "}
            {project.kdp_format} · {project.citation_style}
          </div>
        </div>

        <div className="card">
          <h3>Canlı Olaylar (WebSocket)</h3>
          <div className="list events">
            {events.length === 0 && (
              <div className="muted">Olay bekleniyor… (üretim başlayınca güncellenir)</div>
            )}
            {events.map((e, i) => (
              <div key={i} className="muted">
                {e}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>İçindekiler & Bölümler</h3>
        <label>Her satır bir bölüm başlığı</label>
        <textarea value={toc} onChange={(e) => setToc(e.target.value)} />
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn" onClick={uploadTOC}>
            İçindekileri yükle
          </button>
          <button className="btn ghost" onClick={loadChapters}>
            Bölümleri yenile
          </button>
        </div>
        {err && <div className="err">{err}</div>}
        <div className="list" style={{ marginTop: 12 }}>
          {chapters.map((c) => (
            <div key={c.id} className="item">
              <span className="meta">#{c.order_index}</span>
              <b>{c.title}</b>
              <span className="meta">{c.word_count} kelime</span>
              <span className={"pill " + c.status}>{c.status}</span>
              <span style={{ marginLeft: "auto" }} />
              <button className="btn ghost" onClick={() => viewChapter(c.id)} disabled={!c.content}>
                Gör
              </button>
              <button className="btn ghost" onClick={() => editChapter(c)}>
                Düzenle
              </button>
              <button className="btn" onClick={() => generate(c.id)}>
                Üret
              </button>
            </div>
          ))}
        </div>
        <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
          Not: Gerçek üretim için worker + ANTHROPIC_API_KEY gerekir; aksi halde bölüm "queued" kalır.
        </div>
      </div>

      {viewing && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            {viewing.title}
            <button className="btn ghost" style={{ float: "right" }} onClick={() => setViewing(null)}>
              Kapat
            </button>
          </h3>
          <div className="content-view">{viewing.content || "(içerik yok)"}</div>
          {citations.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Atıflar ({citations.length})</h3>
              <div className="list">
                {citations.map((c, i) => (
                  <div key={i} className="item">
                    <span className="meta">{c.marker}</span>
                    <span>{c.raw_title.slice(0, 80)}</span>
                    <span className={"pill " + c.verification_status}>{c.verification_status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {mediaAssets.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Görseller ({mediaAssets.length})</h3>
              <div className="list">
                {mediaAssets.map((m) => (
                  <div key={m.id} className="item">
                    <span className="meta">{m.asset_type}</span>
                    <span>{m.description || m.s3_path}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {editing && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            Düzenle: {editing.title}
            <button className="btn ghost" style={{ float: "right" }} onClick={() => setEditing(null)}>
              İptal
            </button>
          </h3>
          <label>Başlık</label>
          <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
          <label>Açıklama</label>
          <input
            value={editing.description || ""}
            onChange={(e) => setEditing({ ...editing, description: e.target.value })}
          />
          <label>Hedef kelime</label>
          <input
            type="number"
            value={editing.target_word_count || ""}
            onChange={(e) => setEditing({ ...editing, target_word_count: Number(e.target.value) })}
          />
          <label>İçerik (Markdown)</label>
          <textarea
            value={editing.content || ""}
            onChange={(e) => setEditing({ ...editing, content: e.target.value })}
            style={{ minHeight: 300, fontFamily: "ui-monospace,monospace" }}
          />
          {err && <div className="err">{err}</div>}
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={saveEdit}>
              Kaydet
            </button>
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
            Not: İçerik değişirse user_edit versiyonu oluşturulur (backend).
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Export</h3>
        <div className="row">
          <select value={exFormat} onChange={(e) => setExFormat(e.target.value)} style={{ maxWidth: 140 }}>
            {["docx", "pdf", "epub"].map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          <button className="btn" onClick={createExport}>
            Export oluştur
          </button>
          <button className="btn ghost" onClick={loadExports}>
            Yenile
          </button>
        </div>
        <div className="list" style={{ marginTop: 12 }}>
          {exportJobs.length === 0 && <div className="muted">Henüz export yok.</div>}
          {exportJobs.map((j) => (
            <div key={j.id} className="item">
              <b>{j.format}</b>
              <span className={"pill " + j.status}>{j.status}</span>
              {j.file_size_bytes ? <span className="meta">{j.file_size_bytes} bayt</span> : null}
              <span style={{ marginLeft: "auto" }} />
              {j.presigned_url ? (
                <a href={j.presigned_url} target="_blank" rel="noreferrer">
                  indir
                </a>
              ) : (
                <span className="muted">—</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
