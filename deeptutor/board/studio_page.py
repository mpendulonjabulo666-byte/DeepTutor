"""The studio page: plain HTML, no libraries, no network except this server."""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vboard</title>
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
select,textarea,input[type=text],input[type=number]{width:100%;min-height:46px;padding:8px 10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit}
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
.chatlog{max-height:300px;overflow:auto;margin:8px 0;display:flex;flex-direction:column;gap:6px}
.chatlog p{margin:0;padding:8px 10px;border-radius:10px;border:1px solid var(--line);max-width:92%}
.chatlog p.tutor{align-self:flex-end;background:var(--bg)}
.chatlog p.ai{align-self:flex-start;color:var(--ink)}
textarea{width:100%}
.bar{height:8px;border-radius:99px;background:var(--line);overflow:hidden;margin-top:10px}
.bar i{display:block;height:100%;width:40%;background:var(--accent);animation:slide 1.4s ease-in-out infinite alternate}
@keyframes slide{from{margin-left:0}to{margin-left:60%}}
@media (prefers-reduced-motion:reduce){.bar i{animation:none;width:100%}}
</style></head>
<body><main>
<h1>Vboard</h1>
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
  <label for="school">School or college (optional)</label>
  <input type="text" id="school" maxlength="120" placeholder="Majuba TVET College, Newcastle campus">
  <label for="area">Area (optional)</label>
  <input type="text" id="area" maxlength="120" placeholder="Newcastle, KwaZulu-Natal">
  <label for="textbooks">Textbooks your students use (optional)</label>
  <input type="text" id="textbooks" maxlength="400" placeholder="Title, author and publisher of each book, separated by semicolons">
  <p class="hint">The board then uses that area for examples and the books' terms and answer layout. Upload the pages you want the notes built from: the AI does not search for or copy books.</p>
  <div class="row"><button type="submit">Save</button></div>
  <p class="err" id="profileErr"></p>
 </form></section>

<section class="card" id="c2"><h2><span class="num">2</span>Your files</h2>
 <p class="hint" style="margin-top:0">Upload the subject guideline and past papers (PDF with real text, Word or text file). The board is built only from these.</p>
 <div class="row"><input type="file" id="file" accept=".pdf,.docx,.txt,.md"><button type="button" id="uploadBtn">Upload</button></div>
 <p class="err" id="fileErr"></p>
 <ul id="docList"></ul></section>

<section class="card" id="c2b"><h2><span class="num">+</span>Your pictures (optional)</h2>
 <p class="hint" style="margin-top:0">Add pictures you trust (PNG, JPG, WEBP or SVG, up to 3 MB each): a diagram from your textbook, a photo of a workshop tool. When you build a board you can choose one, and it is used as the board's picture exactly as you made it. The AI is told what you called it. If you tick the box, a PNG, JPG or WEBP is also sent to Google (Gemini) once so the AI can read what is labelled in it; an SVG's labels are read on this computer only. Pictures are kept on this computer.</p>
 <label for="picCap">What is it? (a short name)</label>
 <input type="text" id="picCap" maxlength="300" placeholder="Example: Dumpy level on a tripod, parts labelled">
 <label class="row" style="gap:8px;font-weight:400"><input type="checkbox" id="picAi" style="width:22px;height:22px"> Let the AI read this picture (it is sent to Google once). Leave it off for photos of people or private documents.</label>
 <div class="row"><input type="file" id="picFile" accept=".png,.jpg,.jpeg,.webp,.svg"><button type="button" id="picBtn">Add picture</button></div>
 <p class="err" id="picErr"></p>
 <ul id="picList"></ul></section>

<section class="card" id="c3"><h2><span class="num">3</span>Build a board</h2>
 <label for="topicSel">Topic</label>
 <select id="topicSel"></select>
 <input type="text" id="topicCustom" class="hidden" maxlength="200" placeholder="Type the topic" style="margin-top:8px">
 <label for="pickPic">Picture</label>
 <select id="pickPic"></select>
 <label for="focus">Tell the AI where to focus (optional)</label>
 <textarea id="focus" maxlength="1000" rows="3" placeholder="Example: go deep on levelling readings, keep the wording simple for Level 2, add an extra example on reduced levels."></textarea>
 <label for="qn">Number of questions</label>
 <input type="number" id="qn" min="3" max="30" value="10">
 <label style="font-weight:400;display:flex;gap:8px;align-items:center"><input type="checkbox" id="pic" checked> Draw a picture</label>
 <div class="row"><button type="button" id="buildBtn">Build board</button></div>
 <p class="err" id="buildErr"></p>
 <div id="jobBox" class="hidden"><p id="jobText"></p><div class="bar" id="jobBar"><i></i></div><ul id="jobWarn" class="warn"></ul></div></section>

