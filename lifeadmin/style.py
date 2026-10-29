"""LifeAdmin look & feel: theme CSS, inline SVG icons and small HTML components.

Everything visual lives here so app.py can stay about behaviour. The layout
follows the screen designs in the project document (Figures 2-4): dark navy
canvas, left navigation, rounded cards, coloured status pills.
"""
from __future__ import annotations

import base64
import calendar
import html as _html
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

import streamlit as st

# ---------------------------------------------------------------- palette
C = {"bg":"#0B0B10", "panel":"#15151C", "panel2":"#1D1D26", "line":"#272732",
     "text":"#F2F2F7", "muted":"#8A8A99", "indigo":"#8E92FF", "indigo2":"#8E92FF",
     "green":"#8E92FF", "amber":"#F5C66B", "red":"#FF6B6B", "blue":"#8E92FF", "slate":"#8A8A99"}
PILL = {kind:(label, color, "#1D1D26") for kind,label,color in [
    ("active","Active","#8E92FF"), ("warning","Due soon","#F5C66B"),
    ("critical","Critical","#FF6B6B"), ("expired","Overdue","#FF6B6B"),
    ("none","No expiry","#8A8A99"), ("processed","Processed","#8E92FF"),
    ("pending","Pending","#F5C66B"), ("completed","Handled","#8E92FF"),
    ("upcoming","Upcoming","#8E92FF")]}

# ---------------------------------------------------------------- icons
# Stroke icons on a 24x24 grid.
_ICON_PATHS: Dict[str, str] = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    "upload": '<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M12 12v9"/><path d="m16 16-4-4-4 4"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
    "files": '<path d="M15 2H8a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/><path d="M15 2v5h5"/><path d="M4 7v13a2 2 0 0 0 2 2h10"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 7.5v5"/><path d="M12 16.5h.01"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "car": '<path d="M5 17H3v-5l2-5h14l2 5v5h-2"/><path d="M3 12h18"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/><path d="M9.5 17h5"/>',
    "id": '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><path d="M14 10h4"/><path d="M14 14h4"/><path d="M5 16c.6-1.2 1.7-1.8 3-1.8s2.4.6 3 1.8"/>',
    "cap": '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/><path d="M22 10v6"/>',
    "receipt": '<path d="M5 2h14v20l-2.3-1.5L14.3 22 12 20.5 9.7 22l-2.4-1.5L5 22z"/><path d="M9 7h6"/><path d="M9 11h6"/><path d="M9 15h4"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"/>',
    "repeat": '<path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
    "sparkle": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    "list": '<path d="M9 6h12"/><path d="M9 12h12"/><path d="M9 18h12"/><path d="M4 6h.01"/><path d="M4 12h.01"/><path d="M4 18h.01"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M8 17V11"/><path d="M13 17V7"/><path d="M18 17v-4"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
}

TYPE_STYLE: Dict[str, Tuple[str, str]] = {kind: (name, "#8E92FF") for kind, name in {
    "ID":"id", "Insurance":"shield", "Vehicle":"car", "Certificate":"cap",
    "Bill":"receipt", "Warranty":"wrench", "Subscription":"repeat", "Other":"file"}.items()}


def esc(s: object) -> str:
    return _html.escape(str(s if s is not None else ""))


def icon(name: str, size: int = 18, color: str = "currentColor", stroke: float = 1.8) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="flex-shrink:0">{_ICON_PATHS[name]}</svg>')


def icon_tile(name: str, color: str, size: int = 40, radius: int = 11, icon_size: int = 20,
              solid: bool = False) -> str:
    bg = color if solid else _alpha(color, 0.16)
    fg = "#fff" if solid else color
    return (f'<div class="la-tile" style="width:{size}px;height:{size}px;border-radius:{radius}px;'
            f'background:{bg};color:{fg}">{icon(name, icon_size, fg)}</div>')


def type_tile(doc_type: str, size: int = 40) -> str:
    name, color = TYPE_STYLE.get(doc_type, TYPE_STYLE["Other"])
    return icon_tile(name, color, size)


