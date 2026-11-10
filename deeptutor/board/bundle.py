"""Write a board as one self-contained HTML file for an offline phone.

No network request, no external font or library, no service worker. Copy the
file to a phone, open it in Chrome, and it works in airplane mode.

Layout (Vboard v2): notes are the spine. The first screen answers four
questions: what am I learning, how am I doing, what must I do now (one
Continue button) and what does it look like (the picture). Each notes section
carries the picture labels it talks about and one check question; a wrong
answer opens a plain explanation and a fresh question. On a laptop the picture,
the notes and the current check question sit side by side.

All board text is inserted with ``textContent``. The only generated markup
placed in the page is the picture SVG, which has already been through
``sanitize_svg``; its ids are prefixed so they cannot clash with the page.
The Barlow fonts are embedded (SIL OFL, see ``FONT_LICENSE.md``); the V logo
is shown still, without its animation.
"""

from __future__ import annotations

from functools import lru_cache
import json
import math
from pathlib import Path
import re
from typing import Any

from deeptutor.services.file_io import atomic_write_text

from .schema import Board
from .store import BoardStore

_BRAND_FILE = Path(__file__).with_name("brand.json")

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; base-uri 'none'; form-action 'none'">
<meta name="color-scheme" content="dark light">
<meta name="theme-color" content="#0e0e11">
<title>__TITLE__</title>
<style>__FONTS__</style>
<style>
:root{--bg:#0d0907;--bg2:radial-gradient(130% 70% at 50% -12%,#4a220c 0%,#1c110b 45%,#0d0907 100%);--card:rgba(255,236,220,.055);--card2:rgba(255,236,220,.08);--ink:#f7efe7;--mute:#cbbfb3;--or:#ff8a3d;--or2:#e8590c;--line:rgba(255,236,220,.11);--good:#5be08a;--bad:#ff8a80;--focus:#ffd166;--onor:#1a0b02;--glass:rgba(38,24,16,.62);--glow:0 10px 28px rgba(232,89,12,.35);
--ui:"Barlow Condensed","Bahnschrift","Roboto Condensed","Arial Narrow",system-ui,sans-serif;--tx:"Barlow",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--r:16px}
:root.light{--bg:#f7f2ec;--bg2:linear-gradient(180deg,#fbe7d6 0%,#f7f2ec 40%);--card:#ffffff;--card2:#f6efe7;--ink:#1d1611;--mute:#544a42;--or:#b8400b;--or2:#9a3412;--line:#e6dbcf;--good:#15803d;--bad:#b42318;--focus:#1d4ed8;--onor:#ffffff;--glass:rgba(255,255,255,.72);--glow:0 8px 20px rgba(154,52,18,.18)}
:root.hc{--bg:#000;--bg2:#000;--card:#000;--card2:#000;--ink:#fff;--mute:#fff;--or:#ffc23d;--or2:#ffc23d;--line:#fff;--good:#7dff9b;--bad:#ff9d9d;--focus:#00e5ff;--onor:#000;--glass:#000;--glow:none}
html.t1{font-size:16px}html.t2{font-size:19px}html.t3{font-size:22px}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;background:var(--bg);color:var(--ink);font:1rem/1.6 var(--tx)}
body{background:var(--bg2) no-repeat,var(--bg);min-height:100vh}
:root:not(.calm){scroll-behavior:smooth}
:root:not(.calm) .cta,:root:not(.calm) .opt,:root:not(.calm) .sec{transition:background .2s,border-color .2s,box-shadow .2s}
a{color:var(--or)}
:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.skip{position:absolute;left:-999px;top:8px;background:var(--card);color:var(--ink);padding:10px 14px;border-radius:10px;z-index:99}.skip:focus{left:8px}
h1,h2,h3{font-family:var(--ui);line-height:1.15;margin:0}
button{font:inherit;color:inherit}
/* header */
.top{display:flex;align-items:center;gap:10px;min-height:56px;max-width:1440px;margin:0 auto;padding:8px max(16px,env(safe-area-inset-left)) 0}
.top .vx-logo{width:32px;height:32px;flex:none}
.wm{font-family:var(--ui);font-weight:700;letter-spacing:.12em;font-size:1rem}
.ttop{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--mute);font-size:.95rem}
.iconbtn{display:none}
/* tabs */
.dock{position:fixed;left:50%;bottom:calc(12px + env(safe-area-inset-bottom));transform:translateX(-50%);z-index:30;display:flex;gap:4px;padding:6px;border-radius:999px;background:var(--glass);border:1px solid var(--line);-webkit-backdrop-filter:blur(18px) saturate(150%);backdrop-filter:blur(18px) saturate(150%);box-shadow:0 12px 32px rgba(0,0,0,.45)}
.dock a,.dock button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;width:64px;height:58px;border-radius:999px;border:0;background:transparent;color:var(--mute);text-decoration:none;font:600 .72rem/1.1 var(--tx);cursor:pointer}
.dock svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.dock .aa{font-family:var(--ui);font-weight:700;font-size:1.15rem;line-height:22px}
.dock [aria-current="true"]{background:linear-gradient(180deg,var(--or),var(--or2));color:var(--onor);box-shadow:var(--glow)}
@media (prefers-reduced-transparency:reduce){.dock{-webkit-backdrop-filter:none;backdrop-filter:none;background:var(--bg)}}
:root.hc .dock{-webkit-backdrop-filter:none;backdrop-filter:none;border-width:2px}