<section class="card hidden" id="cEdit"><h2><span class="num">&#9998;</span><span id="editTitle">Edit the notes and questions</span></h2>
 <p class="hint" style="margin-top:0">Only you see this chat. Ask for a change to the notes or the practice questions, check it with <b>Open</b>, then press Approve. Students only ever see approved boards. Each change can be undone.</p>
 <div id="chatLog" class="chatlog"></div>
 <textarea id="chatIn" rows="2" maxlength="1500" placeholder="Example: Explain levelling more simply. Add a worked example with a backsight of 1.5 m. Add the other measuring instruments. Make question 3 easier."></textarea>
 <div class="row"><button type="button" id="chatSend">Send</button><button type="button" class="ghost" id="chatUndo">Undo last change</button><button type="button" class="ghost" id="chatClose">Close</button></div>
 <p class="err" id="chatErr"></p></section>

<section class="card" id="c4"><h2><span class="num">4</span>Your boards</h2>
 <p class="hint" style="margin-top:0">A new board is a draft. Read it against your guideline, then press Approve.</p>
 <ul id="boardList"></ul>
 <div id="trashBox" class="hidden"><h3 style="margin:16px 0 4px;font-size:15px">Trash</h3><ul id="trashList"></ul></div></section>
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
  if(S.profile){$("level").value=S.profile.level;$("programme").value=S.profile.programme;$("subject").value=S.profile.subject;$("school").value=S.profile.school||"";$("area").value=S.profile.area||"";$("textbooks").value=S.profile.textbooks||""}
}
function levels(){var ls=$("level");ls.textContent="";S.curricula[$("curriculum").value].levels.forEach(function(l){opt(ls,l,l)})}
function render(){
  var has=!!S.profile;
  $("profileView").classList.toggle("hidden",!has);$("profileForm").classList.toggle("hidden",has);
  if(has){var p=S.profile;$("profileText").textContent=S.curricula[p.curriculum].label+", "+p.level+(p.programme?" | "+p.programme:"")+" | "+p.subject}
  var dl=$("docList");dl.textContent="";
  if(!S.docs.length){var li=el("li");li.appendChild(el("span","No files yet.","hint"));dl.appendChild(li)}
  S.docs.forEach(function(d){var li=el("li");li.appendChild(el("span",d.name));var b=el("button","Remove","ghost");b.type="button";b.onclick=function(){post("/api/docs/"+d.id+"/delete").then(load).catch(function(e){$("fileErr").textContent=e.message})};li.appendChild(b);dl.appendChild(li)});
  var pl=$("picList");pl.textContent="";var ps=$("pickPic");ps.textContent="";opt(ps,"","Let Vboard draw one (exact templates first)");
  (S.pictures||[]).forEach(function(p){var li=el("li");li.appendChild(el("span",p.caption+(p.kind!=="svg"?(p.ai_read?" (AI may read it)":" (AI does not read it)"):"")));var b=el("button","Remove","ghost");b.type="button";b.onclick=function(){post("/api/pictures/"+p.id+"/delete").then(load).catch(function(e){$("picErr").textContent=e.message})};li.appendChild(b);pl.appendChild(li);opt(ps,p.id,"Use my picture: "+p.caption)});
  if(!(S.pictures||[]).length){var e0=el("li");e0.appendChild(el("span","No pictures yet.","hint"));pl.appendChild(e0)}
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
    var ed=el("button","Edit","ghost");ed.type="button";ed.onclick=function(){openEdit(b)};r.appendChild(ed);
    var dl=el("button","Delete","ghost");dl.type="button";dl.onclick=function(){if(confirm("Delete the board "+b.topic+"? It moves to Trash and you can restore it."))post("/api/boards/"+b.id+"/delete").then(load).catch(function(e){$("buildErr").textContent=e.message})};r.appendChild(dl);
    li.appendChild(r);bl.appendChild(li)});
  var tl=$("trashList");tl.textContent="";$("trashBox").classList.toggle("hidden",!(S.trash||[]).length);
  (S.trash||[]).forEach(function(t){var li=el("li");li.appendChild(el("span",t.id));var rb=el("button","Restore","ghost");rb.type="button";rb.onclick=function(){post("/api/trash/"+t.key+"/restore").then(load).catch(function(e){$("buildErr").textContent=e.message})};li.appendChild(rb);tl.appendChild(li)});
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
  post("/api/profile",{curriculum:$("curriculum").value,level:$("level").value,programme:$("programme").value,subject:$("subject").value,school:$("school").value,area:$("area").value,textbooks:$("textbooks").value}).then(load).catch(function(e){$("profileErr").textContent=e.message})};
