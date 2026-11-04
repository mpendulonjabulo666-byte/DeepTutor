"""Write a board as one self-contained HTML file for an offline phone.

No network request, no external font or library, no service worker. Copy the
file to a phone, open it in Chrome, and it works in airplane mode.

All board text is inserted with ``textContent``. The only markup placed in the
page is the SVG, which has already been through ``sanitize_svg``.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from deeptutor.services.file_io import atomic_write_text

from .schema import Board
from .store import BoardStore

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f7f5;--card:#fff;--ink:#1b1f24;--mute:#5b6670;--line:#d5dbd8;--accent:#0f6b5c;--accent-ink:#fff;--ok:#1b7a3a;--bad:#b3261e;--warn:#fff4e0}
@media (prefers-color-scheme:dark){:root{--bg:#111514;--card:#1b201f;--ink:#e8ecea;--mute:#9aa6a1;--line:#33403c;--accent:#4fc3ad;--accent-ink:#06211c;--ok:#5fd17f;--bad:#ff8a80;--warn:#3a2f17}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
body{padding-bottom:calc(68px + env(safe-area-inset-bottom))}
header{padding:14px 16px 6px}
header h1{font-size:1.25rem;line-height:1.3;margin:0}
header p{margin:2px 0 0;color:var(--mute);font-size:.9rem}
main{padding:8px 16px 16px;max-width:46rem;margin:0 auto}
section[hidden]{display:none}
h2{font-size:1.1rem;margin:16px 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0}
.banner{background:var(--warn);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:10px 16px;font-size:.9rem}
.banner ul{margin:6px 0 0;padding-left:18px}
.banner summary{padding:0;min-height:0;font-weight:600}
figure{margin:8px 0}
figure svg{width:100%;height:auto;max-height:70vh;background:#fff;border:1px solid var(--line);border-radius:12px}
figcaption{color:var(--mute);font-size:.92rem;margin-top:6px}
details{border:1px solid var(--line);border-radius:12px;background:var(--card);margin:8px 0}
summary{padding:12px 14px;font-weight:600;min-height:44px;cursor:pointer}
details ul{margin:0;padding:0 14px 12px 32px}
details li{margin:4px 0}
.formula code{display:block;font:0.92rem ui-monospace,Menlo,Consolas,monospace;overflow-x:auto;padding:6px 0}
dt{font-weight:600;margin-top:10px}
dd{margin:2px 0 0;color:var(--mute)}
button{font:inherit;min-height:44px;padding:8px 16px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:600}
button:disabled{opacity:.5}
.opt:disabled{opacity:1;cursor:default}
.opts{display:grid;gap:8px;margin:10px 0}
.opt{display:flex;align-items:flex-start;gap:10px;text-align:left;width:100%}
.opt.sel{border-color:var(--accent);outline:2px solid var(--accent)}
.opt.right{border-color:var(--ok);outline:2px solid var(--ok)}
.opt.wrong{border-color:var(--bad);outline:2px solid var(--bad)}
.opt b{min-width:1.4em}
textarea,input[type=text]{width:100%;font:inherit;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);min-height:44px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.meta{color:var(--mute);font-size:.88rem}
.good{color:var(--ok);font-weight:600}.badc{color:var(--bad);font-weight:600}
.path li{margin:8px 0}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--line);font-size:.8rem;margin-left:6px}
nav{position:fixed;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(4,1fr);background:var(--card);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}
nav button{border:0;border-radius:0;min-height:56px;background:transparent;font-size:.85rem;color:var(--mute)}
nav button[aria-selected=true]{color:var(--accent);font-weight:700;box-shadow:inset 0 3px 0 var(--accent)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<header><h1 id="title"></h1><p id="meta"></p></header>
<div id="banners"></div>
<main>
<section id="s-picture" role="tabpanel"></section>
<section id="s-notes" role="tabpanel" hidden></section>
<section id="s-practice" role="tabpanel" hidden></section>
<section id="s-progress" role="tabpanel" hidden></section>
</main>
<nav role="tablist" aria-label="Board sections">
<button role="tab" data-t="picture" aria-selected="true">Picture</button>
<button role="tab" data-t="notes" aria-selected="false">Notes</button>
<button role="tab" data-t="practice" aria-selected="false">Practice</button>
<button role="tab" data-t="progress" aria-selected="false">Progress</button>
</nav>
<div id="picture-svg" hidden>__SVG__</div>
<script type="application/json" id="board-data">__BOARD_JSON__</script>
<script>
(function(){
"use strict";
var B=JSON.parse(document.getElementById("board-data").textContent);
var KEY="dtboard:"+B.board_id+":"+B.generated_at;
var mem={}, store=null;
try{localStorage.setItem("__t","1");localStorage.removeItem("__t");store=localStorage;}catch(e){store=null;}
function load(){try{var r=store&&store.getItem(KEY);return r?JSON.parse(r):{}}catch(e){return mem}}
var answers=load();
function save(){mem=answers;try{if(store)store.setItem(KEY,JSON.stringify(answers))}catch(e){}}
function el(tag,attrs,kids){var n=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="text")n.textContent=attrs[k];else if(k==="class")n.className=attrs[k];else n.setAttribute(k,attrs[k]);}(kids||[]).forEach(function(c){n.appendChild(c)});return n}
function clear(n){while(n.firstChild)n.removeChild(n.firstChild)}
function norm(s){return String(s||"").trim().toLowerCase().replace(/\s+/g," ")}

document.getElementById("title").textContent=B.topic;
document.getElementById("meta").textContent=B.subject;
var ban=document.getElementById("banners");
if(B.review&&B.review.status!=="reviewed"){ban.appendChild(el("div",{class:"banner",role:"note",text:"Draft. A teacher or peer educator has not checked this board yet. Check answers against your guideline."}))}
if(B.warnings&&B.warnings.length){var b=el("details",{class:"banner"},[el("summary",{text:"Notes from the builder ("+B.warnings.length+")"})]);var ul=el("ul");B.warnings.forEach(function(w){ul.appendChild(el("li",{text:w}))});b.appendChild(ul);ban.appendChild(b)}

/* Picture */
(function(){var s=document.getElementById("s-picture");var holder=document.getElementById("picture-svg");var svg=holder.querySelector("svg");
 if(!svg){s.appendChild(el("p",{class:"meta",text:"No picture for this topic."}));return}
 var fig=el("figure");svg.setAttribute("role","img");svg.setAttribute("aria-label",B.picture.alt||B.picture.title||"Diagram");
 fig.appendChild(svg);
 if(B.picture.caption||B.picture.title)fig.appendChild(el("figcaption",{text:B.picture.caption||B.picture.title}));
 if(B.picture.title)s.appendChild(el("h2",{text:B.picture.title}));
 s.appendChild(fig);holder.remove();})();

/* Notes */
(function(){var s=document.getElementById("s-notes"),n=B.notes||{};
 if(n.summary)s.appendChild(el("div",{class:"card"},[el("p",{text:n.summary})]));
 (n.sections||[]).forEach(function(sec,i){var d=el("details");if(i===0)d.open=true;d.appendChild(el("summary",{text:sec.heading}));var ul=el("ul");(sec.points||[]).forEach(function(p){ul.appendChild(el("li",{text:p}))});d.appendChild(ul);s.appendChild(d)});
 if((n.formulas||[]).length){s.appendChild(el("h2",{text:"Formulas"}));n.formulas.forEach(function(f){var c=el("div",{class:"card formula"},[el("strong",{text:f.name}),el("code",{text:f.latex})]);if(f.explanation)c.appendChild(el("div",{class:"meta",text:f.explanation}));s.appendChild(c)})}
 if((n.key_terms||[]).length){s.appendChild(el("h2",{text:"Key terms"}));var dl=el("dl");n.key_terms.forEach(function(t){dl.appendChild(el("dt",{text:t.term}));dl.appendChild(el("dd",{text:t.meaning}))});s.appendChild(dl)}
 if(!s.firstChild)s.appendChild(el("p",{class:"meta",text:"No notes for this topic."}));})();

/* Practice */
var qs=(B.practice&&B.practice.questions)||[];var qi=0;
var P=document.getElementById("s-practice"),PR=document.getElementById("s-progress");
function isChoice(q){return q.type==="single_choice"||q.type==="multi_choice"}
function keys(a){return String(a).split(/[,\s]+/).filter(Boolean).map(function(x){return x.toUpperCase()}).sort()}
function same(a,b){return a.length===b.length&&a.every(function(v,i){return v===b[i]})}
function renderPractice(){
 clear(P);
 if(!qs.length){P.appendChild(el("p",{class:"meta",text:"No practice questions for this topic."}));return}
 var q=qs[qi],a=answers[q.id];
 P.appendChild(el("p",{class:"meta",text:"Question "+(qi+1)+" of "+qs.length+" · "+q.marks+(q.marks===1?" mark":" marks")}));
 P.appendChild(el("div",{class:"card"},[el("p",{text:q.question})]));
 var draft=draftFor(q);
 if(isChoice(q)){
  var box=el("div",{class:"opts"});var multi=q.type==="multi_choice";var right=keys(q.answer);
  Object.keys(q.options).sort().forEach(function(k){
   var cls="opt";if(a){if(right.indexOf(k.toUpperCase())>-1)cls+=" right";else if(a.given.indexOf(k.toUpperCase())>-1)cls+=" wrong"}else if(draft.sel.indexOf(k.toUpperCase())>-1)cls+=" sel";
   var b=el("button",{class:cls,type:"button","aria-pressed":String(draft.sel.indexOf(k.toUpperCase())>-1)},[el("b",{text:k+"."}),el("span",{text:q.options[k]})]);
   if(a)b.disabled=true;
   b.addEventListener("click",function(){var K=k.toUpperCase();var i=draft.sel.indexOf(K);if(multi){if(i>-1)draft.sel.splice(i,1);else draft.sel.push(K)}else draft.sel=[K];renderPractice()});
   box.appendChild(b)});
  P.appendChild(box);
  if(multi&&!a)P.appendChild(el("p",{class:"meta",text:"Choose all that apply."}));
  if(!a){var c=el("button",{class:"primary",type:"button",text:"Check answer"});c.disabled=!draft.sel.length;c.addEventListener("click",function(){var g=draft.sel.slice().sort();record(q,g,same(g,right))});P.appendChild(c)}
 }else if(q.type==="true_false"){
  var box2=el("div",{class:"opts"});["true","false"].forEach(function(v){
   var cls="opt";if(a){if(q.answer.toLowerCase()===v)cls+=" right";else if(a.given[0]===v)cls+=" wrong"}
   var b=el("button",{class:cls,type:"button",text:v==="true"?"True":"False"});if(a)b.disabled=true;
   b.addEventListener("click",function(){record(q,[v],q.answer.toLowerCase()===v)});box2.appendChild(b)});P.appendChild(box2);
 }else{
  if(!a){var ta=q.type==="fill_blank"?el("input",{type:"text","aria-label":"Your answer",autocomplete:"off"}):el("textarea",{rows:"4","aria-label":"Your answer"});ta.value=draft.text;ta.addEventListener("input",function(){draft.text=ta.value});P.appendChild(ta);
   var show=el("button",{class:"primary",type:"button",text:"Show model answer"});show.addEventListener("click",function(){draft.reveal=true;renderPractice()});P.appendChild(show);
   if(draft.reveal){P.appendChild(el("div",{class:"card"},[el("strong",{text:"Model answer"}),el("p",{text:q.answer})]));
    var row=el("div",{class:"row"});var yes=el("button",{type:"button",text:"I got it right"}),no=el("button",{type:"button",text:"Not yet"});
    yes.addEventListener("click",function(){record(q,[draft.text],true)});no.addEventListener("click",function(){record(q,[draft.text],false)});row.appendChild(yes);row.appendChild(no);P.appendChild(row)}
  }
 }
 if(a){
  var msg=a.correct?el("p",{class:"good",text:"Correct"}):el("p",{class:"badc",text:"Not correct"});P.appendChild(msg);
  if(!isChoice(q)&&q.type!=="true_false")P.appendChild(el("div",{class:"card"},[el("strong",{text:"Model answer"}),el("p",{text:q.answer})]));
  if(q.explanation)P.appendChild(el("div",{class:"card"},[el("strong",{text:"Why"}),el("p",{text:q.explanation})]));
  var redo=el("button",{type:"button",text:"Try again"});redo.addEventListener("click",function(){delete answers[q.id];delete drafts[q.id];save();renderPractice();renderProgress()});P.appendChild(redo);
 }
 var nav=el("div",{class:"row"});var prev=el("button",{type:"button",text:"Back"}),next=el("button",{class:"primary",type:"button",text:qi===qs.length-1?"Finish":"Next"});
 prev.disabled=qi===0;prev.addEventListener("click",function(){qi--;renderPractice()});
 next.addEventListener("click",function(){if(qi<qs.length-1){qi++;renderPractice()}else show("progress")});
 nav.appendChild(prev);nav.appendChild(next);P.appendChild(nav);
 window.scrollTo(0,0);
}
var drafts={};
function draftFor(q){return drafts[q.id]||(drafts[q.id]={sel:[],text:"",reveal:false})}
function record(q,given,correct){answers[q.id]={given:given,correct:!!correct,at:new Date().toISOString()};save();renderPractice();renderProgress()}

/* Progress */
function stats(){var total=0,got=0,done=0,byKp={};
 qs.forEach(function(q){total+=q.marks;var a=answers[q.id];var k=q.knowledge_point_id||"";var s=byKp[k]||(byKp[k]={n:0,done:0,right:0});s.n++;if(a){done++;s.done++;if(a.correct){got+=q.marks;s.right++}}});
 return {total:total,got:got,done:done,byKp:byKp}}
function renderProgress(){
 clear(PR);var st=stats();
 PR.appendChild(el("div",{class:"card"},[el("strong",{text:"Score: "+st.got+" of "+st.total+" marks"}),el("div",{class:"meta",text:st.done+" of "+qs.length+" questions answered"})]));
 var path=(B.progress&&B.progress.mastery_path)||[];var weak=[];
 if(path.length){PR.appendChild(el("h2",{text:"Mastery path"}));var ol=el("ol",{class:"path"});
  path.forEach(function(m){var s=st.byKp[m.id]||{n:0,done:0,right:0};var status="new";
   if(s.n&&s.done===s.n&&s.right===s.n)status="mastered";else if(s.done)status="learning";
   if(s.done&&s.right<s.done)weak.push(m.title);
   var li=el("li",{},[el("span",{text:m.title}),el("span",{class:"pill",text:status})]);if(s.n)li.appendChild(el("div",{class:"meta",text:s.right+" of "+s.n+" right"}));ol.appendChild(li)});PR.appendChild(ol)}
 var loose=st.byKp[""];if(loose&&loose.done>loose.right){var n0=loose.done-loose.right;weak.push(n0+(n0===1?" other question":" other questions")+" missed")}
 PR.appendChild(el("h2",{text:"Weak areas"}));
 if(weak.length){var u=el("ul");weak.forEach(function(w){u.appendChild(el("li",{text:w}))});PR.appendChild(u)}else PR.appendChild(el("p",{class:"meta",text:st.done?"None so far.":"Answer some questions to see this."}));
 PR.appendChild(el("h2",{text:"Your progress file"}));
 PR.appendChild(el("p",{class:"meta",text:store?"Progress is saved on this phone in this browser.":"This browser cannot keep progress after you close the page. Use Save progress file."}));
 var row=el("div",{class:"row"});
 var ex=el("button",{type:"button",text:"Save progress file"});ex.addEventListener("click",exportProgress);
 var im=el("button",{type:"button",text:"Load progress file"});var inp=el("input",{type:"file",accept:"application/json,.json",hidden:"hidden"});
 im.addEventListener("click",function(){inp.click()});inp.addEventListener("change",function(){importProgress(inp.files&&inp.files[0])});
 var rs=el("button",{type:"button",text:"Start over"});rs.addEventListener("click",function(){if(confirm("Delete all your answers for this board?")){answers={};drafts={};save();renderPractice();renderProgress()}});
 [ex,im,rs,inp].forEach(function(n){row.appendChild(n)});PR.appendChild(row);
 PR.appendChild(el("p",{class:"meta",id:"pmsg",role:"status"}));
}
function say(t){var m=document.getElementById("pmsg");if(m)m.textContent=t}
function exportProgress(){
 var data={board_id:B.board_id,generated_at:B.generated_at,exported_at:new Date().toISOString(),answers:answers};
 var blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});var a=document.createElement("a");
 a.href=URL.createObjectURL(blob);a.download="progress-"+B.board_id+".json";document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},2000);say("Progress file saved to your downloads.")}
function importProgress(f){
 if(!f)return;var r=new FileReader();r.onload=function(){try{var d=JSON.parse(r.result);
  if(!d||d.board_id!==B.board_id||typeof d.answers!=="object"||d.answers===null){say("That file is for a different board.");return}
  var ok={},ids={};qs.forEach(function(q){ids[q.id]=1});
  Object.keys(d.answers).forEach(function(k){var a=d.answers[k];if(ids[k]&&a&&Array.isArray(a.given)&&typeof a.correct==="boolean")ok[k]={given:a.given.map(String),correct:a.correct,at:String(a.at||"")}});
  answers=ok;save();renderPractice();renderProgress();say("Progress loaded.")}catch(e){say("That file could not be read.")}};r.readAsText(f)}

/* Tabs */
var tabs=[].slice.call(document.querySelectorAll("nav button"));
function show(name){tabs.forEach(function(t){t.setAttribute("aria-selected",String(t.getAttribute("data-t")===name))});
 ["picture","notes","practice","progress"].forEach(function(n){document.getElementById("s-"+n).hidden=n!==name});window.scrollTo(0,0)}
tabs.forEach(function(t){t.addEventListener("click",function(){show(t.getAttribute("data-t"))})});
renderPractice();renderProgress();
})();
</script>
</body>
</html>
"""


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
    # One pass over the template, so text inside a value can never be read as a marker.
    values = {
        "__TITLE__": _escape_html(f"{board.topic} - {board.subject}"),
        "__SVG__": svg or "",
        "__BOARD_JSON__": _json_for_script(board.model_dump(mode="json")),
    }
    return re.sub(r"__TITLE__|__SVG__|__BOARD_JSON__", lambda m: values[m.group(0)], _TEMPLATE)


def write_bundle(store: BoardStore, board_id: str, out: Path | str | None = None) -> Path:
    board = store.load(board_id)
    svg = store.read_asset(board)
    target = Path(out) if out else store.board_dir(board_id) / f"{board_id}.html"
    atomic_write_text(target, render_bundle(board, svg))
    return target


__all__ = ["render_bundle", "write_bundle"]