main{max-width:760px;margin:0 auto;padding:10px 14px calc(110px + env(safe-area-inset-bottom))}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:18px;margin:0 0 14px}
.draft{border:1px dashed var(--or);color:var(--ink);border-radius:12px;padding:8px 12px;margin:0 0 12px;font-size:.92rem}
/* today */
.today .eyebrow{margin:0;color:var(--mute);font-size:.95rem}
.today h1{font-size:2rem;margin:4px 0 10px;color:var(--ink)}
.where{margin:0 0 8px;font-weight:600;color:var(--mute)}
.where b{font-family:var(--ui);font-size:2.6rem;line-height:1;color:var(--ink);margin-right:6px}
.bar{height:10px;border-radius:99px;background:var(--card2);border:1px solid var(--line);overflow:hidden}
.bar span{display:block;height:100%;width:0;background:var(--or)}
.weak{margin:8px 0 0;color:var(--mute)}
.cta{display:flex;align-items:center;justify-content:center;width:100%;min-height:54px;margin-top:14px;border:0;border-radius:14px;background:linear-gradient(180deg,var(--or),var(--or2));color:var(--onor);font-family:var(--ui);font-weight:700;font-size:1.25rem;cursor:pointer;box-shadow:var(--glow)}
.ghost{min-height:48px;padding:8px 16px;border-radius:12px;border:1px solid var(--line);background:transparent;cursor:pointer;font-weight:600}
.link{background:none;border:0;padding:10px 0;min-height:44px;color:var(--or);font-weight:600;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:12px}
/* picture */
.frame{position:relative;margin:0;background:#fff;border-radius:12px;padding:8px;cursor:zoom-in;border:1px solid var(--line)}
.frame svg,.mini svg{display:block;width:100%;height:auto;max-height:46vh}
.frame .hint{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.7);color:#fff;font-size:.8rem;padding:2px 8px;border-radius:8px}
.cap{color:var(--mute);font-size:.92rem;margin:8px 0 0}
.chips{list-style:none;display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:10px 0 0}
.chips li{border:1px solid var(--or);border-radius:99px;padding:2px 10px;font-size:.9rem}
.nopic{color:var(--mute)}
.credit{color:var(--mute);font-size:.82rem;margin:6px 0 0}
/* sections */
.secno{margin:0;color:var(--mute);font-size:.9rem}
.sec h2{font-size:1.5rem;margin:2px 0 10px}
.sec.cur{border-color:var(--or);box-shadow:0 0 0 1px var(--or)}
.sec.done .secno::after{content:"  \2713 done";color:var(--good);font-weight:700}
.pts{margin:0;padding-left:1.2em}.pts li{margin:0 0 8px}
.simple{background:var(--card2);border-radius:12px;padding:10px 12px;margin:0 0 12px}
.simple strong{display:block;font-family:var(--ui);font-size:1.05rem}
.mini{margin:0 0 12px;background:#fff;border-radius:12px;padding:6px;border:1px solid var(--line);cursor:zoom-in}
.xbox p{white-space:pre-line}
.xbox{background:var(--card2);border-radius:12px;padding:12px;margin:8px 0}
.xbox h3{font-size:1.1rem;margin:0 0 6px}.xbox p{margin:0 0 8px}
/* questions */
.qcard{border:1px solid var(--line);border-radius:14px;padding:14px;margin-top:14px;background:var(--card2)}
.qlab{margin:0 0 4px;color:var(--mute);font-size:.88rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.qtext{margin:0 0 10px;font-weight:600;font-size:1.08rem}
.opts{display:grid;gap:8px}
.opt{display:flex;align-items:center;gap:10px;width:100%;min-height:48px;padding:10px 12px;text-align:left;border-radius:12px;border:1px solid var(--line);background:var(--card);cursor:pointer}
.opt .k{flex:none;width:28px;height:28px;border-radius:50%;border:2px solid var(--mute);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85rem}
.opt.sel{border-color:var(--or)}.opt.sel .k{background:var(--or);border-color:var(--or);color:var(--onor)}
.opt.right{border-color:var(--good)}.opt.right .k{background:var(--good);border-color:var(--good);color:#000}
.opt.wrong{border-color:var(--bad)}.opt.wrong .k{background:var(--bad);border-color:var(--bad);color:#000}
.opt:disabled{cursor:default;opacity:1}
.ans{width:100%;min-height:48px;padding:10px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit}
.res{font-weight:700;margin:12px 0 6px}.res.good{color:var(--good)}.res.bad{color:var(--bad)}
.go{min-height:48px;padding:8px 18px;border:0;border-radius:12px;background:var(--or);color:var(--onor);font-weight:700;cursor:pointer}
.go:disabled{opacity:.45;cursor:default}
.memo{background:var(--card);border-left:4px solid var(--or);border-radius:8px;padding:8px 12px;margin:8px 0}
.memo strong{display:block}
/* terms, formulas, progress */
dl{margin:0}dt{font-weight:700;margin-top:8px}dd{margin:0 0 4px;color:var(--ink)}
.f{background:var(--card2);border-radius:10px;padding:10px;margin:0 0 8px}
.f .mm{font-size:1.45rem;padding:6px 0;overflow-x:auto}
.f .mm math{color:var(--ink)}
.f code{display:block;font-size:1.05rem;white-space:pre-wrap;color:var(--ink)}
.plist{list-style:none;padding:0;margin:0}
.plist li{display:flex;align-items:center;gap:10px;justify-content:space-between;border-bottom:1px solid var(--line);padding:8px 0}
.st{font-size:.85rem;font-weight:700;border-radius:99px;padding:2px 10px;border:1px solid var(--line);white-space:nowrap}
.st.done{color:var(--good);border-color:var(--good)}.st.weak{color:var(--bad);border-color:var(--bad)}
.score{font-size:1.1rem;font-weight:700;margin:0 0 8px}
.foot{color:var(--mute);font-size:.85rem;text-align:center;margin-top:20px}
/* overlays */
.veil{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;padding:10px}
.zbox{width:100%;max-width:1100px;max-height:94vh;overflow:auto;background:#fff;border-radius:14px;padding:8px}
.zbox svg{width:100%;min-width:min(760px,160vw);height:auto;display:block}
.sheet{width:100%;max-width:480px;max-height:92vh;overflow:auto;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:18px;padding:18px}
.sheet h2{font-size:1.4rem;margin-bottom:6px}
.sheet fieldset{border:0;padding:0;margin:14px 0 0}
.sheet legend{font-weight:700;margin-bottom:6px}
.seg{display:flex;flex-wrap:wrap;gap:8px}
.seg button{min-height:46px;min-width:64px;padding:6px 12px;border-radius:12px;border:1px solid var(--line);background:var(--card2);cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--or);color:var(--onor);border-color:var(--or);font-weight:700}
.say{min-height:1.4em;color:var(--mute);font-size:.92rem}
/* tablet: picture beside notes */
@media (min-width:768px){
 main{max-width:1100px}
 .layout{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:16px;align-items:start}
 .pic-col{position:sticky;top:16px}
 .mini{display:none}
 .check-col{display:none}
}
/* laptop: picture, notes, check question side by side */
@media (min-width:1200px){
 main{max-width:1440px}
 .layout{grid-template-columns:minmax(0,3fr) minmax(0,4fr) minmax(0,3fr)}
 .check-col{display:block;position:sticky;top:16px}
 .check-col .qcard{margin-top:0}
 .today{display:grid;grid-template-columns:2fr 1fr;gap:6px 24px;align-items:center}
 .today .cta{grid-column:2;grid-row:1 / span 4;margin:0}
}
@media print{.dock,.cta,.veil,.check-col{display:none!important}body{background:#fff;color:#000}.card{break-inside:avoid}}
</style>
</head>
<body>
<a class="skip" href="#notes">Skip to the notes</a>
<header class="top">
 __LOGO__
 <span class="wm">VBOARD</span>
 <span class="ttop" id="ttop"></span>
</header>

<main id="main">
 <p class="draft" id="draft" hidden>Draft for the tutor to check. Students only receive approved boards.</p>
 <section class="card today" aria-labelledby="title">
  <p class="eyebrow" id="course"></p>
  <h1 id="title"></h1>
  <p class="where" id="where"></p>
  <div class="bar" id="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Sections done"><span id="barfill"></span></div>
  <p class="weak" id="weak"></p>
  <button type="button" class="cta" id="continue">Start</button>
 </section>
 <div class="layout">
  <aside class="pic-col" id="glance" aria-labelledby="glanceLab">
   <section class="card">
    <h2 id="glanceLab" style="font-size:1.3rem;margin-bottom:8px">The picture</h2>
    <figure class="frame" id="frame" tabindex="0" role="button" aria-label="Enlarge the picture"></figure>
    <p class="cap" id="cap"></p>
    <p class="credit" id="credit" hidden></p>
    <p class="cap" id="chipsLab" hidden>In this section:</p>
    <ul class="chips" id="chips" aria-live="polite"></ul>
   </section>
  </aside>
  <div class="stream" id="notes" tabindex="-1">
   <section class="card" id="sumbox"><h2 style="font-size:1.3rem">In short</h2><p id="summary" style="margin:6px 0 0"></p></section>
   <div id="sections"></div>
   <section class="card" id="termsbox" hidden><h2 style="font-size:1.3rem">Key terms</h2><dl id="terms"></dl></section>
   <section class="card" id="formbox" hidden><h2 style="font-size:1.3rem;margin-bottom:8px">Formulas</h2><div id="formulas"></div></section>
   <section class="card" id="test" aria-labelledby="testLab" tabindex="-1"><h2 id="testLab" style="font-size:1.4rem">Topic test</h2><div id="testbox"></div></section>
   <section class="card" id="progress" aria-labelledby="progLab" tabindex="-1"><h2 id="progLab" style="font-size:1.4rem;margin-bottom:8px">How am I doing</h2><p class="score" id="score"></p><ul class="plist" id="plist"></ul></section>
  </div>
  <aside class="check-col" id="side" aria-label="Check question for the section you are reading"></aside>
 </div>
 <p class="foot" id="foot"></p>
</main>
<nav class="dock" aria-label="Jump to a part of this board">
 <a href="#glance" data-t="glance"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="15.5" cy="8.5" r="1.5"/></svg>Picture</a>
 <a href="#notes" data-t="notes"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h7"/></svg>Notes</a>
 <a href="#test" data-t="test"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l3 3 5-6"/></svg>Practice</a>
 <a href="#progress" data-t="progress"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 20V12M12 20V5M19 20v-9"/></svg>Progress</a>
 <button type="button" id="aa" aria-haspopup="dialog" aria-label="Settings: text size, colours, motion, read aloud"><span class="aa" aria-hidden="true">Aa</span>Settings</button>
</nav>
<div class="veil" id="v-zoom" hidden><div class="zbox" id="zbox" role="dialog" aria-modal="true" aria-label="Picture, full screen. Tap to close."></div></div>
<div class="veil" id="v-set" hidden>
 <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="setLab">
  <h2 id="setLab">Settings</h2>
  <fieldset><legend>Text size</legend><div class="seg" data-pref="size"><button type="button" data-v="t1">A</button><button type="button" data-v="t2">A+</button><button type="button" data-v="t3">A++</button></div></fieldset>
  <fieldset><legend>Colours</legend><div class="seg" data-pref="theme"><button type="button" data-v="dark">Dark</button><button type="button" data-v="light">Light</button><button type="button" data-v="hc">High contrast</button></div></fieldset>
  <fieldset><legend>Motion</legend><div class="seg" data-pref="motion"><button type="button" data-v="on">Normal</button><button type="button" data-v="off">Reduce motion</button></div></fieldset>
  <fieldset><legend>Words</legend><div class="seg" data-pref="simple"><button type="button" data-v="off">Standard</button><button type="button" data-v="on">Simple first</button></div></fieldset>
  <fieldset id="readSet"><legend>Read aloud</legend><p class="cap" style="margin:0">Each section has a Listen button. It uses your phone's own voice.</p></fieldset>
  <fieldset><legend>My progress</legend><p class="cap" style="margin:0 0 8px">Progress saves on this phone by itself. If it does not stay, save a file and load it next time.</p>
   <div class="row" style="margin-top:0"><button type="button" class="ghost" id="exp">Save my progress</button><button type="button" class="ghost" id="impBtn">Load progress</button><input type="file" id="imp" accept=".json,application/json" hidden><button type="button" class="ghost" id="reset">Start again</button></div>
   <p class="say" id="say" aria-live="polite"></p></fieldset>
  <div class="row"><button type="button" class="go" id="setClose">Done</button></div>
 </div>
</div>
<div id="picture-svg" hidden>__SVG__</div>
<div id="math" hidden>__MATH__</div>
<script type="application/json" id="board-data">__BOARD_JSON__</script>
<script>
(function(){
"use strict";
var B=JSON.parse(document.getElementById("board-data").textContent);
var PLAN=B._plan||{sections:[],test:[]};
var SECS=(B.notes&&B.notes.sections)||[];
var QS={};((B.practice&&B.practice.questions)||[]).forEach(function(q){QS[q.id]=q});
var EXS=B.explainers||[];
function $(i){return document.getElementById(i)}
function el(tag,attrs,kids){var n=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="text")n.textContent=attrs[k];else if(k==="class")n.className=attrs[k];else n.setAttribute(k,attrs[k]);}(kids||[]).forEach(function(c){n.appendChild(typeof c==="string"?document.createTextNode(c):c)});return n}
function clear(n){while(n.firstChild)n.removeChild(n.firstChild)}

/* ---- storage: on this phone, with an in-memory fallback ---- */
var KEY="vboard:"+B.board_id+":"+B.generated_at, PKEY="vboard:prefs", store=null;
try{localStorage.setItem("__t","1");localStorage.removeItem("__t");store=localStorage}catch(e){store=null}
function read(k,d){try{var r=store&&store.getItem(k);return r?JSON.parse(r):d}catch(e){return d}}
function write(k,v){try{if(store)store.setItem(k,JSON.stringify(v))}catch(e){}}
var S=read(KEY,null)||{};S.ans=S.ans||{};S.done=S.done||{};S.weak=S.weak||{};
function save(){write(KEY,S)}
var P=read(PKEY,{})||{};
function savePrefs(){write(PKEY,P)}

/* ---- preferences ---- */
var reduceOS=!!(window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches);
if(!P.size)P.size="t1";if(!P.theme)P.theme="dark";if(!P.motion)P.motion=reduceOS?"off":"on";if(!P.simple)P.simple="off";
function applyPrefs(){var h=document.documentElement;h.classList.remove("t1","t2","t3","light","hc","calm");h.classList.add(P.size);
 if(P.theme==="light")h.classList.add("light");if(P.theme==="hc")h.classList.add("hc");if(P.motion==="off")h.classList.add("calm");
 [].forEach.call(document.querySelectorAll(".seg"),function(g){var k=g.getAttribute("data-pref");[].forEach.call(g.querySelectorAll("button"),function(b){b.setAttribute("aria-pressed",String(b.getAttribute("data-v")===P[k]))})})}
[].forEach.call(document.querySelectorAll(".seg button"),function(b){b.addEventListener("click",function(){var k=b.parentNode.getAttribute("data-pref");P[k]=b.getAttribute("data-v");savePrefs();applyPrefs();if(k==="simple")renderSections()})});
applyPrefs();

/* ---- sheets ---- */
var lastFocus=null;
function openSheet(id,focusEl){lastFocus=document.activeElement;$(id).hidden=false;(focusEl||$(id).querySelector("button"))&&(focusEl||$(id).querySelector("button")).focus()}
function closeSheets(){$("v-zoom").hidden=true;$("v-set").hidden=true;if(lastFocus&&lastFocus.focus)lastFocus.focus()}
document.addEventListener("keydown",function(e){if(e.key==="Escape")closeSheets()});
$("aa").addEventListener("click",function(){openSheet("v-set")});
$("setClose").addEventListener("click",closeSheets);
$("v-set").addEventListener("click",function(e){if(e.target===$("v-set"))closeSheets()});
$("zbox").addEventListener("click",closeSheets);

/* ---- header and today ---- */
var c=B.course||{};
var courseLine=[B.subject,B.level||c.level,B.programme].filter(Boolean).join(" · ");
$("ttop").textContent=B.topic;$("title").textContent=B.topic;$("course").textContent=courseLine;
if(!B.review||B.review.status!=="reviewed")$("draft").hidden=false;
$("summary").textContent=(B.notes&&B.notes.summary)||"";if(!$("summary").textContent)$("sumbox").hidden=true;
$("foot").textContent=B.review&&B.review.status==="reviewed"?"Checked and approved by your tutor"+(B.review.reviewed_at?" on "+String(B.review.reviewed_at).slice(0,10):"")+".":"Not yet approved.";

/* ---- picture ---- */
var PIC=null,LABELS=[],OPENPIC=null;
function norm(t){return String(t||"").toLowerCase().replace(/\s+/g," ").trim()}
function key(t){return t.replace(/\([^)]*\)/g," ").split(" ").filter(function(w){return w.length>1&&!/\d/.test(w)}).join(" ")}
function has(body,k){return(" "+body.replace(/[^a-z0-9 ]/g," ")+" ").indexOf(" "+k+" ")>-1}
(function(){
 var holder=$("picture-svg"),svg=holder.querySelector("svg"),frame=$("frame"),pic=B.picture||{};
 if(!svg){frame.removeAttribute("role");frame.removeAttribute("tabindex");frame.style.cursor="default";frame.appendChild(el("p",{class:"nopic",text:"No picture for this topic."}));frame.style.background="transparent";return}
 PIC=svg;svg.setAttribute("role","img");svg.setAttribute("aria-label",pic.alt||pic.title||"Diagram for "+B.topic);
 frame.appendChild(svg);
 var cp=String(pic.caption||pic.title||"").trim();if(cp&&!/[.!?]$/.test(cp))cp+=".";$("cap").textContent=(cp+" Tap the picture to enlarge it.").trim();
 if(pic.credit){$("credit").hidden=false;$("credit").textContent=pic.credit}
 LABELS=[].slice.call(svg.querySelectorAll("text")).map(function(n){var t=norm(n.textContent);return{n:n,raw:String(n.textContent||"").trim(),k:key(t)||(t.length>=3?t:""),fill:n.getAttribute("fill"),w:n.getAttribute("font-weight")}}).filter(function(o){return o.k.length>=2&&!/^[\d.,\s]+[a-z°%]{0,3}$/i.test(o.k)});
 OPENPIC=function(src){var z=$("zbox");clear(z);z.appendChild((src||svg).cloneNode(true));openSheet("v-zoom",z)};
 frame.addEventListener("click",function(){OPENPIC()});frame.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();OPENPIC()}});
})();
function labelsFor(i){var s=SECS[i];if(!s)return[];var body=norm(s.heading+" "+(s.points||[]).join(" "));return LABELS.filter(function(o){return has(body,o.k)})}
function light(root,list){var on={};list.forEach(function(o){on[o.raw]=1});
 [].forEach.call(root.querySelectorAll("text"),function(n){var lit=!!on[String(n.textContent||"").trim()];
  if(lit){if(!n.hasAttribute("data-f"))n.setAttribute("data-f",n.getAttribute("fill")||"");if(!n.hasAttribute("data-w"))n.setAttribute("data-w",n.getAttribute("font-weight")||"");n.setAttribute("fill","#c2410c");n.setAttribute("font-weight","700")}
  else if(n.hasAttribute("data-f")){var f=n.getAttribute("data-f"),w=n.getAttribute("data-w");if(f)n.setAttribute("fill",f);else n.removeAttribute("fill");if(w)n.setAttribute("font-weight",w);else n.removeAttribute("font-weight")}})}

/* ---- questions ---- */
var CHOICE={single_choice:1,multi_choice:1};
function keys(a){return String(a||"").toUpperCase().split(/[,\s]+/).filter(Boolean).sort()}
function same(a,b){return a.length===b.length&&a.every(function(x,i){return x===b[i]})}
var drafts={};
/* Draw one question into box. done(correct) is called once the student has answered. */
function qui(box,q,label,done){
 clear(box);var a=S.ans[q.id],d=drafts[q.id]||(drafts[q.id]={sel:[],text:"",reveal:false});
 box.appendChild(el("p",{class:"qlab",text:label}));
 box.appendChild(el("p",{class:"qtext",text:q.question}));
 function redraw(){qui(box,q,label,done)}
 function answer(given,ok){S.ans[q.id]={given:given,correct:!!ok,at:new Date().toISOString()};save();redraw();if(done)done(!!ok)}
 if(CHOICE[q.type]){
  var multi=q.type==="multi_choice",right=keys(q.answer),opts=el("div",{class:"opts",role:multi?"group":"radiogroup","aria-label":"Answers"});
  Object.keys(q.options||{}).sort().forEach(function(k){var K=k.toUpperCase(),cls="opt";
   if(a){if(right.indexOf(K)>-1)cls+=" right";else if(a.given.indexOf(K)>-1)cls+=" wrong"}else if(d.sel.indexOf(K)>-1)cls+=" sel";
   var b=el("button",{class:cls,type:"button",role:multi?"checkbox":"radio","aria-checked":String(a?a.given.indexOf(K)>-1:d.sel.indexOf(K)>-1)},[el("span",{class:"k",text:K,"aria-hidden":"true"}),String(q.options[k])]);
   if(a)b.disabled=true;
   b.addEventListener("click",function(){var i=d.sel.indexOf(K);if(multi){if(i>-1)d.sel.splice(i,1);else d.sel.push(K)}else d.sel=[K];redraw();var f=box.querySelector('.opt[aria-checked="true"]');if(f)f.focus()});
   opts.appendChild(b)});
  box.appendChild(opts);
  if(!a){if(multi)box.appendChild(el("p",{class:"cap",text:"Choose all that apply."}));var go=el("button",{class:"go",type:"button",text:"Check my answer"});go.disabled=!d.sel.length;go.addEventListener("click",function(){var g=d.sel.slice().sort();answer(g,same(g,right))});box.appendChild(el("div",{class:"row"},[go]))}
 }else if(q.type==="true_false"){
  var tf=el("div",{class:"opts",role:"radiogroup","aria-label":"Answers"});
  [["true","True"],["false","False"]].forEach(function(p){var v=p[0],cls="opt";if(a){if(String(q.answer).toLowerCase()===v)cls+=" right";else if(a.given[0]===v)cls+=" wrong"}
   var b=el("button",{class:cls,type:"button",role:"radio","aria-checked":String(!!a&&a.given[0]===v)},[el("span",{class:"k",text:p[1].charAt(0),"aria-hidden":"true"}),p[1]]);if(a)b.disabled=true;
   b.addEventListener("click",function(){answer([v],String(q.answer).toLowerCase()===v)});tf.appendChild(b)});box.appendChild(tf);
 }else if(!a){
  var ta=q.type==="fill_blank"?el("input",{class:"ans",type:"text","aria-label":"Your answer",autocomplete:"off"}):el("textarea",{class:"ans",rows:"3","aria-label":"Your answer"});ta.value=d.text;ta.addEventListener("input",function(){d.text=ta.value});box.appendChild(ta);
  if(!d.reveal){var sh=el("button",{class:"go",type:"button",text:"Show the memo"});sh.addEventListener("click",function(){d.reveal=true;redraw()});box.appendChild(el("div",{class:"row"},[sh]))}
  else{box.appendChild(el("div",{class:"memo"},[el("strong",{text:"Memo"}),el("span",{text:q.answer})]));
   var y=el("button",{class:"go",type:"button",text:"I got it right"}),n=el("button",{class:"ghost",type:"button",text:"Not yet"});
   y.addEventListener("click",function(){answer([d.text],true)});n.addEventListener("click",function(){answer([d.text],false)});box.appendChild(el("div",{class:"row"},[y,n]))}
 }
 if(a){
  box.appendChild(el("p",{class:"res "+(a.correct?"good":"bad"),role:"status",text:a.correct?"✓ Correct.":"✗ Not yet."}));
  if(!CHOICE[q.type]&&q.type!=="true_false")box.appendChild(el("div",{class:"memo"},[el("strong",{text:"Memo"}),el("span",{text:q.answer})]));
  if(q.explanation)box.appendChild(el("div",{class:"memo"},[el("strong",{text:"Why"}),el("span",{text:q.explanation})]));
 }
}

/* ---- sections: the spine ---- */
var cur=0;
function status(i){if(S.done[i])return"done";if(S.weak[i])return"weak";return"new"}
function explainBox(ex,wrap){var x=el("div",{class:"xbox"});x.appendChild(el("h3",{text:"What the book says"}));x.appendChild(el("p",{text:ex.explanation}));
 if(ex.example){x.appendChild(el("h3",{text:"Write it like this in the exam"}));x.appendChild(el("p",{text:ex.example}))}
 if(ex.mistake){x.appendChild(el("h3",{text:"Where marks are lost"}));x.appendChild(el("p",{text:ex.mistake}))}
 if(wrap)wrap.appendChild(x);return x}
function listen(text,btn){if(!("speechSynthesis" in window))return;var ss=window.speechSynthesis;if(ss.speaking){ss.cancel();btn.textContent="Listen";return}
 var u=new SpeechSynthesisUtterance(text);u.lang="en-ZA";u.rate=.95;u.onend=function(){btn.textContent="Listen"};btn.textContent="Stop";ss.speak(u)}
function checkFor(i,slot){
 var plan=PLAN.sections[i]||{},q=plan.check&&QS[plan.check],ex=plan.explain!=null?EXS[plan.explain]:null;clear(slot);
 if(!q){var nx=el("button",{class:"go",type:"button",text:i<SECS.length-1?"I have read this. Next section":"I have read this. Go to the topic test"});
  nx.addEventListener("click",function(){S.done[i]=true;delete S.weak[i];save();refresh();goNext(i)});slot.appendChild(el("div",{class:"row"},[nx]));return}
 var card=el("div",{class:"qcard"});slot.appendChild(card);
 var after=el("div",{});
 function finish(ok){if(ok){S.done[i]=true;delete S.weak[i]}else{S.weak[i]=true}save();refresh();drawAfter()}
 function drawAfter(){clear(after);var a=S.ans[q.id];if(!a)return;
  if(!a.correct&&!S.done[i]){
   if(ex){explainBox(ex,after);if(ex.check){var fq=ex.check,fb=el("div",{class:"qcard"});after.appendChild(fb);qui(fb,fq,"Try a fresh question",function(ok){if(ok){S.done[i]=true;delete S.weak[i];save();refresh();drawAfter()}})}}
   var again=el("button",{class:"ghost",type:"button",text:"Try the question again"});again.addEventListener("click",function(){delete S.ans[q.id];delete drafts[q.id];if(ex&&ex.check){delete S.ans[ex.check.id];delete drafts[ex.check.id]}save();checkFor(i,slot);placeChecks()});
   after.appendChild(el("div",{class:"row"},[again]));
  }
  if(S.done[i]||a.correct){var nx2=el("button",{class:"go",type:"button",text:i<SECS.length-1?"Next section":"Go to the topic test"});nx2.addEventListener("click",function(){goNext(i)});after.appendChild(el("div",{class:"row"},[nx2]))}
 }
 qui(card,q,"Check question · section "+(i+1),finish);slot.appendChild(after);drawAfter();
}
function goNext(i){if(i<SECS.length-1)goSection(i+1);else jump("test")}
function renderSections(){
 var host=$("sections");clear(host);
 SECS.forEach(function(s,i){
  var plan=PLAN.sections[i]||{},ex=plan.explain!=null?EXS[plan.explain]:null;
  var sec=el("section",{class:"card sec "+status(i),id:"sec-"+i,"data-i":String(i),"aria-labelledby":"sh-"+i,tabindex:"-1"});
  sec.appendChild(el("p",{class:"secno",text:"Section "+(i+1)+" of "+SECS.length}));
  sec.appendChild(el("h2",{id:"sh-"+i,text:s.heading}));
  if(P.simple==="on"&&ex){var sb=el("div",{class:"simple"},[el("strong",{text:"In simple words"}),el("span",{text:ex.explanation})]);sec.appendChild(sb)}
  var lab=labelsFor(i);
  if(PIC&&lab.length){var m=el("figure",{class:"mini",role:"button",tabindex:"0","aria-label":"Picture for this section, tap to enlarge"});var cl=PIC.cloneNode(true);cl.removeAttribute("id");light(cl,lab);m.appendChild(cl);m.addEventListener("click",function(){OPENPIC(cl)});m.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();OPENPIC(cl)}});sec.appendChild(m)}
  var ul=el("ul",{class:"pts"});(s.points||[]).forEach(function(p){ul.appendChild(el("li",{text:p}))});sec.appendChild(ul);
  var tools=el("div",{class:"row"});
  if(ex&&P.simple!=="on"){var xw=el("div",{hidden:""});var xb=el("button",{class:"link",type:"button","aria-expanded":"false",text:"Show me how the book explains it"});xb.addEventListener("click",function(){var open=xw.hidden;xw.hidden=!open;xb.setAttribute("aria-expanded",String(open));if(open&&!xw.firstChild)explainBox(ex,xw)});tools.appendChild(xb);sec.appendChild(tools);sec.appendChild(xw)}
  else sec.appendChild(tools);
  if("speechSynthesis" in window){var lb=el("button",{class:"ghost",type:"button",text:"Listen","aria-label":"Read this section aloud"});lb.addEventListener("click",function(){listen(s.heading+". "+(s.points||[]).join(" "),lb)});tools.appendChild(lb)}
  var slot=el("div",{class:"slot",id:"slot-"+i});sec.appendChild(slot);checkFor(i,slot);
  host.appendChild(sec)});
 if(!("speechSynthesis" in window))$("readSet").hidden=true;
 watchSections();placeChecks();
}