$("uploadBtn").onclick=function(){$("fileErr").textContent="";var f=$("file").files[0];if(!f){$("fileErr").textContent="Choose a file first.";return}
  $("uploadBtn").disabled=true;$("fileErr").textContent="Reading the file. A scanned PDF is read with Gemini and can take a few minutes. Keep this page open.";$("fileErr").style.color="var(--mute)";
  api("POST","/api/docs",f,{"X-Filename":encodeURIComponent(f.name),"Content-Type":"application/octet-stream"}).then(function(){$("file").value="";$("fileErr").style.color="";$("fileErr").textContent="";return load()}).catch(function(e){$("fileErr").style.color="";$("fileErr").textContent=e.message}).then(function(){$("uploadBtn").disabled=false})};
$("topicSel").onchange=function(){$("topicCustom").classList.toggle("hidden",$("topicSel").value!=="__custom__")};
$("buildBtn").onclick=function(){$("buildErr").textContent="";
  var topic=$("topicSel").value==="__custom__"?$("topicCustom").value:$("topicSel").value;
  post("/api/build",{topic:topic,questions:parseInt($("qn").value,10)||10,with_picture:$("pic").checked,focus:$("focus").value,picture_id:$("pickPic").value}).then(function(d){S.job=d.job;job(d.job)}).catch(function(e){$("buildErr").textContent=e.message})};
$("picBtn").onclick=function(){$("picErr").textContent="";var f=$("picFile").files[0];if(!f){$("picErr").textContent="Choose a picture first.";return}
  api("POST","/api/pictures",f,{"X-Filename":encodeURIComponent(f.name),"X-Caption":encodeURIComponent($("picCap").value),"X-AI-Read":$("picAi").checked?"1":"0","Content-Type":"application/octet-stream"}).then(function(){$("picFile").value="";$("picCap").value="";return load()}).catch(function(e){$("picErr").textContent=e.message})};
var editId=null;
function showChat(h){var lg=$("chatLog");lg.textContent="";(h||[]).forEach(function(m){lg.appendChild(el("p",m.text,m.role))});lg.scrollTop=lg.scrollHeight}
function openEdit(b){editId=b.id;$("editTitle").textContent="Edit the notes and questions: "+b.topic;$("cEdit").classList.remove("hidden");$("chatErr").textContent="";
  api("GET","/api/boards/"+b.id+"/chat").then(function(d){showChat(d.history)});$("cEdit").scrollIntoView({behavior:"smooth"})}
$("chatClose").onclick=function(){$("cEdit").classList.add("hidden");editId=null};
$("chatSend").onclick=function(){var m=$("chatIn").value.trim();if(!m||!editId)return;$("chatErr").textContent="";$("chatSend").disabled=true;$("chatSend").textContent="Working...";
  post("/api/boards/"+editId+"/chat",{message:m}).then(function(d){$("chatIn").value="";showChat(d.history);return load()}).catch(function(e){$("chatErr").textContent=e.message}).then(function(){$("chatSend").disabled=false;$("chatSend").textContent="Send"})};
$("chatUndo").onclick=function(){if(!editId)return;post("/api/boards/"+editId+"/undo").then(function(d){showChat(d.history);if(!d.ok)$("chatErr").textContent="Nothing to undo.";return load()}).catch(function(e){$("chatErr").textContent=e.message})};
load();
})();
</script></body></html>
"""