def file_badge(filename: str, size: int = 30) -> str:
    """Small coloured file glyph: red PDF, blue image, Word, Excel, text."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    _, label = {
        "pdf": ("#EF4444", "PDF"), "png": ("#3B82F6", ""), "jpg": ("#3B82F6", ""),
        "jpeg": ("#3B82F6", ""), "docx": ("#2563EB", "W"), "xlsx": ("#16A34A", "X"),
        "txt": ("#64748B", "TXT"),
    }.get(ext, ("#64748B", ""))
    color = C["indigo"]
    h = size
    w = round(size * 0.8)
    inner = (f'<text x="12" y="17.2" text-anchor="middle" font-size="{6 if len(label) > 1 else 8}" '
             f'font-weight="800" fill="#fff" font-family="Inter,Arial">{label}</text>' if label else
             '<circle cx="9.5" cy="11" r="1.6" fill="#fff"/><path d="M5.5 19l4.5-4.5 2.5 2.5 2.5-3 3.5 5z" fill="#fff"/>')
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 24 28" style="flex-shrink:0">'
            f'<path d="M3 2.5A2.5 2.5 0 0 1 5.5 0H15l6 6v19.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 25.5z" fill="{color}"/>'
            f'<path d="M15 0v4.5A1.5 1.5 0 0 0 16.5 6H21z" fill="#fff" fill-opacity=".45"/>{inner}</svg>')


def _alpha(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def pill(kind: str, label: Optional[str] = None) -> str:
    text, fg, bg = PILL.get(kind, PILL["none"])
    return f'<span class="la-pill" style="color:{fg};background:{bg}">{esc(label or text)}</span>'


# ---------------------------------------------------------------- brand art
LOGO_SVG = (
    '<svg width="34" height="34" viewBox="0 0 48 48" aria-hidden="true">'
    '<defs><linearGradient id="lg-oct" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#8E92FF"/><stop offset="1" stop-color="#8E92FF"/></linearGradient></defs>'
    '<path fill="url(#lg-oct)" d="M24 3C15.7 3 10 9 10 16.5c0 4.4 1.9 7.6 4.6 9.6L10.2 33c-1.2 1.9-3.4 2.4-5 1.6 '
    '1 2.6 4.6 3.4 7 1.4l4.4-5.2-1.2 7.4c-.4 2-2 3.3-3.8 3.4 2.2 1.6 5.6.8 6.6-1.9L20.4 32l1.2 9.4c.2 1.4 1.1 '
    '2.6 2.4 2.6s2.2-1.2 2.4-2.6l1.2-9.4 2.2 7.8c1 2.7 4.4 3.5 6.6 1.9-1.8-.1-3.4-1.4-3.8-3.4l-1.2-7.4 4.4 5.2c2.4 '
    '2 6 1.2 7-1.4-1.6.8-3.8.3-5-1.6l-4.4-6.9c2.7-2 4.6-5.2 4.6-9.6C38 9 32.3 3 24 3z"/>'
    '<ellipse cx="19" cy="16" rx="3.2" ry="3.6" fill="#fff"/><ellipse cx="29" cy="16" rx="3.2" ry="3.6" fill="#fff"/>'
    '<circle cx="19.6" cy="16.8" r="1.6" fill="#1B1F3B"/><circle cx="29.6" cy="16.8" r="1.6" fill="#1B1F3B"/>'
    '<path d="M21 22.5c1.8 1.3 4.2 1.3 6 0" stroke="#15151C" stroke-width="1.4" fill="none" stroke-linecap="round"/>'
    '</svg>'
)

MOUNTAIN_SVG = (
    '<svg class="la-mtn" viewBox="0 0 360 120" preserveAspectRatio="xMaxYMax slice" aria-hidden="true">'
    '<defs><linearGradient id="m1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3A3F9E"/>'
    '<stop offset="1" stop-color="#1A1E5A"/></linearGradient>'
    '<linearGradient id="m2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4C52C9"/>'
    '<stop offset="1" stop-color="#232877"/></linearGradient></defs>'
    '<path d="M0 120 L70 62 L120 92 L190 40 L250 85 L300 55 L360 90 L360 120Z" fill="url(#m1)" opacity=".75"/>'
    '<path d="M120 120 L215 52 L262 86 L300 66 L360 104 L360 120Z" fill="url(#m2)"/>'
    '<path d="M300 66 L300 34" stroke="#C7CAFF" stroke-width="2"/><path d="M300 34 L318 40 L300 46Z" fill="#7C7FFA"/>'
    '<circle cx="246" cy="22" r="1.2" fill="#C7CAFF"/><circle cx="272" cy="10" r="1" fill="#C7CAFF"/>'
    '<circle cx="318" cy="26" r="1.3" fill="#C7CAFF"/><circle cx="344" cy="12" r="1" fill="#C7CAFF"/></svg>'
)

# ---------------------------------------------------------------- CSS
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0B0B10;--surface:#15151C;--surface-2:#1D1D26;--border:#272732;--text:#F2F2F7;--muted:#8A8A99;--faint:#5A5A68;--accent:#8E92FF;--accent-soft:rgba(142,146,255,.14);--on-accent:#0B0B10;--la-bg:var(--bg);--la-panel:var(--surface);--la-panel2:var(--surface-2);--la-line:var(--border);--la-text:var(--text);--la-muted:var(--muted);--la-indigo:var(--accent)}
html,body,.stApp,button,input,textarea,select{font-family:Inter,system-ui,sans-serif!important;font-size:15px;font-weight:500}
.stApp{background:var(--bg);color:var(--text)}
#MainMenu,footer,header[data-testid=stHeader],[data-testid=stToolbar],[data-testid=stDecoration],[data-testid=stStatusWidget],[data-testid=stSidebarCollapseButton],[data-testid=stSidebarCollapsedControl]{display:none!important}
[data-testid=stMain]{margin-left:240px;min-width:0;width:calc(100% - 240px)!important;max-width:calc(100% - 240px)!important;flex:none!important}
.block-container,[data-testid=stMainBlockContainer]{max-width:1344px;padding:32px 32px 48px!important;margin:auto}
[data-testid=stVerticalBlock]{gap:16px}
h1,h2,h3,h4{color:var(--text)!important;letter-spacing:-.02em}h1{font-size:clamp(26px,2.2vw,34px)!important;font-weight:700!important}h2{font-size:24px!important}h3{font-size:20px!important}
p,li{line-height:1.6}a{color:var(--accent)}svg{flex-shrink:0}*{box-sizing:border-box}
[data-testid=stIconMaterial],span[role=img][translate=no]{font-family:'Material Symbols Rounded'!important}
:focus-visible{outline:2px solid var(--accent)!important;outline-offset:4px}
.la-eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:8px}
.la-mono{font-family:'JetBrains Mono',monospace!important;color:var(--accent);font-size:12px;letter-spacing:.03em}
.la-sub{font-size:13px;color:var(--muted);line-height:1.6}.la-empty{padding:32px 8px;color:var(--muted);text-align:center;font-size:14px}
/* Persistent rail, compact rail and bottom navigation use the same native radio routing. */
[data-testid=stSidebar]{position:fixed!important;inset:0 auto 0 0!important;transform:none!important;visibility:visible!important;width:240px!important;min-width:240px!important;max-width:240px!important;background:var(--bg)!important;border-right:1px solid var(--border);z-index:1001}
[data-testid=stSidebarHeader]{display:none!important}[data-testid=stSidebarContent]{height:100%;padding:0!important}.st-key-nav{width:100%!important}[data-testid=stSidebarUserContent]{padding:32px 20px 20px!important;height:100dvh;overflow:auto}
[data-testid=stSidebarUserContent]>div,[data-testid=stSidebarUserContent]>div>[data-testid=stVerticalBlock]{min-height:100%;height:100%;display:flex;flex-direction:column}
.st-key-sidebar_footer{padding-top:32px}[data-testid=stSidebarUserContent] [data-testid=stLayoutWrapper]:has(>.st-key-sidebar_footer){margin-top:auto!important}.la-brand{display:flex;gap:10px;align-items:center;padding:4px 4px 40px}.la-brand span{font-size:22px;font-weight:800;letter-spacing:-.06em}.la-brand svg{width:30px;height:30px}
.la-user{display:flex;gap:10px;align-items:center;margin:0 0 12px;min-width:0}.la-user b{font-size:13px;display:block}.la-user small{color:var(--muted);font-size:11px}.la-user-icon{width:36px;height:36px;background:var(--accent-soft);border:1px solid var(--border);border-radius:12px;display:grid;place-items:center;color:var(--accent);font-size:12px}
.la-motto{font-size:11px;color:var(--muted);padding:20px 4px 0}.la-motto br{display:none}.la-motto i{display:none}
[data-testid=stSidebar] [role=radiogroup]{gap:8px;width:100%}[data-testid=stSidebar] [role=radiogroup]>div{width:100%}
[data-testid=stSidebar] [role=radiogroup] label{display:flex;width:100%;min-height:48px;margin:0!important;padding:12px 16px;border-radius:14px;color:var(--muted);transition:background .2s,color .2s;position:relative;cursor:pointer}
[data-testid=stSidebar] [role=radiogroup] label p{font-size:14px!important;display:flex;align-items:center;gap:12px;white-space:nowrap;margin:0}
[data-testid=stSidebar] [role=radiogroup] label[data-baseweb=radio]>div:first-child{display:none}
[data-testid=stSidebar] [role=radiogroup] label:hover{background:var(--surface-2);color:var(--text)}
[data-testid=stSidebar] [role=radiogroup] label:has(input:checked){background:var(--accent);color:var(--on-accent);font-weight:700}
[data-testid=stSidebar] [data-testid=stRadio]>label{display:none!important}
[data-testid="stRadioOption"]>div>div:first-child{display:none!important}
/* App header */
.st-key-topbar{padding-bottom:24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.la-head{display:flex;align-items:center;gap:20px;justify-content:space-between;min-width:0}.la-head h1{margin:0;padding:0;line-height:1.15}.la-head p{margin:8px 0 0;color:var(--muted);font-size:13px}
.st-key-topsearch input{font-size:13px!important}.st-key-topsearch [data-baseweb=input]{min-height:48px}
[class*=st-key-bell] button,.st-key-avatar button{min-width:44px;padding:8px!important;background:var(--surface)!important;border:1px solid var(--border)!important}
.st-key-avatar button{display:flex!important;flex-wrap:nowrap!important;gap:0!important}.st-key-avatar button>div{display:none!important}.st-key-avatar button::before{flex-shrink:0;content:var(--avatar);display:grid;place-items:center;width:24px;height:24px;color:var(--accent);font-size:11px;font-weight:700}
.st-key-avatar button p{font-size:0!important}.st-key-avatar button svg{width:12px}
.st-key-bell_on button:after{content:'';width:5px;height:5px;border-radius:50%;background:#F5C66B;position:absolute;top:9px;right:9px}
/* Surfaces and document components */
div[class*=st-key-card_],div[class*=st-key-rem_]{background:var(--surface);border:1px solid var(--border);border-radius:22px;padding:24px!important;animation:rise .45s ease both;min-width:0;transition:transform .2s,border-color .2s}
div[class*=st-key-card_]:hover,div[class*=st-key-rem_]:hover{border-color:rgba(142,146,255,.34);transform:translateY(-2px)}
div[class*=st-key-card_]:nth-child(2){animation-delay:40ms}div[class*=st-key-card_]:nth-child(3){animation-delay:80ms}
.la-card-title{display:flex;align-items:center;gap:10px;font-size:15px;font-weight:600;min-height:28px}.la-card-title svg{color:var(--accent)}
.la-tile{display:flex;align-items:center;justify-content:center;background:var(--surface-2)!important;color:var(--accent)!important;border-radius:14px!important}
.la-pill{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:8px;background:var(--surface-2)!important;font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.la-pill:before{content:'';width:5px;height:5px;border-radius:50%;background:currentColor}.la-head>.la-pill{margin-left:auto}
.la-row{display:flex;align-items:center;gap:14px;min-width:0;padding:17px 0;border-bottom:1px solid var(--border)}.la-row:last-child{border:0}.la-row .main{flex:1;min-width:0}.la-row .t{font-size:14px;font-weight:600;color:var(--text);overflow-wrap:anywhere}.la-row .s{font-size:12px;color:var(--muted);margin-top:5px;display:flex;gap:6px;align-items:center}.la-row .s svg{flex-shrink:0}
.la-doc-row{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:14px;align-items:center;padding:18px 0;border-bottom:1px solid var(--border)}.la-doc-row:last-child{border-bottom:0}.la-doc-row h4{font-size:14px!important;margin:0;overflow-wrap:anywhere}.la-doc-row .note{font-size:12px;color:var(--muted);margin-top:8px;overflow-wrap:anywhere}.la-doc-row .meta{margin-top:6px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.la-fields,.la-sum{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:16px}.la-fields>div,.la-sum>div{padding:14px;border-radius:14px;background:var(--surface-2);min-width:0}.la-fields span,.la-sum span{display:block;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}.la-fields b{font-size:13px;font-weight:500;overflow-wrap:anywhere}.la-sum b{font-family:'Archivo Black',Inter,sans-serif;font-size:24px;color:var(--text)}
.la-health .bar{height:6px;background:var(--surface-2);border-radius:8px;margin:12px 0 16px;overflow:hidden}.la-health .bar i{display:block;height:100%;background:var(--accent)!important}.la-health .ck{display:flex;justify-content:space-between;padding:5px 0;font-size:12px;color:var(--muted)}
/* Score dial and accent summary */
.la-ring{position:relative;width:min(100%,280px);aspect-ratio:1;margin:16px auto 4px;display:grid;place-items:center}.la-ring svg{position:absolute;inset:0;width:100%;height:100%}.la-ring .dial{stroke:var(--accent);stroke-dasharray:var(--score) 100;animation:dial-in .9s ease-out both;transform:rotate(-90deg);transform-origin:center}.la-ring .ring-value{text-align:center}.la-ring .score{font-family:'Archivo Black',Inter,sans-serif;font-size:clamp(56px,6vw,82px);line-height:1.1;letter-spacing:-.07em}.la-ring .scale{position:absolute;bottom:7%;width:72%;display:flex;justify-content:space-between;color:var(--muted);font-size:11px}.la-ring .ring-caption{font-size:10px;color:var(--muted);letter-spacing:.16em;margin-top:8px;text-transform:uppercase}
@property --count{syntax:'<integer>';initial-value:0;inherits:false}.la-count{--count:var(--target);counter-reset:score var(--count);animation:count-up .9s ease-out both}.la-count:after{content:counter(score)}
.la-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.la-summary{background:var(--accent);color:var(--on-accent);border-radius:22px;padding:28px;min-height:230px;display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.la-summary .la-eyebrow,.la-summary .la-sub{color:var(--on-accent);opacity:.75}.la-summary strong{font-family:'Archivo Black',Inter,sans-serif;font-size:clamp(38px,4.6vw,68px);line-height:1.2;letter-spacing:-.06em;display:block;margin:24px 0 8px}.la-summary .next{text-align:right;min-width:90px}.la-summary .next b{display:block;font-family:'Archivo Black',Inter,sans-serif;font-size:26px;margin-top:16px}.la-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.la-stat{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px;min-width:0}.la-stat .value{font-family:'Archivo Black',Inter,sans-serif;font-size:30px;line-height:1.3;margin-top:10px}.la-stat .la-eyebrow{font-size:10px;letter-spacing:.1em}
.la-insight{display:flex;align-items:center;gap:14px;padding:4px 0 24px}.la-insight>b{width:44px;height:44px;border-radius:12px;background:var(--accent-soft);color:var(--accent);display:grid;place-items:center;font-family:'Archivo Black',Inter,sans-serif;flex-shrink:0}.la-insight p{font-size:13px;color:var(--muted);margin:0}
.la-result{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:8px 0 20px}.la-result b{font-family:'Archivo Black',Inter,sans-serif;font-size:32px;letter-spacing:-.04em}.la-result svg{color:var(--accent)}
/* Timeline and calendar */
.la-day-strip{display:grid;grid-template-columns:repeat(7,minmax(58px,1fr));gap:8px;padding:16px 0 4px;overflow-x:auto}.la-day{background:var(--surface-2);border:1px solid transparent;border-radius:14px;min-height:150px;display:flex;align-items:center;flex-direction:column;gap:8px;padding:16px 8px;font-size:12px}.la-day.today{border-color:var(--accent)}.la-day .day-name{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em}.la-day .date{font-family:'Archivo Black',Inter,sans-serif;font-size:22px}.la-day .due-ring{border:2px dashed var(--muted);border-radius:50%;width:24px;height:24px;display:grid;place-items:center;color:var(--muted);font-size:10px}.la-day.handled .due-ring{border-style:solid;border-color:var(--accent);color:var(--accent)}.la-day .today-label{font-size:8px;letter-spacing:.08em;color:var(--accent)}.la-day .day-caption{color:var(--muted);font-size:10px}
.la-year{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-top:20px}.la-month-bar{background:var(--surface-2);border-radius:12px;padding:14px;font-size:12px;color:var(--muted)}.la-month-bar b{display:block;color:var(--text);font-size:22px;margin-top:20px;font-family:'Archivo Black',Inter,sans-serif}.la-month-bar i{display:block;height:3px;margin-top:12px;background:var(--accent);border-radius:2px}
.la-cal{display:table!important;table-layout:fixed;width:100%;border-collapse:separate;border-spacing:4px!important;margin:16px 0 0!important;border:0!important}.la-cal td,.la-cal th{border:0!important;text-align:center!important;background:transparent!important;padding:10px 0!important;font-size:12px;color:var(--muted)}.la-cal th{font-size:10px;text-transform:uppercase;letter-spacing:.06em}.la-cal .n{display:inline-grid;place-items:center;width:32px;height:32px;border-radius:10px;color:var(--text)}.la-cal .today .n{background:var(--accent);color:var(--on-accent);font-weight:700}.la-cal .o .n{color:var(--faint)}.la-cal .dots{display:flex;justify-content:center;gap:3px;height:5px}.la-cal .dots i{display:block;width:4px;height:4px;border-radius:50%}.la-cal-head{font-size:20px;font-weight:600;text-align:center}.st-key-card_calendar_large .la-cal td{height:80px;border:1px solid var(--border)!important;border-radius:12px;background:var(--surface-2)!important}.st-key-card_calendar_large .la-cal th{padding-bottom:16px!important}
.st-key-card_calendar_large button p{font-size:0!important}.st-key-card_docdetail{position:sticky;top:24px}.la-note-content{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;color:var(--text);font-size:14px;margin:16px 0}
/* All native controls follow the same theme, including overlays. */
[data-testid="stTextInputRootElement"],[data-testid="stTextAreaRootElement"],[data-testid="stDateInputRootElement"],[data-testid="stNumberInputContainer"]{background:var(--surface-2)!important;border:1px solid var(--border)!important;border-radius:14px!important;overflow:hidden}
[data-testid="stTextInputRootElement"] input{padding:12px!important}
[data-testid="stTextAreaRootElement"] textarea{padding:14px!important}
.st-key-auth_card [data-testid="stFormSubmitButton"],.st-key-auth_card [data-testid="stFormSubmitButton"] button{width:100%!important}

button[kind],.stButton>button,.stDownloadButton>button,[data-testid=stPopoverButton]{min-height:48px;border-radius:14px!important;border:1px solid var(--border)!important;background:var(--surface-2)!important;color:var(--text)!important;font-weight:600!important;transition:filter .15s,transform .15s,border-color .15s;box-shadow:none!important;overflow-wrap:anywhere}
button[kind]:hover{filter:brightness(1.13);border-color:var(--accent)!important}button[kind]:active{transform:scale(.98)}button[kind=primary],button[kind=primaryFormSubmit]{background:var(--accent)!important;color:var(--on-accent)!important;border-color:transparent!important}button[kind=tertiary]{min-height:36px;border:0!important;background:transparent!important;color:var(--accent)!important;padding:0 4px}
[data-testid=stForm]{padding:20px;border:1px solid var(--border)!important;border-radius:22px!important;background:var(--surface)!important}
[data-baseweb=input],[data-baseweb=base-input],[data-baseweb=textarea],[data-baseweb=select]>div{background:var(--surface-2)!important;border-color:var(--border)!important;border-radius:14px!important;color:var(--text)!important;box-shadow:none!important;min-width:0!important}
input,textarea{color:var(--text)!important;font-size:14px!important}input{min-height:46px}input::placeholder,textarea::placeholder{color:var(--muted)!important}[data-testid=stWidgetLabel] p{font-size:12px;color:var(--muted)}[data-baseweb=checkbox] [data-testid=stMarkdownContainer] p{color:var(--text)}
[data-testid=stFileUploaderDropzone],[data-testid=stFileUploadDropzone]{background:var(--surface-2)!important;border:1px dashed var(--accent)!important;border-radius:18px!important;min-height:250px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:16px;padding:24px!important;text-align:center}
[data-testid=stFileUploaderFile]{border:1px solid var(--border);border-radius:12px;padding:12px}
[data-testid=stButtonGroup]{max-width:100%;overflow:auto} [data-testid=stButtonGroup] button{min-height:40px!important;border-radius:10px!important;background:var(--surface-2)!important;color:var(--muted)!important;border:1px solid var(--border)!important;padding:8px 14px!important}
[data-testid=stButtonGroup] button[aria-checked=true],[data-testid=stButtonGroup] button[aria-selected=true]{background:var(--accent)!important;color:var(--on-accent)!important}
[data-baseweb=tab-list]{gap:12px;border-bottom:1px solid var(--border);background:transparent!important}[data-baseweb=tab]{padding:12px 16px!important;color:var(--muted)!important;background:transparent!important}[aria-selected=true][data-baseweb=tab]{color:var(--accent)!important}[data-baseweb=tab-highlight]{background:var(--accent)!important}
[data-testid=stDataFrame]{border:1px solid var(--border);border-radius:14px;overflow:hidden;max-width:100%}[data-testid=stExpander] details{border:1px solid var(--border)!important;border-radius:14px!important;background:var(--surface)!important}[data-testid=stAlert]{background:var(--surface-2)!important;color:var(--text)!important;border-radius:14px!important;border:1px solid var(--border)!important}[data-testid=stToast]{background:var(--surface)!important;border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:14px;color:var(--text)}[data-baseweb=popover],[data-baseweb=menu]{background:var(--surface)!important;color:var(--text)!important;border-color:var(--border)!important}
.la-extract{display:flex;gap:16px;align-items:center}.la-thumb{width:70px;height:88px;object-fit:cover;object-position:top;border-radius:12px}.la-thumb-ph{width:70px;height:88px;display:grid;place-items:center;background:var(--surface-2);border-radius:12px}
div[class*=st-key-qt],div[class*=st-key-qtsel_]{border:1px solid var(--border);background:var(--surface-2);border-radius:14px;padding:16px 8px!important;text-align:center}div[class*=st-key-qtsel_]{border-color:var(--accent);background:var(--accent-soft)}.la-qt{display:flex;justify-content:center;margin-bottom:8px}
.la-skeleton{height:100px;border-radius:14px;background:linear-gradient(100deg,var(--surface-2) 30%,#2B2B39 50%,var(--surface-2) 70%);background-size:200% 100%;animation:shimmer 1.2s linear infinite}
/* Split sign-in page: the original forms and auth callbacks stay native. */
[data-testid=stMain]:has(.st-key-auth_shell){margin-left:0!important;width:100%!important;max-width:100%!important}.st-key-auth_shell{max-width:1160px;margin:4vh auto}.st-key-auth_card{max-width:460px;margin:40px auto;background:var(--surface);border:1px solid var(--border);padding:32px!important;border-radius:22px}.st-key-auth_card [data-testid=stForm]{padding:0;border:0!important;background:transparent!important}.st-key-auth_card h1{font-size:28px!important}.la-auth-brand{padding:48px 50px 20px 16px}.la-auth-brand .la-brand{padding-bottom:64px}.la-auth-brand h2{font-size:clamp(36px,4vw,56px)!important;line-height:1.12;font-weight:700;letter-spacing:-.05em;max-width:470px;margin-bottom:24px}.la-auth-brand>p{color:var(--muted);max-width:350px;font-size:15px}.la-auth-brand .la-ring{width:250px;margin:32px 0 0}.la-auth-brand .la-pill{margin-top:24px}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}@keyframes dial-in{from{stroke-dasharray:0 100}to{stroke-dasharray:var(--score) 100}}@keyframes count-up{from{--count:0}to{--count:var(--target)}}@keyframes shimmer{to{background-position:-200% 0}}
@media(min-width:768px) and (max-width:1199px){[data-testid=stSidebar]{width:76px!important;min-width:76px!important;max-width:76px!important}[data-testid=stMain]{margin-left:76px;width:calc(100% - 76px)!important;max-width:calc(100% - 76px)!important}[data-testid=stSidebarUserContent]{padding:32px 10px 16px!important}.la-brand{padding:4px 12px 32px}.la-brand span,.la-motto,.la-user>div:not(.la-user-icon),.st-key-sidebar_footer [data-testid=stCaptionContainer]{display:none}.la-user{justify-content:center}[data-testid=stSidebar] label{justify-content:center;padding:12px!important}[data-testid=stSidebar] [role=radiogroup] label p{font-size:0!important;gap:0!important}[data-testid=stSidebar] label [data-testid=stIconMaterial],[data-testid=stSidebar] label span[role=img]{font-size:23px!important}.st-key-sidebar_footer button p{font-size:0!important}.st-key-sidebar_footer button p:after{content:'Exit';font-size:11px}.block-container,[data-testid=stMainBlockContainer]{padding:24px!important}.la-head>.la-pill{display:none}.la-auth-brand{padding:32px 16px}.la-auth-brand h2{font-size:36px!important}}
@media(max-width:1199px){[class*=st-key-layout_]>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]{flex-wrap:wrap!important}[class*=st-key-layout_]>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]>[data-testid=stColumn]{flex:1 1 280px!important;min-width:0!important}.st-key-layout_board>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]>[data-testid=stColumn]{flex-basis:260px!important}.la-stats{gap:8px}.la-stat{padding:16px}.la-stats .la-eyebrow{font-size:9px}.st-key-topbar>[data-testid=stHorizontalBlock]{flex-wrap:wrap}.la-head{gap:12px}}
@media(max-width:767px){[data-testid=stMain]{margin:0!important;padding-bottom:100px;width:100%!important;max-width:100%!important}[data-testid=stMainBlockContainer],.block-container{padding:24px 16px 28px!important}[data-testid=stSidebar]{inset:auto 12px 12px!important;width:calc(100% - 24px)!important;min-width:0!important;max-width:none!important;height:76px!important;border:1px solid var(--border);border-radius:24px;background:var(--surface)!important;box-shadow:0 8px 32px #0008;overflow:visible!important}[data-testid=stSidebarContent]{height:100%!important;overflow:visible!important}[data-testid=stSidebarUserContent]{height:100%!important;min-height:0!important;padding:7px!important;overflow:visible!important}[data-testid=stSidebarUserContent]>div,[data-testid=stSidebarUserContent]>div>[data-testid=stVerticalBlock]{min-height:0!important;height:100%!important;gap:0!important}[data-testid=stSidebar] .la-brand,.st-key-sidebar_footer{display:none!important}[data-testid=stSidebar] [role=radiogroup]{flex-direction:row!important;display:flex!important;gap:2px!important;height:60px!important;align-items:center}[data-testid=stSidebar] [role=radiogroup]>div{flex:1 1 0!important;min-width:0!important;width:0!important}[data-testid=stSidebar] [role=radiogroup] label{padding:8px 2px!important;min-height:58px;width:100%;justify-content:center;border-radius:17px}[data-testid=stSidebar] [role=radiogroup] label p{font-size:9px!important;gap:3px!important;flex-direction:column;line-height:1.2}[data-testid=stSidebar] label [data-testid=stIconMaterial],[data-testid=stSidebar] label span[role=img]{font-size:21px!important}.st-key-topbar{padding-bottom:16px}.st-key-topbar [data-testid=stHorizontalBlock]{flex-wrap:wrap!important;gap:12px!important}.st-key-topbar [data-testid=stColumn]{min-width:0!important;flex:1 1 40px!important}.st-key-topbar [data-testid=stColumn]:first-child{flex-basis:100%!important}.st-key-topbar [data-testid=stColumn]:nth-child(2){flex-basis:50%!important}.la-head>.la-pill{display:inline-flex}.la-head h1{font-size:26px!important}.la-head .la-sub{display:none}div[class*=st-key-card_],div[class*=st-key-rem_]{padding:20px!important;border-radius:22px}[class*=st-key-layout_]>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]>[data-testid=stColumn]{flex-basis:100%!important;width:100%!important}.la-summary{padding:24px;min-height:205px}.la-summary strong{font-size:42px}.la-summary .next{min-width:60px}.la-summary .next b{font-size:22px}.la-stats{grid-template-columns:1fr}.la-stat{display:flex;align-items:center;justify-content:space-between;padding:16px}.la-stat .value{margin:0;font-size:26px}.la-stat .la-eyebrow{margin:0;font-size:10px}.la-ring{max-width:245px}.la-fields{grid-template-columns:1fr}.la-year{grid-template-columns:repeat(3,minmax(0,1fr))}.la-doc-row{grid-template-columns:36px minmax(0,1fr);gap:10px}.la-doc-row>.la-pill{grid-column:2;justify-self:start}.la-cal{border-spacing:2px!important}.la-cal td,.la-cal th{font-size:10px;padding:6px 0!important}.la-cal .n{width:27px;height:27px}.st-key-card_calendar_large .la-cal td{height:64px}.st-key-card_docdetail{position:static}.la-auth-brand{display:none}.st-key-auth_shell{margin:0!important}.st-key-auth_shell>[data-testid=stHorizontalBlock]{display:block!important}.st-key-auth_shell [data-testid=stColumn]{width:100%!important;flex:1 1 100%!important}.st-key-auth_shell [data-testid=stColumn]:first-child{display:none!important}.st-key-auth_card{margin:12px auto;padding:24px!important}.st-key-auth_card h1{font-size:26px!important}[data-testid=stFormSubmitButton] button,[data-testid=stDownloadButton] button{width:100%}.st-key-card_activity{overflow:hidden}}

@media(min-width:768px) and (max-width:1199px){
[data-testid=stSidebar],[data-testid=stSidebarContent],[data-testid=stSidebarUserContent]{overflow:visible!important}
[data-testid=stSidebar] label:after{position:absolute;left:62px;top:8px;padding:8px 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface-2);color:var(--text);font-size:12px;white-space:nowrap;z-index:1100;pointer-events:none;opacity:0;transition:opacity .15s}
[data-testid=stSidebar] label:hover:after,[data-testid=stSidebar] label:focus-within:after{opacity:1}
[data-testid=stSidebar] label:has(input[value="0"]):after{content:'Dashboard'}
[data-testid=stSidebar] label:has(input[value="1"]):after{content:'Upload'}
[data-testid=stSidebar] label:has(input[value="2"]):after{content:'Documents'}
[data-testid=stSidebar] label:has(input[value="3"]):after{content:'Reminders'}
[data-testid=stSidebar] label:has(input[value="4"]):after{content:'Calendar'}
[data-testid=stSidebar] label:has(input[value="5"]):after{content:'Notes'}
}
@media(min-width:768px) and (max-width:1023px){.st-key-layout_calendar>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]>[data-testid=stColumn],.st-key-layout_documents>[data-testid=stLayoutWrapper]>[data-testid=stHorizontalBlock]>[data-testid=stColumn]{flex-basis:100%!important}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}.la-count{--count:var(--target)}}
</style>
"""