/* ---- current section: picture labels light up; on a laptop the check question sits on the right ---- */
var io=null,wide=window.matchMedia?window.matchMedia("(min-width:1200px)"):{matches:false};
function setCurrent(i){cur=i;[].forEach.call(document.querySelectorAll(".sec"),function(x){x.classList.toggle("cur",x.getAttribute("data-i")===String(i))});
 var lab=labelsFor(i);if(PIC)light(PIC,lab);var ch=$("chips");clear(ch);lab.forEach(function(o){ch.appendChild(el("li",{text:o.raw}))});$("chipsLab").hidden=!lab.length;placeChecks()}
function placeChecks(){var side=$("side");
 [].forEach.call(document.querySelectorAll(".sec"),function(sec){var i=sec.getAttribute("data-i"),slot=$("slot-"+i);var inSide=side.querySelector('[data-from="'+i+'"]');
  if(wide.matches&&String(cur)===i){if(!inSide&&slot.firstChild){var w=el("div",{"data-from":i});while(slot.firstChild)w.appendChild(slot.firstChild);clear(side);side.appendChild(w)}}
  else if(inSide){while(inSide.firstChild)slot.appendChild(inSide.firstChild);side.removeChild(inSide)}})}
if(wide.addEventListener)wide.addEventListener("change",placeChecks);
function watchSections(){if(!("IntersectionObserver" in window))return;if(io)io.disconnect();
 io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)setCurrent(Number(e.target.getAttribute("data-i")))})},{rootMargin:"-35% 0px -55% 0px"});
 [].forEach.call(document.querySelectorAll(".sec"),function(x){io.observe(x)})}
