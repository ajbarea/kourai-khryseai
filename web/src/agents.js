// Agent registry — names, roles, glyphs (emoji fallback), and accent colors.
// Single source of truth for the web GUI's per-maiden presentation.
export const AGENTS = {
  hephaestus: { name: "Hephaestus", role: "Forge Master", glyph: "🔥", color: "#e2562b", pipeline: false },
  metis:      { name: "Metis",      role: "Planner",      glyph: "📐", color: "#5b9bff", pipeline: true },
  techne:     { name: "Techne",     role: "Coder",        glyph: "⚙️", color: "#e0962f", pipeline: true },
  dokimasia:  { name: "Dokimasia",  role: "Tester",       glyph: "🧪", color: "#46b977", pipeline: true },
  kallos:     { name: "Kallos",     role: "Stylist",      glyph: "✨", color: "#cf86ec", pipeline: true },
  mneme:      { name: "Mneme",      role: "Scribe",       glyph: "📜", color: "#4ec5c5", pipeline: true },
  puck:       { name: "Puck",       role: "Guide",        glyph: "🎭", color: "#9bd07a", pipeline: false },
  cupid:      { name: "Cupid",      role: "Romance",      glyph: "💘", color: "#ff7eb0", pipeline: false },
  aidos:      { name: "Aidos",      role: "Anti-Slop",    glyph: "🪞", color: "#b8b0a0", pipeline: false },
  aletheia:   { name: "Aletheia",   role: "Research",     glyph: "📚", color: "#d8b24a", pipeline: false },
};

// The default forge pipeline, in order.
export const PIPELINE = ["metis", "techne", "dokimasia", "kallos", "mneme"];

const NAMES = Object.keys(AGENTS);

// Best-effort: find which maiden a status line is about (mirrors the bridge's tracker).
export function agentFromText(text) {
  const lower = String(text || "").toLowerCase();
  for (const id of NAMES) {
    if (lower.includes(id)) return id;
  }
  return null;
}
