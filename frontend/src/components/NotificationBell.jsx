import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState([]);
  const [unseen, setUnseen] = useState(0);
  const panelRef = useRef(null);

  const refresh = useCallback(() => {
    api("/notifications")
      .then((r) => {
        setNotes(r.notifications || []);
        setUnseen(r.unseen_count || 0);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    function onClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function markSeen(note) {
    if (note.seen) return;
    try {
      await api("/notifications/" + note.id + "/seen", { method: "POST" });
      refresh();
    } catch (e) { /* keep the panel usable even if one call fails */ }
  }

  return (
    <div className="bell-wrap" ref={panelRef}>
      <button className="bell" onClick={() => setOpen((o) => !o)} aria-label="Notifications">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {unseen > 0 && <span className="bell-badge">{unseen}</span>}
      </button>
      {open && (
        <div className="bell-panel">
          <p className="muted bell-head">In-app alerts (simulated)</p>
          {notes.length === 0 && <div className="empty">No notifications yet.</div>}
          {notes.slice(0, 20).map((n) => (
            <button
              key={n.id}
              className={"bell-item" + (n.seen ? "" : " unseen")}
              onClick={() => markSeen(n)}
            >
              <strong>{n.title}</strong>
              <span>{n.body}</span>
              <small>{n.created_at ? new Date(n.created_at).toLocaleString("en-IN") : ""}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