function jump(id){var t=$(id);if(!t)return;t.scrollIntoView({block:"start"});try{t.focus({preventScroll:true})}catch(e){}}
function goSection(i){setCurrent(i);var t=$("sec-"+i);if(!t)return;t.scrollIntoView({block:"start"});try{t.focus({preventScroll:true})}catch(e){}}

/* ---- tabs are jump links ---- */
(function(){var tabs=[].slice.call(document.querySelectorAll(".dock a"));
 tabs.forEach(function(a){a.addEventListener("click",function(e){e.preventDefault();jump(a.getAttribute("data-t"))})});
 if(!("IntersectionObserver" in window))return;
 var ob=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){var id=e.target.id;tabs.forEach(function(a){a.setAttribute("aria-current",String(a.getAttribute("data-t")===id))})}})},{rootMargin:"-40% 0px -55% 0px"});
 ["glance","notes","test","progress"].forEach(function(id){if($(id))ob.observe($(id))})})();

/* ---- keyboard: J and K move between sections ---- */
document.addEventListener("keydown",function(e){var t=e.target&&e.target.tagName;if(t==="INPUT"||t==="TEXTAREA"||e.ctrlKey||e.metaKey||e.altKey)return;
 if(e.key==="j"&&cur<SECS.length-1)goSection(cur+1);if(e.key==="k"&&cur>0)goSection(cur-1)});

