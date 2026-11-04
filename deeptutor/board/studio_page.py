"""The studio page: plain HTML, no libraries, no network except this server."""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learning Board Studio</title>
<style>
:root{--bg:#f6f8fb;--card:#fff;--ink:#14213d;--mute:#5b6677;--line:#dde3ec;--brand:#1b3a6b;--accent:#4c9a2a;--bad:#b3261e;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#0e1522;--card:#16202f;--ink:#e8edf5;--mute:#9aa7ba;--line:#2a3649;--brand:#8db4ff;--accent:#7bd155;--bad:#ff8a80;--warn:#f0c36a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 system-ui,Segoe UI,Roboto,sans-serif}
main{max-width:46rem;margin:0 auto;padding:16px 16px 64px}
h1{font-size:1.5rem;margin:12px 0 2px;color:var(--brand)}
.sub{color:var(--mute);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}
.card h2{font-size:1.05rem;margin:0 0 10px}
.num{display:inline-block;width:1.6rem;height:1.6rem;line-height:1.6rem;text-align:center;border-radius:50%;background:var(--brand);color:var(--bg);font-size:.9rem;margin-right:8px}
label{display:block;font-weight:600;margin:12px 0 4px}
select,input[type=text],input[type=number]{width:100%;min-height:46px;padding:8px 10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit}
button,.btn{min-height:46px;padding:8px 16px;border:0;border-radius:10px;background:var(--brand);color:var(--bg);font:inherit;font-weight:600;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
button.ghost,.btn.ghost{background:transparent;color:var(--brand);border:1px solid var(--line)}
button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
.hint{color:var(--mute);font-size:.92rem;margin:6px 0 0}
.err{color:var(--bad);font-weight:600;margin:10px 0 0}
.warn{color:var(--warn);font-size:.92rem}
ul{list-style:none;padding:0;margin:8px 0 0}
li{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 0;border-top:1px solid var(--line);flex-wrap:wrap}
li:first-child{border-top:0}
.pill{font-size:.78rem;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}
.pill.ok{color:var(--accent);border-color:var(--accent)}
.hidden{display:none}
.bar{height:8px;border-radius:99px;background:var(--line);overflow:hidden;margin-top:10px}
.bar i{display:block;height:100%;width:40%;background:var(--accent);animation:slide 1.4s ease-in-out infinite alternate}
@keyframes slide{from{margin-left:0}to{margin-left:60%}}
@media (prefers-reduced-motion:reduce){.bar i{animation:none;width:100%}}
</style></head>
<body><main>
<h1>Learning Board Studio</h1>
<p class="sub">Pick your level once, upload your guideline, choose a topic, press Build. Runs on this computer only.</p>

<section class="card" id="c1"><h2><span class="num">1</span>Your level</h2>
 <div id="profileView" class="hidden"><div id="profileText"></div>
  <div class="row"><button class="ghost" id="changeBtn" type="button">Change</button></div></div>
 <form id="profileForm" class="hidden">
  <label for="curriculum">Where do you study?</label>
  <select id="curriculum"></select>
  <label for="level">Level</label>
  <select id="level"></select>
  <label for="programme">Programme (optional)</label>
  <input type="text" id="programme" maxlength="120" placeholder="Civil Engineering and Building Construction">
  <label for="subject">Subject</label>
  <input type="text" id="subject" maxlength="120" placeholder="Construction Planning">
  <p class="hint">The more the board knows about you, the fewer guesses it makes.</p>
  <div class="row"><button type="submit">Save</button></div>
  <p class="err" id="profileErr"></p>
 </form></section>

<section class="card" id="c2"><h2><span class="num">2</span>Your files</h2>
 <p class="hint" style="margin-top:0">Upload the subject guideline and past papers (PDF with real text, Word or text file). The board is built only from these.</p>
 <div class="row"><input type="file" id="file" accept=".pdf,.docx,.txt,.md"><button type="button" id="uploadBtn">Upload</button></div>
 <p class="err" id="fileErr"></p>
 <ul id="docList"></ul></section>

<section class="card" id="c3"><h2><span class="num">3</span>Build a board</h2>
 <label for="topicSel">Topic</label>
 <select id="topicSel"></select>
 <input type="text" id="topicCustom" class="hidden" maxlength="200" placeholder="Type the topic" style="margin-top:8px">
 <label for="qn">Number of questions</label>
 <input type="number" id="qn" min="3" max="30" value="10">
 <label style="font-weight:400;display:flex;gap:8px;align-items:center"><input type="checkbox" id="pic" checked> Draw a picture</label>
 <div class="row"><button type="button" id="buildBtn">Build board</button></div>
 <p class="err" id="buildErr"></p>
 <div id="jobBox" class="hidden"><p id="jobText"></p><div class="bar" id="jobBar"><i></i></div><ul id="jobWarn" class="warn"></ul></div></section>

<section class="card" id="c4"><h2><span class="num">4</span>Your boards</h2>
 <p class="hint" style="margin-top:0">A new board is a draft. Read it against your guideline, then press Approve.</p>
 <ul id="boardList"></ul></section>
</main>
<script>
(function(){
var S=null,polling=null;
function $(i){return document.getElementById(i)}
function api(method,path,body,headers){
  var o={method:method,headers:Object.assign({"X-Studio":"1"},headers||{})};
  if(body!==undefined){o.body=body;}
  return fetch(path,o).then(function(r){return r.json().then(function(d){if(!r.ok){throw new Error(d.error||"Something went wrong.")}return d})});
}
function post(path,obj){return api("POST",path,JSON.stringify(obj||{}),{"Content-Type":"application/json"})}
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function opt(sel,value,text){var o=document.createElement("option");o.value=value;o.textContent=text;sel.appendChild(o)}
function fill(){
  var cs=$("curriculum");cs.textContent="";
  Object.keys(S.curricula).forEach(function(k){opt(cs,k,S.curricula[k].label)});
  if(S.profile)cs.value=S.profile.curriculum;
  levels();
  if(S.profile){$("level").value=S.profile.level;$("programme").value=S.profile.programme;$("subject").value=S.profile.subject}
}
function levels(){var ls=$("level");ls.textContent="";S.curricula[$("curriculum").value].levels.forEach(function(l){opt(ls,l,l)})}
function render(){
  var has=!!S.profile;
  $("profileView").classList.toggle("hidden",!has);$("profileForm").classList.toggle("hidden",has);
  if(has){var p=S.profile;$("profileText").textContent=S.curricula[p.curriculum].label+", "+p.level+(p.programme?" | "+p.programme:"")+" | "+p.subject}
  var dl=$("docList");dl.textContent="";
  if(!S.docs.length){var li=el("li");li.appendChild(el("span","No files yet.","hint"));dl.appendChild(li)}
  S.docs.forEach(function(d){var li=el("li");li.appendChild(el("span",d.name));var b=el("button","Remove","ghost");b.type="button";b.onclick=function(){post("/api/docs/"+d.id+"/delete").then(load).catch(function(e){$("fileErr").textContent=e.message})};li.appendChild(b);dl.appendChild(li)});
  var ts=$("topicSel"),keep=ts.value;ts.textContent="";
  S.topics.forEach(function(t){opt(ts,t.name,"Topic "+t.number+": "+t.name+(t.weight?" ("+t.weight+"%)":""))});
  opt(ts,"__custom__","Type my own topic...");
  if(keep&&Array.prototype.some.call(ts.options,function(o){return o.value===keep}))ts.value=keep;
  $("topicCustom").classList.toggle("hidden",ts.value!=="__custom__");
  var bl=$("boardList");bl.textContent="";
  if(!S.boards.length){var e=el("li");e.appendChild(el("span","No boards yet.","hint"));bl.appendChild(e)}
  S.boards.forEach(function(b){
    var li=el("li");var left=el("span");left.appendChild(el("strong",b.topic));left.appendChild(document.createTextNode(" "));left.appendChild(el("span",b.status==="reviewed"?"approved":"draft","pill"+(b.status==="reviewed"?" ok":"")));li.appendChild(left);
    var r=el("span");r.style.display="flex";r.style.gap="8px";r.style.flexWrap="wrap";
    function link(t,h,dl){var a=el("a",t,"btn ghost");a.href=h;if(dl)a.download=dl;else a.target="_blank";a.rel="noopener";r.appendChild(a)}
    link("Open","/b/"+b.id+".html");link("PDF","/b/"+b.id+".pdf",b.id+".pdf");link("Phone file","/b/"+b.id+".html",b.id+".html");
    if(b.status!=="reviewed"){var ap=el("button","Approve");ap.type="button";ap.onclick=function(){post("/api/boards/"+b.id+"/approve").then(load).catch(function(e){$("buildErr").textContent=e.message})};r.appendChild(ap)}
    li.appendChild(r);bl.appendChild(li)});
  job(S.job);
}
function job(j){
  var box=$("jobBox");
  if(!j){box.classList.add("hidden");return}
  box.classList.remove("hidden");
  var run=j.status==="running";$("jobBar").classList.toggle("hidden",!run);$("buildBtn").disabled=run;
  var t=run?"Building "+j.topic+"... "+j.seconds+"s. This usually takes one to three minutes.":j.status==="done"?"Done: "+j.topic+". It is in Your boards below. Check it before you approve.":"Build failed: "+j.error;
  $("jobText").textContent=t;
  var w=$("jobWarn");w.textContent="";(j.warnings||[]).forEach(function(x){w.appendChild(el("li",x))});
  if(run&&!polling){polling=setInterval(function(){api("GET","/api/jobs/"+j.id).then(function(n){job(n);if(n.status!=="running"){clearInterval(polling);polling=null;load()}}).catch(function(){})},2000)}
}
function load(){return api("GET","/api/state").then(function(s){S=s;fill();render()}).catch(function(e){$("buildErr").textContent=e.message})}
$("curriculum").onchange=levels;
$("changeBtn").onclick=function(){$("profileView").classList.add("hidden");$("profileForm").classList.remove("hidden")};
$("profileForm").onsubmit=function(ev){ev.preventDefault();$("profileErr").textContent="";
  post("/api/profile",{curriculum:$("curriculum").value,level:$("level").value,programme:$("programme").value,subject:$("subject").value}).then(load).catch(function(e){$("profileErr").textContent=e.message})};
$("uploadBtn").onclick=function(){$("fileErr").textContent="";var f=$("file").files[0];if(!f){$("fileErr").textContent="Choose a file first.";return}
  $("uploadBtn").disabled=true;$("fileErr").textContent="Reading the file. A scanned PDF is read with Gemini and can take a few minutes. Keep this page open.";$("fileErr").style.color="var(--mute)";
  api("POST","/api/docs",f,{"X-Filename":encodeURIComponent(f.name),"Content-Type":"application/octet-stream"}).then(function(){$("file").value="";$("fileErr").style.color="";$("fileErr").textContent="";return load()}).catch(function(e){$("fileErr").style.color="";$("fileErr").textContent=e.message}).then(function(){$("uploadBtn").disabled=false})};
$("topicSel").onchange=function(){$("topicCustom").classList.toggle("hidden",$("topicSel").value!=="__custom__")};
$("buildBtn").onclick=function(){$("buildErr").textContent="";
  var topic=$("topicSel").value==="__custom__"?$("topicCustom").value:$("topicSel").value;
  post("/api/build",{topic:topic,questions:parseInt($("qn").value,10)||10,with_picture:$("pic").checked}).then(function(d){S.job=d.job;job(d.job)}).catch(function(e){$("buildErr").textContent=e.message})};
load();
})();
</script></body></html>
"""
