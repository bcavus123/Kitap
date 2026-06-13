import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";

export default function Settings() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [settings, setSettings] = useState(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [p, s] = await Promise.all([
          api("GET", "/projects/" + id),
          api("GET", "/projects/" + id + "/settings"),
        ]);
        setProject(p);
        setSettings(s);
      } catch (e) {
        setErr(e.message);
      }
    })();
  }, [id]);

  async function save(e) {
    e.preventDefault();
    setErr("");
    setOk(false);
    try {
      await api("PATCH", "/projects/" + id + "/settings", settings);
      setOk(true);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  if (!settings) return <div className="center">Yükleniyor…</div>;

  return (
    <div>
      <Link to={"/projects/" + id} className="back muted">
        ← {project?.title || "Proje"}
      </Link>
      <h2>Ayarlar</h2>
      <div className="card">
        <form onSubmit={save}>
          <div className="grid cols2">
            <div>
              <label>Yazı tonu</label>
              <select
                value={settings.tone_profile}
                onChange={(e) => setSettings({ ...settings, tone_profile: e.target.value })}
              >
                {["academic", "formal", "conversational", "technical", "narrative"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Hedef kitle</label>
              <select
                value={settings.audience_level}
                onChange={(e) => setSettings({ ...settings, audience_level: e.target.value })}
              >
                {["undergraduate", "graduate", "professional", "general"].map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <label>
            <input
              type="checkbox"
              checked={settings.human_writing_mode}
              onChange={(e) => setSettings({ ...settings, human_writing_mode: e.target.checked })}
            />{" "}
            İnsan yazısı modu (cümle çeşitliliği, doğal akış)
          </label>
          <div className="muted" style={{ fontSize: 12, marginTop: 12 }}>
            LLM config (JSON): model, temperature, max_tokens (proje seviyesinde, .env üstüne)
          </div>
          <label>llm_config (isteğe bağlı JSON)</label>
          <textarea
            value={JSON.stringify(settings.llm_config || {}, null, 2)}
            onChange={(e) => {
              try {
                setSettings({ ...settings, llm_config: JSON.parse(e.target.value) });
              } catch {
                /* geçersiz JSON yoksay */
              }
            }}
            style={{ fontFamily: "ui-monospace,monospace", fontSize: 12 }}
          />
          {err && <div className="err">{err}</div>}
          {ok && <div style={{ color: "var(--ok)", marginTop: 8 }}>✓ Kaydedildi.</div>}
          <div style={{ marginTop: 14 }}>
            <button className="btn">Kaydet</button>
          </div>
        </form>
      </div>
    </div>
  );
}