/* ---- terms and formulas ---- */
(function(){var t=(B.notes&&B.notes.key_terms)||[],f=(B.notes&&B.notes.formulas)||[];
 if(t.length){$("termsbox").hidden=false;t.forEach(function(x){$("terms").appendChild(el("dt",{text:x.term}));$("terms").appendChild(el("dd",{text:x.meaning}))})}
 if(f.length){$("formbox").hidden=false;f.forEach(function(x,i){var b=el("div",{class:"f"});b.appendChild(el("strong",{text:x.name}));
  var m=document.querySelector('#math [data-i="'+i+'"] math');
  if(m){var w=el("div",{class:"mm"});w.appendChild(m);b.appendChild(w)}else b.appendChild(el("code",{text:x.latex}));
  if(x.explanation)b.appendChild(el("p",{text:x.explanation,style:"margin:6px 0 0"}));$("formulas").appendChild(b)})}})();

/* ---- topic test: one question at a time ---- */
var TEST=(PLAN.test||[]).filter(function(id){return QS[id]}),ti=0;
function renderTest(){var box=$("testbox");clear(box);
 if(!TEST.length){box.appendChild(el("p",{class:"cap",text:"No test questions for this topic."}));return}
 var q=QS[TEST[ti]],card=el("div",{class:"qcard"});box.appendChild(card);
 qui(card,q,"Question "+(ti+1)+" of "+TEST.length+" · "+q.marks+(q.marks===1?" mark":" marks"),function(){refresh()});
 var prev=el("button",{class:"ghost",type:"button",text:"Back"}),next=el("button",{class:"ghost",type:"button",text:ti===TEST.length-1?"See how I am doing":"Next question"});
 prev.disabled=ti===0;prev.addEventListener("click",function(){ti--;renderTest()});
 next.addEventListener("click",function(){if(ti<TEST.length-1){ti++;renderTest()}else jump("progress")});
 var redo=el("button",{class:"ghost",type:"button",text:"Try again"});redo.addEventListener("click",function(){delete S.ans[q.id];delete drafts[q.id];save();renderTest();refresh()});
 box.appendChild(el("div",{class:"row"},S.ans[q.id]?[prev,redo,next]:[prev,next]))}