def inject_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    """Render HTML. Lines are joined so Markdown never treats them as code."""
    st.markdown(" ".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


# ---------------------------------------------------------------- components
def brand() -> str:
    return f'<div class="la-brand">{LOGO_SVG}<span>LifeAdmin</span></div>'


def motto() -> str:
    return '<div class="la-motto">Less chaos.<br/>More life.<i></i></div>'


def page_header(title: str, subtitle: str, icon_name: str) -> str:
    return (f'<div class="la-head"><div><div class="la-eyebrow">{esc(icon_name)} · Updated now</div>'
            f'<h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>{pill("none", "Private vault")}</div>')


def card_title(title: str, icon_name: str) -> str:
    return f'<div class="la-card-title">{icon(icon_name, 18)}<span>{esc(title)}</span></div>'


KPI_STYLE = {
    "total": ("files", "#6366F1", "linear-gradient(135deg, rgba(79,70,229,.30), rgba(24,30,80,.55))", "rgba(99,102,241,.35)"),
    "active": ("check", "#22C55E", "linear-gradient(135deg, rgba(22,101,52,.40), rgba(14,32,40,.55))", "rgba(34,197,94,.30)"),
    "expiring": ("clock", "#F5A524", "linear-gradient(135deg, rgba(146,94,10,.40), rgba(36,30,26,.55))", "rgba(245,165,36,.30)"),
    "critical": ("alert", "#EF4444", "linear-gradient(135deg, rgba(153,27,27,.42), rgba(40,20,34,.55))", "rgba(239,68,68,.32)"),
}


def kpi(kind: str, label: str, value: object, caption: str) -> str:
    ic, col, bg, border = KPI_STYLE[kind]
    return (f'<div class="la-kpi" style="background:{bg};border-color:{border}">'
            f'{icon_tile(ic, col, 44, 12, 22, solid=kind != "total")}'
            f'<div><div class="lbl">{esc(label)}</div><div class="val">{esc(value)}</div>'
            f'<div class="cap">{esc(caption)}</div></div></div>')


def row(leading: str, title: str, sub: str, trailing: str = "", sub_icon: str = "") -> str:
    si = icon(sub_icon, 12) if sub_icon else ""
    return (f'<div class="la-row">{leading}<div class="main"><div class="t" title="{esc(title)}">{esc(title)}</div>'
            f'<div class="s">{si}{sub}</div></div>{trailing}</div>')


def rows(items: List[str], empty: str) -> str:
    return "".join(items) if items else f'<div class="la-empty">{esc(empty)}</div>'


def legend(entries: Iterable[Tuple[str, str, int, int]]) -> str:
    out = []
    for label, color, count, pct in entries:
        out.append(f'<div><span class="la-dot" style="background:{color}"></span>{esc(label)}'
                   f'<b>{count}</b><em>({pct}%)</em></div>')
    return f'<div class="la-legend">{"".join(out)}</div>'


def promo(line1: str, line2: str, highlight: str = "", byline: str = "") -> str:
    hl = f"<br/><span>{esc(highlight)}</span>" if highlight else ""
    by = f'<div class="by">— {esc(byline)}</div>' if byline else ""
    return (f'<div class="la-promo">{MOUNTAIN_SVG}<div class="q">{esc(line1)}<br/>{esc(line2)}{hl}</div>{by}</div>')


def thumb_img(png: Optional[bytes]) -> str:
    if not png:
        return f'<div class="la-thumb-ph">{icon("file", 30, "#8F94FF")}</div>'
    return f'<img class="la-thumb" src="data:image/png;base64,{base64.b64encode(png).decode()}"/>'


def fields_table(pairs: List[Tuple[str, str]]) -> str:
    body = "".join(f'<div><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in pairs)
    return f'<div class="la-fields">{body}</div>'


def health_meter(score: int, checks: List[Tuple[str, bool]], verdict: str) -> str:
    color = C["indigo"]
    ck = "".join(f'<div class="ck"><span>{esc(lbl)}</span><span style="color:{"#8E92FF" if ok else "#FF6B6B"}">'
                 f'{"✓" if ok else "✗"}</span></div>' for lbl, ok in checks)
    return (f'<div class="la-health"><div style="display:flex;justify-content:space-between"><span class="la-sub">Completeness</span>'
            f'<b style="color:{color}">{score}%</b></div><div class="bar"><i style="width:{score}%;background:{color}"></i></div>'
            f'{ck}<div class="la-sub" style="margin-top:.5rem">{esc(verdict)}</div></div>')


def month_calendar(year: int, month: int, marks: Dict[date, List[Tuple[str, str]]],
                   today: date) -> str:
    """HTML month grid. marks: day -> [(colour, tooltip), ...]."""
    cal = calendar.Calendar(firstweekday=6)  # Sunday first, like the design
    head = "".join(f"<th>{d}</th>" for d in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    body = []
    for week in cal.monthdatescalendar(year, month):
        cells = []
        for d in week:
            cls = []
            if d.month != month:
                cls.append("o")
            if d == today:
                cls.append("today")
            dots = marks.get(d, []) if d.month == month else []
            tip = esc("; ".join(t for _, t in dots))
            dot_html = "".join(f'<i style="background:{c}"></i>' for c, _ in dots[:3])
            cells.append(f'<td class="{" ".join(cls)}" title="{tip}"><span class="n">{d.day}</span>'
                         f'<div class="dots">{dot_html}</div></td>')
        body.append(f"<tr>{''.join(cells)}</tr>")
    return f'<table class="la-cal"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def summary_grid(items: List[Tuple[str, str, object, str]]) -> str:
    out = "".join(f'<div>{icon_tile(ic, col, 36, 10, 18, solid=True)}<div><b>{esc(v)}</b><span>{esc(lbl)}</span></div></div>'
                  for ic, col, v, lbl in items)
    return f'<div class="la-sum">{out}</div>'


def avatar_css(initials: str) -> None:
    st.markdown(f'<style>.st-key-avatar button::before {{ content:"{esc(initials)}"; }}</style>',
                unsafe_allow_html=True)

# Presentation-only components. All data and actions remain in the existing modules.
def health_ring(score: int, label: str = "Document health") -> str:
    import math
    value = max(0, min(100, int(score)))
    ticks = []
    for i in range(60):
        angle = math.pi * i / 30
        inner = 128 if i % 5 else 124
        ticks.append(f'<line x1="{140+inner*math.sin(angle):.2f}" y1="{140-inner*math.cos(angle):.2f}" '
                     f'x2="{140+133*math.sin(angle):.2f}" y2="{140-133*math.cos(angle):.2f}" '
                     'stroke="#5A5A68" stroke-width="1"/>')
    return (f'<div class="la-ring" role="img" aria-label="{esc(label)}: {value} out of 100" style="--score:{value}">'
            f'<svg viewBox="0 0 280 280" aria-hidden="true">{"".join(ticks)}'
            '<circle cx="140" cy="140" r="109" fill="none" stroke="#272732" stroke-width="16"/>'
            '<circle class="dial" cx="140" cy="140" r="109" pathLength="100" fill="none" stroke-width="16" stroke-linecap="round"/>'
            '</svg><div class="ring-value"><div class="score">'
            f'<span class="la-count" style="--target:{value}" aria-hidden="true"></span>'
            f'<span class="la-sr-only">{value}</span></div><div class="ring-caption">{esc(label)}</div></div>'
            '<div class="scale"><span>0</span><span>100</span></div></div>')


def vault_summary(valid: int, total: int, next_days: int | None) -> str:
    due = "No deadline" if next_days is None else "Today" if next_days == 0 else f"{next_days} days"
    return (f'<div class="la-summary"><div><div class="la-eyebrow">A little less to think about</div>'
            f'<strong>{valid} of {total}</strong><div>documents are up to date</div></div>'
            f'<div class="next"><div class="la-eyebrow">Next due</div><b>{esc(due)}</b></div></div>')


def stat_tiles(items) -> str:
    return '<div class="la-stats">'+''.join(
        f'<div class="la-stat"><div class="la-eyebrow">{esc(label)}</div><div class="value">{esc(value)}</div></div>'
        for label,value in items)+'</div>'


def result_card(title: str, subtitle: str) -> str:
    return (f'<div class="la-result"><div><b>{esc(title)}</b><div class="la-sub">{esc(subtitle)}</div></div>'
            f'{icon("check",40)}</div>')


def document_row(doc, status: str) -> str:
    expiry = f'Due {doc.expiry_date:%d %b %Y}' if doc.expiry_date else 'No expiry date'
    note = f'<div class="note">{icon("file",12)} {esc(doc.notes)}</div>' if doc.notes else ''
    return (f'<div class="la-doc-row">{type_tile(doc.doc_type,42)}<div><h4>{esc(doc.filename)}</h4>'
            f'<div class="meta"><span class="la-sub">{esc(doc.doc_type)} · {esc(expiry)}</span>'
            f'<span class="la-mono">DOC-{int(doc.id or 0):03d}</span></div>{note}</div>{status}</div>')


def day_strip(docs, completed: set, today: date, view: str = "Week") -> str:
    from datetime import timedelta
    if view == "Year":
        counts = [sum(bool(d.expiry_date and d.expiry_date.year == today.year and d.expiry_date.month == m) for d in docs) for m in range(1,13)]
        peak = max(counts, default=1) or 1
        return '<div class="la-year">'+''.join(
            f'<div class="la-month-bar">{calendar.month_abbr[m]}<b>{counts[m-1]}</b>'
            f'<i style="width:{max(4,100*counts[m-1]/peak):.1f}%"></i></div>' for m in range(1,13))+'</div>'
    if view == "Month":
        marks = {}
        for d in docs:
            if d.expiry_date:
                marks.setdefault(d.expiry_date, []).append((C["indigo"] if d.id in completed else C["amber"], d.filename))
        return month_calendar(today.year, today.month, marks, today)
    start = today-timedelta(days=today.weekday())
    days = []
    for offset in range(7):
        day = start+timedelta(days=offset)
        due = [d for d in docs if d.expiry_date == day]
        handled = bool(due) and all(d.id in completed for d in due)
        css = ' today' if day == today else ''
        css += ' handled' if handled else ''
        caption = 'Handled' if handled else 'Pending' if due else 'Clear'
        days.append(f'<div class="la-day{css}"><span class="day-name">{day:%a}</span><span class="date">{day.day:02d}</span>'
                    f'<span class="due-ring">{len(due) if due else ""}</span><span class="day-caption">{caption}</span>'
                    f'<span class="today-label">{"TODAY" if day == today else "&nbsp;"}</span></div>')
    return '<div class="la-day-strip">'+''.join(days)+'</div>'