/* ---- today card and progress ---- */
function refresh(){
 var n=SECS.length,done=0,weak=0;for(var i=0;i<n;i++){if(S.done[i])done++;else if(S.weak[i])weak++}
 var tAns=TEST.filter(function(id){return S.ans[id]}),tGot=0,tMarks=0,tTotal=0;TEST.forEach(function(id){var q=QS[id];tTotal+=q.marks;if(S.ans[id]&&S.ans[id].correct){tGot++;tMarks+=q.marks}});
 var CHK={};(PLAN.sections||[]).forEach(function(p){if(p.check)CHK[p.check]=1});
 var tWrong=tAns.filter(function(id){return !S.ans[id].correct&&!CHK[id]}).length;
 var pct=n?Math.round(done/n*100):0;$("barfill").style.width=pct+"%";$("bar").setAttribute("aria-valuenow",String(pct));
 var wh=$("where");clear(wh);if(n){wh.appendChild(el("b",{text:done+"/"+n}));wh.appendChild(document.createTextNode("sections done"))}else wh.textContent="No sections yet";
 var w=weak+tWrong;$("weak").textContent=w?w+(w===1?" weak spot":" weak spots")+" to go back to":(done?"No weak spots so far.":"Read each section, then answer its check question.");
 var next=-1;for(var j=0;j<n;j++){if(!S.done[j]){next=j;break}}
 var btn=$("continue");
 if(next===-1){btn.textContent=tAns.length<TEST.length?"Do the topic test":"See how I am doing";btn.onclick=function(){jump(tAns.length<TEST.length?"test":"progress")}}
 else{btn.textContent=(done||weak?"Continue: section ":"Start: section ")+(next+1);btn.onclick=function(){goSection(next)}}
 [].forEach.call(document.querySelectorAll(".sec"),function(x){var i2=Number(x.getAttribute("data-i"));x.classList.toggle("done",!!S.done[i2])});
 var pl=$("plist");clear(pl);
 SECS.forEach(function(s,i){var st=status(i),li=el("li");li.appendChild(el("span",{text:(i+1)+". "+s.heading}));
  var r=el("span",{class:"row",style:"margin:0;flex-wrap:nowrap"});r.appendChild(el("span",{class:"st "+(st==="new"?"":st),text:st==="done"?"Done":st==="weak"?"Weak":"Not started"}));
  if(st!=="done"){var go=el("button",{class:"ghost",type:"button",text:st==="weak"?"Revisit":"Go","aria-label":(st==="weak"?"Revisit":"Go to")+" section "+(i+1)});go.addEventListener("click",function(){goSection(i)});r.appendChild(go)}
  li.appendChild(r);pl.appendChild(li)});
 $("score").textContent=TEST.length?"Topic test: "+tGot+" of "+TEST.length+" right ("+tMarks+" of "+tTotal+" marks)":"";
}

/* ---- progress file (fallback for phones that do not keep it) ---- */
function say(t){$("say").textContent=t}
$("exp").addEventListener("click",function(){var data={board_id:B.board_id,generated_at:B.generated_at,saved_at:new Date().toISOString(),progress:S};
 var blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="progress-"+B.board_id+".json";document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},2000);say("Progress file saved to your downloads.")});
$("impBtn").addEventListener("click",function(){$("imp").click()});
$("imp").addEventListener("change",function(){var f=$("imp").files[0];if(!f)return;var r=new FileReader();r.onload=function(){try{var d=JSON.parse(r.result);if(d.board_id!==B.board_id)throw new Error("x");var p=d.progress||{};
  var ok={ans:{},done:{},weak:{}};Object.keys(p.ans||{}).forEach(function(k){var a=p.ans[k];if(a&&Array.isArray(a.given)&&typeof a.correct==="boolean")ok.ans[k]={given:a.given.map(String),correct:a.correct,at:String(a.at||"")}});
  Object.keys(p.done||{}).forEach(function(k){if(/^\d+$/.test(k))ok.done[k]=true});Object.keys(p.weak||{}).forEach(function(k){if(/^\d+$/.test(k))ok.weak[k]=true});
  S=ok;save();renderSections();renderTest();refresh();say("Progress loaded.")}catch(e){say("That file is not progress for this board.")}};r.readAsText(f)});
$("reset").addEventListener("click",function(){if(!confirm("Start this board again? Your answers on this phone will be cleared."))return;S={ans:{},done:{},weak:{}};drafts={};save();renderSections();renderTest();refresh();say("Cleared.")});

renderSections();renderTest();refresh();
})();
</script>
</body>
</html>
"""

_STOP = frozenset(
    "that this with from have your what when which their there they them then than into "
    "will would should could must also each other about after before where while these those "
    "used uses using does done being been were more most some such only very many much".split()
)
_WORD = re.compile(r"[a-z][a-z0-9]{3,}")
_AUTO = {"single_choice", "multi_choice", "true_false"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def plan_layout(board: Board) -> dict[str, Any]:
    """Tie each notes section to one check question and one explanation.

    Board JSON v1 does not store which question tests which section, so this
    matches them by shared words, best matches first, each used once. A section
    with no good match has no check question; it is marked read by a button.
    Questions not used as checks form the topic test (all of them if fewer than 3).
    """
    secs = board.notes.sections
    sw = [_words(s.heading + " " + " ".join(s.points)) for s in secs]
    qs = board.practice.questions

    def best_pairs(items: list[tuple[str, set[str], float]]) -> dict[int, str]:
        scored = []
        for i, words in enumerate(sw):
            for ident, other, bonus in items:
                shared = len(words & other)
                if shared >= 2:
                    scored.append((shared / math.sqrt(len(other) or 1) + bonus, i, ident))
        out: dict[int, str] = {}
        used: set[str] = set()
        for _score, i, ident in sorted(scored, key=lambda t: (-t[0], t[1], t[2])):
            if i not in out and ident not in used:
                out[i] = ident
                used.add(ident)
        return out

    def q_text(q) -> str:
        right = " ".join(
            str(v) for k, v in q.options.items() if k.upper() in re.split(r"[,\s]+", q.answer.upper())
        )
        return f"{q.question} {right} {q.answer if not q.options else ''} {q.explanation}"

    checks = best_pairs([(q.id, _words(q_text(q)), 0.5 if q.type in _AUTO else 0.0) for q in qs])
    explains = best_pairs(
        [(str(n), _words(f"{e.title} {e.explanation}"), 0.0) for n, e in enumerate(board.explainers)]
    )
    used = set(checks.values())
    test = [q.id for q in qs if q.id not in used]
    if len(test) < 3:
        test = [q.id for q in qs]
    return {
        "sections": [
            {"check": checks.get(i), "explain": int(explains[i]) if i in explains else None}
            for i in range(len(secs))
        ],
        "test": test,
    }


_MATH_TAGS = frozenset(
    "math mrow mi mn mo ms mtext mspace msub msup msubsup mfrac msqrt mroot mover munder "
    "munderover mtable mtr mtd mstyle mpadded mphantom mfenced menclose".split()
)
_MATH_ATTRS = frozenset(
    "xmlns display mathvariant stretchy fence separator accent accentunder lspace rspace "
    "linethickness columnalign rowspacing columnspacing open close separators notation width".split()
)


def latex_to_mathml(latex: str) -> str:
    """LaTeX to MathML for offline display, or "" if it cannot be done safely.

    The converter escapes text, and the result is parsed again and every element
    and attribute is checked against a MathML allow-list before it is used.
    """
    try:
        from defusedxml.ElementTree import fromstring
        from latex2mathml.converter import convert
    except ImportError:
        return ""
    try:
        out = convert(latex)
        root = fromstring(out)
    except Exception:
        return ""
    for node in root.iter():
        tag = str(node.tag).rsplit("}", 1)[-1]
        if tag not in _MATH_TAGS:
            return ""
        if any(a.rsplit("}", 1)[-1] not in _MATH_ATTRS for a in node.attrib):
            return ""
    return out


def _math_block(board: Board) -> str:
    parts = []
    for i, f in enumerate(board.notes.formulas):
        mathml = latex_to_mathml(f.latex)
        if mathml:
            mathml = mathml.replace('display="inline"', 'display="block"', 1)
            parts.append(f'<div data-i="{i}">{mathml}</div>')
    return "".join(parts)


@lru_cache(maxsize=1)
def _brand() -> dict:
    return json.loads(_BRAND_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _still_logo() -> str:
    """The V logo without its animation: calmer and lighter on low-end phones."""
    svg = _brand()["logo_svg"]
    svg = re.sub(r"<animate\w*\b[^>]*/>", "", svg)
    svg = re.sub(r"<animate\w*\b[^>]*>.*?</animate\w*>", "", svg, flags=re.S)
    return svg.replace('role="img" aria-label="Vex logo"', 'aria-hidden="true" focusable="false"', 1)


def _font_css() -> str:
    faces = (
        ("Barlow Condensed", 500, "bc500"),
        ("Barlow Condensed", 700, "bc700"),
        ("Barlow", 400, "b400"),
        ("Barlow", 700, "b700"),
    )
    fonts = _brand()["fonts"]
    return "".join(
        f'@font-face{{font-family:"{family}";font-weight:{weight};font-style:normal;'
        f'font-display:swap;src:url(data:font/woff2;base64,{fonts[key]}) format("woff2")}}'
        for family, weight, key in faces
    )


def _prefix_ids(svg: str, prefix: str = "pic-") -> str:
    """Keep the picture's ids from clashing with ids used by the page."""
    if not svg:
        return ""
    svg = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', svg)
    svg = re.sub(r"url\(#([^)\s]+)\)", lambda m: f"url(#{prefix}{m.group(1)})", svg)
    return re.sub(r'href="#([^"]+)"', lambda m: f'href="#{prefix}{m.group(1)}"', svg)


def _json_for_script(data: dict) -> str:
    """Serialise for a <script type=application/json> block."""
    text = json.dumps(data, ensure_ascii=False)
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_bundle(board: Board, svg: str = "") -> str:
    data = board.model_dump(mode="json")
    data["_plan"] = plan_layout(board)
    # One pass over the template, so text inside a value can never be read as a marker.
    values = {
        "__TITLE__": _escape_html(f"{board.topic} - {board.subject}"),
        "__FONTS__": _font_css(),
        "__LOGO__": _still_logo(),
        "__SVG__": _prefix_ids(svg or ""),
        "__BOARD_JSON__": _json_for_script(data),
        "__MATH__": _math_block(board),
    }
    return re.sub(
        r"__TITLE__|__FONTS__|__LOGO__|__SVG__|__BOARD_JSON__|__MATH__",
        lambda m: values[m.group(0)],
        _TEMPLATE,
    )


def write_bundle(store: BoardStore, board_id: str, out: Path | str | None = None) -> Path:
    board = store.load(board_id)
    svg = store.read_asset(board)
    target = Path(out) if out else store.board_dir(board_id) / f"{board_id}.html"
    atomic_write_text(target, render_bundle(board, svg))
    return target


__all__ = ["plan_layout", "render_bundle", "write_bundle"]
