"""Write a board as one self-contained HTML file for an offline phone.

No network request, no external font or library, no service worker. Copy the
file to a phone, open it in Chrome, and it works in airplane mode.

The page uses the Vex Cipher look: the animated Vex "V" logo and the Barlow
fonts are embedded from ``brand.json`` (fonts under the SIL OFL, see
``FONT_LICENSE.md``).

All board text is inserted with ``textContent``. The only generated markup
placed in the page is the picture SVG, which has already been through
``sanitize_svg``; its ids are prefixed so they cannot clash with the page.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re

from deeptutor.services.file_io import atomic_write_text

from .schema import Board
from .store import BoardStore

_BRAND_FILE = Path(__file__).with_name("brand.json")

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#07070a">
<title>__TITLE__</title>
<style>__FONTS__</style>
<style>
:root{--bg:#07070a;--panel:#0c0c10;--card:#0f0f14;--card2:#14141a;--line:rgba(255,122,24,.34);--line2:#24242c;--ink:#f3f3f5;--mute:#9b9ba8;--or:#ff7a18;--or2:#ff4d00;--amb:#ffb347;--ok:#2fd26b;--bad:#ff5a4f;--r:18px;
--ui:"Barlow Condensed","Bahnschrift","Roboto Condensed","Arial Narrow",system-ui,sans-serif;--tx:"Barlow",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--stick:0px}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{scroll-behavior:smooth}
html,body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 var(--tx)}
body{background:radial-gradient(1200px 600px at 85% -10%,rgba(255,90,0,.10),transparent 60%),radial-gradient(900px 500px at -10% 110%,rgba(255,90,0,.07),transparent 60%),var(--bg);min-height:100vh}
body::before{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(135deg,transparent 0 46%,rgba(255,122,24,.06) 46% 46.2%,transparent 46.2%),linear-gradient(315deg,transparent 0 80%,rgba(255,122,24,.10) 80% 80.15%,transparent 80.15%)}
button,input,textarea{font:inherit;color:inherit}
button{cursor:pointer}
a{color:inherit}
.ic{width:20px;height:20px;flex:0 0 auto;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.app{display:grid;grid-template-columns:236px minmax(0,1fr);min-height:100vh;position:relative}
/* ---------- sidebar ---------- */
.side{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:14px;padding:18px 14px 16px;background:linear-gradient(180deg,#0b0b0f,#08080b);border-right:1px solid var(--line2);box-shadow:inset -1px 0 0 rgba(255,122,24,.18)}
.side::after{content:"";position:absolute;right:-1px;top:22%;width:2px;height:120px;background:linear-gradient(var(--or),transparent);box-shadow:0 0 12px var(--or)}
.brand{display:flex;flex-direction:column;align-items:center;text-align:center;gap:2px}
.logo-wrap{width:132px;height:132px;animation:float 6s ease-in-out infinite}
.vx-logo{width:100%;height:100%;display:block}
.wordmark{display:flex;flex-direction:column}
.wm{font:700 26px/1 var(--ui);letter-spacing:.06em}.wm b{color:var(--or);font-weight:700}
.tag{font:500 9.5px/1.4 var(--ui);letter-spacing:.24em;color:#c8c8d0;margin-top:5px}
.menu-btn{display:none}
.side-nav{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.nav-i{display:flex;align-items:center;gap:12px;min-height:46px;padding:0 14px;border-radius:14px;border:1px solid transparent;background:transparent;font:500 17px var(--ui);letter-spacing:.02em;color:#d6d6dd;text-decoration:none;text-align:left;width:100%}
.nav-i .ic{color:#bdbdc6}
.nav-i:hover{border-color:var(--line2);background:#111116}
.nav-i.on{color:#fff;border-color:rgba(255,122,24,.7);background:linear-gradient(90deg,rgba(255,110,10,.30),rgba(255,110,10,.06));box-shadow:0 0 18px rgba(255,100,0,.18),inset 0 0 12px rgba(255,120,30,.12)}
.nav-i.on .ic{color:var(--amb)}
.promo{margin-top:auto;border:1px solid var(--line);border-radius:var(--r);padding:16px 12px 14px;text-align:center;background:radial-gradient(120px 80px at 50% 20%,rgba(255,110,10,.18),transparent 70%),#0c0c10}
.promo svg{width:52px;height:52px}
.promo-t{font:700 19px/1.2 var(--ui);margin:6px 0 2px;color:var(--amb)}.promo-t span{color:#fff}
.promo-s{font:500 11px var(--ui);color:var(--or);margin:0;letter-spacing:.04em}
.profile{display:flex;align-items:center;gap:10px;padding:8px;border:1px solid var(--line2);border-radius:14px;background:#0d0d11;text-align:left;width:100%}
.avatar{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font:700 17px var(--ui);background:linear-gradient(135deg,#2a1608,#ff7a18);color:#fff;box-shadow:0 0 0 2px #1b1b21,0 0 0 3px rgba(255,122,24,.5)}
.profile b{display:block;font:600 16px var(--ui)}.profile small{color:var(--mute);font-size:12px}
.profile .ic{margin-left:auto;color:var(--mute)}
/* ---------- main ---------- */
.main{min-width:0;padding:16px 22px 48px;max-width:1040px;width:100%;margin:0 auto}
.topbar{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.search{position:relative;flex:1;max-width:420px}
.search .ic{position:absolute;left:16px;top:50%;transform:translateY(-50%);color:#d8d8de}
.search input{width:100%;height:46px;border-radius:999px;border:1px solid #2c2c35;background:#0b0b0f;padding:0 16px 0 46px;outline:none}
.search input:focus{border-color:var(--or);box-shadow:0 0 0 3px rgba(255,122,24,.18)}
.results{position:absolute;z-index:30;left:0;right:0;top:52px;background:#101016;border:1px solid var(--line);border-radius:14px;padding:6px;box-shadow:0 18px 40px rgba(0,0,0,.6)}
.results button{display:block;width:100%;text-align:left;background:transparent;border:0;border-radius:10px;padding:9px 10px;min-height:44px}
.results button:hover,.results button:focus{background:#1a1a22;outline:none}
.results small{display:block;color:var(--or);font:600 11px var(--ui);letter-spacing:.12em;text-transform:uppercase}
.spacer{flex:1}
.bell{position:relative;width:46px;height:46px;border-radius:50%;border:1px solid transparent;background:transparent;display:grid;place-items:center}
.bell .ic{width:26px;height:26px}
.badge{position:absolute;top:4px;right:4px;min-width:19px;height:19px;border-radius:99px;background:#e5241b;color:#fff;font:700 11px/19px var(--ui);text-align:center;padding:0 5px;box-shadow:0 0 0 2px var(--bg)}
.tutor{display:flex;align-items:center;gap:8px;height:46px;padding:0 18px;border-radius:999px;border:1px solid rgba(255,122,24,.75);background:rgba(255,110,10,.06);color:var(--amb);font:600 16px var(--ui);letter-spacing:.02em;box-shadow:0 0 16px rgba(255,100,0,.15)}
/* ---------- cards ---------- */
.card{position:relative;background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:var(--r);box-shadow:0 14px 34px rgba(0,0,0,.55),0 0 22px rgba(255,90,0,.06);margin:0 0 18px;overflow:hidden}
.card::after{content:"";position:absolute;top:0;right:28px;width:120px;height:5px;background:linear-gradient(90deg,var(--or2),var(--amb));clip-path:polygon(0 0,100% 0,94% 100%,6% 100%);box-shadow:0 0 14px var(--or)}
.sec{scroll-margin-top:calc(var(--stick) + 74px);padding:18px 20px 20px}
.lab{display:flex;align-items:center;gap:10px;font:700 21px var(--ui);letter-spacing:.08em;color:var(--or);text-transform:uppercase;margin:0}
.lab .ic{width:24px;height:24px}
.ttl{font:600 26px/1.2 var(--ui);margin:4px 0 14px;letter-spacing:.01em}.ttl span{color:#fff;font-weight:700}
/* hero */
.hero{min-height:268px;display:flex;align-items:flex-end;padding:22px 26px 24px}
.hero-art{position:absolute;inset:0;pointer-events:none}
.hero-art svg{position:absolute;right:0;bottom:0;height:100%;width:auto;max-width:72%}
.hero::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,var(--card) 34%,rgba(15,15,20,.75) 58%,rgba(15,15,20,.15));z-index:1}
.hero-in{position:relative;z-index:2;max-width:620px;width:100%}
.chip{display:inline-block;font:600 16px var(--ui);letter-spacing:.03em;padding:5px 14px;border-radius:10px;background:linear-gradient(90deg,#ff6a00,#ff3d00);color:#160700;box-shadow:0 0 18px rgba(255,90,0,.35)}
.hero h1{font:700 clamp(32px,5.4vw,58px)/1.04 var(--tx);margin:16px 0 6px;letter-spacing:-.01em}
.hero h1 .hl{background:linear-gradient(90deg,#ff8a1c,#ff4d00);-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{font:500 clamp(18px,2.2vw,25px) var(--tx);margin:0 0 18px;color:#e9e9ee}.sub .dot{color:var(--or);margin:0 10px}.sub .st{color:var(--amb)}.sub .st.ok{color:var(--ok)}
.prow{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.pbar{flex:1;min-width:160px;max-width:300px;height:12px;border-radius:99px;background:#26262e;overflow:hidden}
.pbar i{display:block;height:100%;width:0;border-radius:99px;background:linear-gradient(90deg,#ff4d00,#ff9a2c);box-shadow:0 0 10px var(--or);transition:width .8s cubic-bezier(.2,.8,.2,1)}
.ptext{font:500 18px var(--ui);color:#e8e8ee}
.pdf{position:absolute;z-index:3;right:20px;bottom:20px;display:flex;align-items:center;gap:8px;height:44px;padding:0 18px;border-radius:999px;border:1px solid rgba(255,140,40,.8);background:rgba(10,10,14,.85);font:600 16px var(--ui);box-shadow:0 0 14px rgba(255,100,0,.2)}
/* tabs */
.tabs{position:sticky;top:var(--stick);z-index:20;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 18px;padding:8px 0;background:linear-gradient(180deg,var(--bg) 70%,rgba(7,7,10,0))}
.tab{display:flex;align-items:center;justify-content:center;gap:10px;height:52px;border-radius:14px;border:1px solid #23232b;background:#0e0e13;font:500 19px var(--ui);color:#e3e3ea;letter-spacing:.02em;transition:background .25s,border-color .25s,box-shadow .25s}
.tab .ic{width:22px;height:22px}
.tab[aria-selected=true]{background:linear-gradient(180deg,#ff7a18,#ff5200);border-color:#ff8a2c;color:#fff;font-weight:700;box-shadow:0 0 22px rgba(255,90,0,.45)}
/* picture */
.pic-grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:18px;align-items:start}
.frame{position:relative;border-radius:14px;background:#fff;border:1px solid #2b2b33;padding:8px;cursor:zoom-in;min-height:160px}
.frame svg{display:block;width:100%;height:auto;max-height:62vh}
.frame .hint{position:absolute;right:10px;bottom:8px;font:600 12px var(--ui);color:#5b5b66;background:rgba(255,255,255,.85);padding:2px 8px;border-radius:99px}
.cap{color:var(--mute);font-size:.93rem;margin:10px 2px 0}
.box{border:1px solid var(--line);border-radius:16px;padding:16px 16px 12px;background:rgba(10,10,14,.7)}
.box h3{font:700 21px var(--ui);color:var(--or);margin:0 0 10px;display:flex;align-items:center;gap:8px}
.ticks{list-style:none;margin:0;padding:0}
.ticks li{display:flex;gap:10px;align-items:flex-start;margin:0 0 11px;font:500 17px/1.3 var(--ui);color:#ececf1}
.ticks small{display:block;font:400 14px/1.35 var(--tx);color:var(--mute);margin-top:2px}
.tick{flex:0 0 22px;height:22px;border-radius:50%;background:linear-gradient(135deg,#ff8a1c,#ff4d00);display:grid;place-items:center;box-shadow:0 0 8px rgba(255,90,0,.5);margin-top:1px}
.tick svg{width:13px;height:13px;fill:none;stroke:#fff;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}
.empty{color:var(--mute)}
/* notes */
.notes-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:18px;align-items:start}
.summary{font-size:1.06rem;color:#e6e6ec;margin:0 0 14px}
.nsec{border-top:1px solid var(--line2);padding:14px 0 4px}
.nsec:first-of-type{border-top:0;padding-top:0}
.nsec h3{font:700 24px/1.2 var(--tx);margin:0 0 8px}.nsec h3 .n{color:var(--or);margin-right:6px}
.nsec ul{margin:0;padding-left:20px;color:#dcdce3}.nsec li{margin:5px 0}
.side-col{display:flex;flex-direction:column;gap:14px}
.fx{margin:0 0 12px}.fx strong{font:600 17px var(--ui)}
.fx code{display:block;font:15px ui-monospace,Consolas,Menlo,monospace;color:var(--amb);background:#09090c;border:1px solid var(--line2);border-radius:10px;padding:8px 10px;margin:4px 0;overflow-x:auto}
.fx div{color:var(--mute);font-size:.92rem}
.xp h3{font:700 22px var(--ui);color:var(--or);margin:20px 0 10px;letter-spacing:.04em}
details.xd{border:1px solid var(--line2);border-radius:14px;background:#0c0c11;margin:0 0 10px}
details.xd summary{list-style:none;cursor:pointer;min-height:50px;display:flex;align-items:center;gap:10px;padding:0 16px;font:600 18px var(--ui)}
details.xd summary::-webkit-details-marker{display:none}
details.xd summary::before{content:"+";color:var(--or);font:700 22px var(--ui);width:16px}
details.xd[open] summary::before{content:"\2212"}
.xd .xb{padding:0 16px 14px}
.flash{animation:flash 1.6s ease-out}
/* practice + progress */
.duo{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}
.duo .card{margin:0}
.qmeta{color:var(--mute);font:500 15px var(--ui);letter-spacing:.04em;margin:2px 0 4px}
.qtext{font:600 21px/1.35 var(--tx);margin:6px 0 14px;padding-right:86px}
.target{position:absolute;right:16px;top:58px;width:84px;height:84px;opacity:.95}
.opts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 14px}
.opt{display:flex;align-items:center;gap:12px;min-height:48px;padding:8px 14px;border-radius:999px;border:1px solid #2a2a33;background:#101016;text-align:left;font:500 17px/1.25 var(--ui);color:#ededf2;transition:border-color .2s,box-shadow .2s}
.opt .rd{flex:0 0 20px;height:20px;border-radius:50%;border:2px solid #8e8e9a;display:grid;place-items:center}
.opt.multi .rd{border-radius:6px}
.opt.sel{border-color:var(--or);box-shadow:0 0 14px rgba(255,90,0,.35),inset 0 0 10px rgba(255,100,0,.12)}
.opt.sel .rd{border-color:var(--or)}.opt.sel .rd::after{content:"";width:10px;height:10px;border-radius:50%;background:var(--or);box-shadow:0 0 8px var(--or)}
.opt.multi.sel .rd::after{border-radius:3px}
.opt.right{border-color:var(--ok);box-shadow:0 0 12px rgba(47,210,107,.3)}.opt.right .rd{border-color:var(--ok)}
.opt.wrong{border-color:var(--bad);box-shadow:0 0 12px rgba(255,90,79,.3)}.opt.wrong .rd{border-color:var(--bad)}
.opt:disabled{cursor:default}
.opt.wide{grid-column:1/-1}
.go{display:flex;align-items:center;justify-content:center;gap:10px;margin:0 auto;min-width:220px;height:50px;padding:0 28px;border-radius:999px;border:0;background:linear-gradient(90deg,#ff7a18,#ff4d00);color:#1a0800;font:700 19px var(--ui);letter-spacing:.02em;box-shadow:0 0 22px rgba(255,90,0,.45)}
.go:disabled{opacity:.45;box-shadow:none}
.go .ic{width:18px;height:18px;stroke-width:2.6}
.ghost{min-height:44px;padding:0 16px;border-radius:999px;border:1px solid #30303a;background:#101016;font:600 16px var(--ui);color:#e6e6ec}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0 0}
.nav2{display:flex;justify-content:space-between;gap:10px;margin-top:16px;border-top:1px solid var(--line2);padding-top:14px}
textarea,input.ans{width:100%;min-height:48px;padding:10px 14px;border-radius:14px;border:1px solid #2c2c35;background:#0b0b0f;margin:0 0 12px}
.res{font:700 19px var(--ui);margin:14px 0 6px}.res.good{color:var(--ok)}.res.bad{color:var(--bad)}
.why{border:1px solid var(--line2);border-radius:14px;background:#0b0b10;padding:12px 14px;margin:8px 0}
.why strong{font:700 15px var(--ui);color:var(--or);letter-spacing:.06em;text-transform:uppercase}.why p{margin:4px 0 0}
.xcard{border:1px solid var(--line);background:radial-gradient(400px 140px at 0 0,rgba(255,110,10,.10),transparent),#0c0c11}
.xcard p{margin:6px 0}.xcard>strong{text-transform:none;font-size:18px;letter-spacing:.02em}
.prog{display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:center}
.ring{position:relative;width:132px;height:132px}
.ring svg{width:100%;height:100%;transform:rotate(-90deg)}
.ring .tr{fill:none;stroke:#2a2a31;stroke-width:11}
.ring .val{fill:none;stroke:url(#ringGrad);stroke-width:11;stroke-linecap:round;transition:stroke-dashoffset .9s cubic-bezier(.2,.8,.2,1)}
.ring b{position:absolute;inset:0;display:grid;place-items:center;font:700 36px var(--tx)}
.ring small{position:absolute;left:0;right:0;bottom:30px;text-align:center;color:var(--mute);font:500 12px var(--ui);letter-spacing:.1em}
.path{list-style:none;margin:0;padding:0}
.path li{display:flex;align-items:center;gap:10px;margin:0 0 10px;font:500 17px/1.25 var(--ui)}
.path li small{color:var(--mute);font:400 13px var(--tx);margin-left:auto;white-space:nowrap}
.st-d{flex:0 0 20px;height:20px;border-radius:50%;border:3px solid #6b6b77}
.st-d.learning{border-color:var(--or);box-shadow:0 0 8px rgba(255,90,0,.6);background:radial-gradient(circle,var(--or) 0 3px,transparent 4px)}
.st-d.mastered{border:0;background:var(--ok);display:grid;place-items:center}
.st-d.mastered svg{width:12px;height:12px;fill:none;stroke:#04170a;stroke-width:3.2;stroke-linecap:round;stroke-linejoin:round}
.keep{position:relative;display:flex;align-items:center;gap:14px;margin-top:16px;border:1px solid var(--line);border-radius:16px;padding:12px 16px;background:linear-gradient(90deg,rgba(255,110,10,.10),rgba(255,110,10,.02));overflow:hidden}
.keep svg.tr2{width:40px;height:40px}
.keep b{display:block;font:700 23px var(--ui);color:var(--amb)}.keep span{color:#dedee5;font-size:.95rem}
.keep .up{position:absolute;right:10px;top:6px;width:110px;height:56px;opacity:.9}
.weak{margin:14px 0 0}.weak h4{font:700 16px var(--ui);color:var(--or);letter-spacing:.08em;text-transform:uppercase;margin:0 0 6px}
.weak ul{margin:0;padding-left:18px;color:#dcdce3}
details.pf{margin-top:14px;border-top:1px solid var(--line2);padding-top:10px}
details.pf summary{cursor:pointer;font:600 16px var(--ui);color:#d0d0d8;min-height:40px;display:flex;align-items:center}
.msg{color:var(--mute);font-size:.9rem;min-height:1.2em}
/* sheets */
.veil{position:fixed;inset:0;z-index:60;background:rgba(0,0,0,.66);display:flex;align-items:center;justify-content:center;padding:16px}
.veil[hidden]{display:none}
.sheet{width:100%;max-width:460px;max-height:86vh;overflow:auto;background:#0f0f14;border:1px solid var(--line);border-radius:20px;padding:20px;box-shadow:0 30px 80px rgba(0,0,0,.7)}
.sheet h2{font:700 24px var(--ui);color:var(--or);margin:0 0 12px;letter-spacing:.04em}
.sheet p,.sheet li{color:#dcdce3}
.sheet label{display:block;font:600 15px var(--ui);color:#cfcfd8;margin:14px 0 6px}
.sheet input[type=text]{width:100%;height:46px;border-radius:12px;border:1px solid #2c2c35;background:#0b0b0f;padding:0 12px}
.switch{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0}
.switch input{position:absolute;opacity:0;width:1px;height:1px}
.switch .sl{display:inline-block;vertical-align:middle;position:relative;width:56px;height:32px;border-radius:99px;background:#33333c;transition:background .3s;flex:0 0 auto}
.switch .sl::after{content:"";position:absolute;top:4px;left:4px;width:24px;height:24px;border-radius:50%;background:#fff;transition:transform .3s}
.switch input:checked+.sl{background:var(--or)}.switch input:checked+.sl::after{transform:translateX(24px)}
.switch input:focus-visible+.sl{outline:2px solid var(--amb);outline-offset:2px}
.zoomv{background:rgba(0,0,0,.9);padding:10px}
.zoomv .zbox{width:100%;max-width:1100px;max-height:94vh;overflow:auto;background:#fff;border-radius:14px;padding:8px}
.zoomv .zbox svg{width:100%;min-width:min(760px,180vw);height:auto;display:block}
.foot{color:#6f6f7b;font-size:.82rem;text-align:center;margin:22px 0 0}
.print-only{display:none}
:focus-visible{outline:2px solid var(--amb);outline-offset:2px}
.rv{opacity:0;transform:translateY(16px)}
.rv.in{opacity:1;transform:none;transition:opacity .55s ease,transform .55s cubic-bezier(.2,.8,.2,1)}
.crane-hook{transform-box:view-box;transform-origin:452px 58px;animation:swing 5.5s ease-in-out infinite alternate}
.win{animation:blink 4s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}
@keyframes swing{from{transform:rotate(-2.2deg)}to{transform:rotate(2.2deg)}}
@keyframes blink{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes flash{0%{box-shadow:0 0 0 2px var(--or),0 0 24px rgba(255,90,0,.6)}100%{box-shadow:0 0 0 0 transparent}}
.still .logo-wrap,.still .crane-hook,.still .win{animation:none}
.still .rv{opacity:1;transform:none}
/* ---------- tablet / phone ---------- */
@media (max-width:1023px){
 :root{--stick:64px}
 .app{display:block}
 .side{position:sticky;top:0;z-index:40;height:auto;flex-direction:row;align-items:center;gap:10px;padding:8px 14px;border-right:0;border-bottom:1px solid var(--line2);box-shadow:0 1px 0 rgba(255,122,24,.2)}
 .side::after{display:none}
 .brand{flex-direction:row;gap:10px;text-align:left;flex:1}
 .logo-wrap{width:52px;height:52px}
 .wm{font-size:21px}.tag{font-size:7.5px;letter-spacing:.2em;margin-top:3px}
 .menu-btn{display:grid;place-items:center;width:46px;height:46px;border-radius:12px;border:1px solid var(--line2);background:#0e0e13;margin-left:auto}
 .side-nav,.promo,.profile{display:none}
 .side.open{flex-wrap:wrap}
 .side.open .side-nav{display:flex;width:100%;margin:4px 0 2px}
 .side.open .profile{display:flex}
 .main{padding:12px 14px 40px}
 .pic-grid,.notes-grid,.duo{grid-template-columns:1fr}
 .duo{gap:18px}
}
@media (max-width:640px){
 .topbar{gap:8px}
 .spacer{display:none}
 .search{max-width:none;min-width:0}
 .tutor{padding:0 12px}.tutor span{display:none}
 .hero{min-height:300px;padding:18px 18px 76px}
 .hero::before{background:linear-gradient(180deg,rgba(15,15,20,.45),var(--card) 62%)}
 .hero-art svg{max-width:100%;height:62%;top:0;bottom:auto}
 .pdf{left:18px;right:auto;bottom:18px}
 .tabs{gap:6px}
 .tab{flex-direction:column;gap:2px;height:58px;font-size:15px}
 .tab .ic{width:20px;height:20px}
 .sec{padding:16px 15px 18px}
 .card::after{right:16px;width:84px}
 .opts{grid-template-columns:1fr}
 .qtext{padding-right:0;font-size:19px}
 .target{display:none}
 .prog{grid-template-columns:1fr;justify-items:center}
 .prog .path{width:100%}
 .nsec h3{font-size:21px}
 .keep .up{display:none}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}.rv{opacity:1;transform:none}}
@media print{
 body{background:#fff;color:#000}body::before{display:none}
 .app,.veil{display:none!important}
 .print-only{display:block;font:12pt/1.45 var(--tx);color:#000}
 .print-only h1{font:700 22pt var(--tx);margin:0 0 2pt}.print-only h2{font:700 15pt var(--ui);margin:14pt 0 4pt;border-bottom:1px solid #999}
 .print-only .pp svg{max-width:100%;height:auto;max-height:9cm}
 .print-only li{margin:2pt 0}
}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#ff4d00"/></linearGradient></defs></svg>
<div class="app" id="app">
<aside class="side" id="side">
 <div class="brand">
  <div class="logo-wrap">__LOGO__</div>
  <div class="wordmark"><span class="wm">VEX <b>CIPHER</b></span><span class="tag">YOUR PRIVATE WORLD. PROTECTED.</span></div>
  <button class="menu-btn" id="menuBtn" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="sideNav"><svg class="ic" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
 </div>
 <nav class="side-nav" id="sideNav" aria-label="Board menu">
  <a class="nav-i" href="#top" data-go="top"><svg class="ic" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>Home</a>
  <a class="nav-i" href="/" id="courses" hidden><svg class="ic" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h6"/></svg>My Courses</a>
  <a class="nav-i on" href="#s-notes" data-go="s-notes"><svg class="ic" viewBox="0 0 24 24"><path d="M4 4h16v16H4zM4 15l5-5 4 4 3-3 4 4"/><circle cx="15.5" cy="8.5" r="1.5"/></svg>Study Board</a>
  <a class="nav-i" href="#s-progress" data-go="s-progress"><svg class="ic" viewBox="0 0 24 24"><path d="M5 20V12M10 20V5M15 20v-6M20 20V9"/></svg>Progress</a>
  <button class="nav-i" type="button" data-sheet="settings"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></svg>Settings</button>
  <button class="nav-i" type="button" data-sheet="help"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17.5v.01"/></svg>Help &amp; Support</button>
 </nav>
 <div class="promo" aria-hidden="true">
  <svg viewBox="0 0 64 64"><defs><linearGradient id="shg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#ff4d00"/></linearGradient></defs><ellipse cx="32" cy="56" rx="20" ry="4" fill="#ff6a00" opacity=".35"/><path d="M32 5l21 8v15c0 13-9 23-21 28C20 51 11 41 11 28V13z" fill="#1a0f08" stroke="url(#shg)" stroke-width="3"/><rect x="23" y="28" width="18" height="14" rx="3" fill="url(#shg)"/><path d="M26 28v-4a6 6 0 0 1 12 0v4" fill="none" stroke="url(#shg)" stroke-width="3"/><circle cx="32" cy="35" r="2.2" fill="#1a0f08"/></svg>
  <p class="promo-t">Secure. Study. <span>Excel.</span></p><p class="promo-s">Powered by VEX</p>
 </div>
 <button class="profile" type="button" data-sheet="settings"><span class="avatar" id="avatar">S</span><span><b id="pname">Student</b><small id="plevel">Student</small></span><svg class="ic" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>
</aside>

<div class="main" id="top">
 <div class="topbar">
  <div class="search"><svg class="ic" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input id="q" type="search" placeholder="Search topics..." aria-label="Search this board" autocomplete="off"><div class="results" id="results" hidden></div></div>
  <span class="spacer"></span>
  <button class="bell" id="bell" type="button" aria-label="Notes from the builder"><svg class="ic" viewBox="0 0 24 24"><path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0"/></svg><span class="badge" id="badge" hidden></span></button>
  <button class="tutor" id="explainBtn" type="button"><svg class="ic" viewBox="0 0 24 24"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 3v4M17 5h4"/></svg><span>Explain it to me</span></button>
 </div>

 <section class="card hero" aria-labelledby="title">
  <div class="hero-art" aria-hidden="true">
   <svg viewBox="0 0 640 320" preserveAspectRatio="xMaxYMax meet">
    <defs><linearGradient id="hz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff7a18" stop-opacity=".0"/><stop offset="1" stop-color="#ff5a00" stop-opacity=".28"/></linearGradient></defs>
    <rect x="0" y="0" width="640" height="320" fill="url(#hz)"/>
    <g stroke="#3a3a44" stroke-width="2" fill="none" opacity=".7"><path d="M40 320V150M40 150h70M52 150v-26M60 150l40 0"/><path d="M110 320V190M98 190h60"/></g>
    <g fill="none" stroke="#5c5c68" stroke-width="2.2">
     <path d="M360 320V120M412 320V120M464 320V120M516 320V120M568 320V120M620 320V120"/>
     <path d="M350 120h280M350 160h280M350 200h280M350 240h280M350 280h280"/>
    </g>
    <g fill="#ff8a1c"><rect class="win" x="372" y="170" width="28" height="20" opacity=".6"/><rect class="win" x="476" y="210" width="28" height="20" opacity=".5" style="animation-delay:1.3s"/><rect class="win" x="528" y="130" width="28" height="20" opacity=".45" style="animation-delay:2.4s"/><rect class="win" x="580" y="250" width="28" height="20" opacity=".5" style="animation-delay:.7s"/></g>
    <g fill="none" stroke="#ff7a18" stroke-width="3" stroke-linejoin="round">
     <path d="M262 320V48M282 320V48"/><path d="M262 300l20-24-20-24 20-24-20-24 20-24-20-24 20-24-20-24 20-24-20-24 20-24"/>
     <path d="M150 48h440M150 66h440"/><path d="M150 66l18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18 18-18 18 18"/>
     <path d="M272 48L272 16M272 16L180 48M272 16L560 48"/>
    </g>
    <rect x="152" y="66" width="34" height="26" fill="#2a1a10" stroke="#ff7a18" stroke-width="2"/>
    <rect x="284" y="66" width="22" height="18" fill="#1a1a20" stroke="#ff9a2c" stroke-width="2"/>
    <g class="crane-hook"><path d="M452 66V170" stroke="#d8d8e0" stroke-width="2"/><rect x="440" y="58" width="24" height="10" fill="#ff9a2c"/><path d="M446 170h12l-2 10h-8z" fill="#ff9a2c"/><rect x="396" y="184" width="112" height="14" fill="#3b3b46" stroke="#ff7a18" stroke-width="2"/><path d="M452 180l-50 4M452 180l50 4" stroke="#bbb" stroke-width="1.5"/></g>
    <path d="M0 318h640" stroke="#ff7a18" stroke-width="2" opacity=".6"/>
   </svg>
  </div>
  <div class="hero-in">
   <span class="chip" id="chip"></span>
   <h1 id="title"></h1>
   <p class="sub" id="sub"></p>
   <div class="prow"><div class="pbar" role="progressbar" aria-label="Questions answered" aria-valuemin="0" aria-valuemax="100" id="pbar"><i id="pfill"></i></div><span class="ptext" id="ptext"></span></div>
  </div>
  <button class="pdf" id="pdfBtn" type="button"><svg class="ic" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h6"/></svg>Save PDF</button>
 </section>

 <div class="tabs" role="tablist" aria-label="Board sections">
  <button class="tab" role="tab" type="button" data-t="s-picture" aria-selected="true"><svg class="ic" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="15.5" cy="8.5" r="1.5"/></svg>Picture</button>
  <button class="tab" role="tab" type="button" data-t="s-notes" aria-selected="false"><svg class="ic" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h6"/></svg>Notes</button>
  <button class="tab" role="tab" type="button" data-t="s-practice" aria-selected="false"><svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>Practice</button>
  <button class="tab" role="tab" type="button" data-t="s-progress" aria-selected="false"><svg class="ic" viewBox="0 0 24 24"><path d="M5 20V12M10 20V5M15 20v-6M20 20V9"/></svg>Progress</button>
 </div>

 <section class="card sec" id="s-picture" aria-labelledby="picLab">
  <p class="lab" id="picLab"><svg class="ic" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="15.5" cy="8.5" r="1.5"/></svg>Picture</p>
  <h2 class="ttl" id="picTitle"></h2>
  <div class="pic-grid"><div><div class="frame" id="frame" role="button" tabindex="0" aria-label="Open the picture full screen"></div><p class="cap" id="cap"></p></div><div class="box"><h3 id="partsHead">Key parts</h3><ul class="ticks" id="parts"></ul></div></div>
 </section>

 <section class="card sec" id="s-notes" aria-labelledby="notesLab">
  <p class="lab" id="notesLab"><svg class="ic" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h6"/></svg>Notes</p>
  <div class="notes-grid"><div id="notesMain"></div><div class="side-col" id="notesSide"></div></div>
  <div class="xp" id="explainers"></div>
 </section>

 <div class="duo">
  <section class="card sec" id="s-practice" aria-labelledby="pracLab"></section>
  <section class="card sec" id="s-progress" aria-labelledby="progLab"></section>
 </div>
 <p class="foot">Made on your laptop with DeepTutor. Works offline. Your answers stay in this browser.</p>
</div>
</div>

<div class="veil" id="v-settings" hidden><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="setH"><h2 id="setH">Settings</h2>
 <label for="nameIn">Your name</label><input type="text" id="nameIn" maxlength="40" placeholder="Student">
 <div class="switch"><span>Animations</span><label style="margin:0"><input type="checkbox" id="motionIn"><span class="sl" aria-hidden="true"></span><span class="sr" style="position:absolute;left:-9999px">Animations</span></label></div>
 <p class="msg">Turn animations off to save battery on older phones.</p>
 <div class="row"><button class="go" type="button" data-close>Done</button></div></div></div>
<div class="veil" id="v-help" hidden><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="helpH"><h2 id="helpH">Help &amp; Support</h2>
 <ul><li>Tap <b>Picture</b>, <b>Notes</b>, <b>Practice</b> or <b>Progress</b> to jump to that part of this board.</li><li>Tap the picture to see it full screen.</li><li>In Practice, pick an answer and press <b>Submit Answer</b>. A wrong answer opens a plain explanation and a new check question.</li><li>Use the search box to find a word in the notes or questions.</li><li><b>Save PDF</b> opens print. Choose <b>Save as PDF</b>.</li><li>This board works with no internet. Your answers stay in this browser. Use <b>Your progress file</b> in Progress to move them to another phone.</li><li>A <b>Draft</b> board has not been checked yet. Check it against your guideline.</li></ul>
 <div class="row"><button class="go" type="button" data-close>Got it</button></div></div></div>
<div class="veil" id="v-notes" hidden><div class="sheet" role="dialog" aria-modal="true" aria-labelledby="bnH"><h2 id="bnH">Notes from the builder</h2><div id="bnList"></div>
 <div class="row"><button class="go" type="button" data-close>Close</button></div></div></div>
<div class="veil zoomv" id="v-zoom" hidden><div class="zbox" id="zbox" role="dialog" aria-modal="true" aria-label="Picture, full screen"></div></div>
<div class="print-only" id="printOut"></div>

<div id="picture-svg" hidden>__SVG__</div>
<script type="application/json" id="board-data">__BOARD_JSON__</script>
<script>
(function(){
"use strict";
var B=JSON.parse(document.getElementById("board-data").textContent);
var KEY="dtboard:"+B.board_id+":"+B.generated_at, PKEY="vexboard:prefs";
var mem={}, store=null;
try{localStorage.setItem("__t","1");localStorage.removeItem("__t");store=localStorage;}catch(e){store=null;}
function load(){try{var r=store&&store.getItem(KEY);return r?JSON.parse(r):{}}catch(e){return mem}}
var answers=load();
function save(){mem=answers;try{if(store)store.setItem(KEY,JSON.stringify(answers))}catch(e){}}
var prefs={};try{prefs=JSON.parse((store&&store.getItem(PKEY))||"{}")||{}}catch(e){prefs={}}
function savePrefs(){try{if(store)store.setItem(PKEY,JSON.stringify(prefs))}catch(e){}}
function $(i){return document.getElementById(i)}
function el(tag,attrs,kids){var n=document.createElement(tag);if(attrs)for(var k in attrs){if(k==="text")n.textContent=attrs[k];else if(k==="class")n.className=attrs[k];else n.setAttribute(k,attrs[k]);}(kids||[]).forEach(function(c){n.appendChild(typeof c==="string"?document.createTextNode(c):c)});return n}
function clear(n){while(n.firstChild)n.removeChild(n.firstChild)}
function short(t,n){t=String(t||"");return t.length>n?t.slice(0,n-1).replace(/\s+\S*$/,"")+"…":t}
var NS="http://www.w3.org/2000/svg";
function svgIcon(d,cls){var s=document.createElementNS(NS,"svg");s.setAttribute("viewBox","0 0 24 24");s.setAttribute("class",cls||"ic");s.setAttribute("aria-hidden","true");d.split("|").forEach(function(p){var e=document.createElementNS(NS,"path");e.setAttribute("d",p);s.appendChild(e)});return s}
function tick(){var t=el("span",{class:"tick"});t.appendChild(svgIcon("M5 12l4 4 10-10",""));return t}
var reduce=!!(window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches);
function motionOn(){return !reduce&&prefs.motion!==false}

/* ---- motion: the V keeps moving; it pauses when the page is hidden or motion is off ---- */
var logo=document.querySelector(".vx-logo");
function applyMotion(){
 var on=motionOn();document.documentElement.classList.toggle("still",!on);
 if(!logo||!logo.pauseAnimations)return;
 try{if(on&&!document.hidden){logo.unpauseAnimations()}else{if(logo.getCurrentTime()<3)logo.setCurrentTime(3);logo.pauseAnimations()}}catch(e){}
}
document.addEventListener("visibilitychange",applyMotion);
applyMotion();

/* ---- header ---- */
var reviewed=B.review&&B.review.status==="reviewed";
$("chip").textContent=[B.level,B.subject].filter(Boolean).join(" • ")||"Learning board";
(function(){var h=$("title"),w=String(B.topic||"").trim().split(/\s+/);var last=w.pop()||"";if(w.length){h.appendChild(document.createTextNode(w.join(" ")+" "))}h.appendChild(el("span",{class:"hl",text:last}))})();
(function(){var s=$("sub");s.appendChild(document.createTextNode(B.programme||B.subject||""));s.appendChild(el("span",{class:"dot",text:"•"}));s.appendChild(el("span",{class:"st"+(reviewed?" ok":""),text:reviewed?"Approved":"Draft"}))})();
$("plevel").textContent=B.level?B.level+" student":"Student";
function setName(){var n=String(prefs.name||"").trim();$("pname").textContent=n||"Student";$("avatar").textContent=(n||"S").split(/\s+/).map(function(x){return x.charAt(0)}).join("").slice(0,2).toUpperCase()}
setName();
if(/^https?:$/.test(location.protocol))$("courses").hidden=false;

/* ---- builder notes (bell) ---- */
var notes=(B.warnings||[]).slice();
if(!reviewed)notes.unshift("This board is a draft. Nobody has checked it yet. Check every note and answer against your guideline.");
if(notes.length){$("badge").hidden=false;$("badge").textContent=String(notes.length)}
(function(){var l=$("bnList");var u=el("ul");notes.forEach(function(w){u.appendChild(el("li",{text:w}))});l.appendChild(notes.length?u:el("p",{text:"Nothing to report."}))})();

/* ---- sheets ---- */
var lastFocus=null;
function openSheet(name){var v=$("v-"+name);if(!v)return;lastFocus=document.activeElement;v.hidden=false;var f=v.querySelector("input,button");if(f)f.focus()}
function closeSheets(){[].forEach.call(document.querySelectorAll(".veil"),function(v){v.hidden=true});if(lastFocus&&lastFocus.focus)lastFocus.focus()}
[].forEach.call(document.querySelectorAll("[data-sheet]"),function(b){b.addEventListener("click",function(){closeMenu();openSheet(b.getAttribute("data-sheet"))})});
[].forEach.call(document.querySelectorAll(".veil"),function(v){v.addEventListener("click",function(e){if(e.target===v||e.target.hasAttribute("data-close"))closeSheets()})});
document.addEventListener("keydown",function(e){if(e.key==="Escape"){closeSheets();hideResults()}});
$("bell").addEventListener("click",function(){openSheet("notes")});
$("nameIn").value=prefs.name||"";$("motionIn").checked=prefs.motion!==false;
$("nameIn").addEventListener("input",function(){prefs.name=$("nameIn").value.slice(0,40);savePrefs();setName()});
$("motionIn").addEventListener("change",function(){prefs.motion=$("motionIn").checked;savePrefs();applyMotion()});

/* ---- menu (phone) ---- */
var side=$("side");
function closeMenu(){side.classList.remove("open");$("menuBtn").setAttribute("aria-expanded","false")}
$("menuBtn").addEventListener("click",function(){var o=side.classList.toggle("open");$("menuBtn").setAttribute("aria-expanded",String(o))});

/* ---- scrolling ---- */
function go(id,flashEl){var t=id==="top"?$("top"):$(id);if(!t)return;t.scrollIntoView({behavior:motionOn()?"smooth":"auto",block:"start"});if(flashEl){flashEl.classList.remove("flash");void flashEl.offsetWidth;flashEl.classList.add("flash")}}
[].forEach.call(document.querySelectorAll("[data-go]"),function(a){a.addEventListener("click",function(e){e.preventDefault();closeMenu();go(a.getAttribute("data-go"))})});
var tabs=[].slice.call(document.querySelectorAll(".tab"));
tabs.forEach(function(t){t.addEventListener("click",function(){go(t.getAttribute("data-t"));setTab(t.getAttribute("data-t"))})});
function setTab(id){tabs.forEach(function(t){t.setAttribute("aria-selected",String(t.getAttribute("data-t")===id))})}
if("IntersectionObserver" in window){
 var spy=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting)setTab(e.target.id)})},{rootMargin:"-35% 0px -60% 0px"});
 tabs.forEach(function(t){var s=$(t.getAttribute("data-t"));if(s)spy.observe(s)});
 if(motionOn()){var rv=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");rv.unobserve(e.target)}})},{rootMargin:"0px 0px -8% 0px"});
  [].forEach.call(document.querySelectorAll(".sec"),function(c){c.classList.add("rv");rv.observe(c)})}
}

/* ---- picture ---- */
(function(){var holder=$("picture-svg"),svg=holder.querySelector("svg"),frame=$("frame");
 $("picTitle").textContent=(B.picture&&B.picture.title)||"Diagram";
 $("cap").textContent=(B.picture&&B.picture.caption)||"";
 if(!svg){frame.removeAttribute("role");frame.removeAttribute("tabindex");frame.style.cursor="default";frame.style.background="#0c0c11";frame.appendChild(el("p",{class:"empty",text:"No picture for this topic. Read the notes instead."}));}
 else{svg.setAttribute("role","img");svg.setAttribute("aria-label",(B.picture&&(B.picture.alt||B.picture.title))||"Diagram");frame.appendChild(svg);frame.appendChild(el("span",{class:"hint",text:"Tap to enlarge"}));
  function zoom(){var z=$("zbox");clear(z);z.appendChild(svg.cloneNode(true));openSheet("zoom")}
  frame.addEventListener("click",zoom);frame.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();zoom()}});$("zbox").addEventListener("click",closeSheets)}
 holder.remove();
 var kt=(B.notes&&B.notes.key_terms)||[],ul=$("parts"),items=[],seen={};
 function meaning(label){var l=label.toLowerCase();for(var i=0;i<kt.length;i++){var t=kt[i].term.toLowerCase();if(l===t||l.indexOf(t)>-1||t.indexOf(l)>-1)return kt[i].meaning}return ""}
 if(svg){[].forEach.call(svg.querySelectorAll("text"),function(n){var t=(n.textContent||"").replace(/\s+/g," ").trim();var k=t.toLowerCase();
  if(t.length<3||t.length>32||/^[\d.,\s]+[a-z\u00b0%]{0,3}$/i.test(t)||seen[k])return;seen[k]=1;items.push({term:t,meaning:meaning(t)})})}
 if(items.length>=2){$("partsHead").textContent="In this picture";items=items.slice(0,6)}
 else items=kt.slice(0,5);
 if(!items.length){ul.appendChild(el("li",{class:"empty",text:"No key parts listed."}))}
 items.forEach(function(t){var li=el("li");li.appendChild(tick());var sp=el("span",{},[t.term]);if(t.meaning)sp.appendChild(el("small",{text:short(t.meaning,70)}));li.appendChild(sp);ul.appendChild(li)});
})();

/* ---- notes ---- */
var nb=B.notes||{};
(function(){var m=$("notesMain"),s=$("notesSide");
 if(nb.summary)m.appendChild(el("p",{class:"summary",text:nb.summary}));
 (nb.sections||[]).forEach(function(sec,i){var d=el("div",{class:"nsec",id:"ns-"+i});d.appendChild(el("h3",{},[el("span",{class:"n",text:(i+1)+"."}),sec.heading]));var u=el("ul");(sec.points||[]).forEach(function(p){u.appendChild(el("li",{text:p}))});d.appendChild(u);m.appendChild(d)});
 if(!m.firstChild)m.appendChild(el("p",{class:"empty",text:"No notes for this topic."}));
 var kt=nb.key_terms||[];
 if(kt.length){var b=el("div",{class:"box"});var h=el("h3");h.appendChild(svgIcon("M9 18h6|M10 21h4|M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"));h.appendChild(document.createTextNode("Key Concepts"));b.appendChild(h);var u=el("ul",{class:"ticks"});
  kt.forEach(function(t,i){var li=el("li",{id:"kt-"+i});li.appendChild(tick());li.appendChild(el("span",{},[t.term,el("small",{text:t.meaning})]));u.appendChild(li)});b.appendChild(u);s.appendChild(b)}
 var fx=nb.formulas||[];
 if(fx.length){var f=el("div",{class:"box"});f.appendChild(el("h3",{text:"Formulas"}));fx.forEach(function(x,i){var c=el("div",{class:"fx",id:"fx-"+i},[el("strong",{text:x.name}),el("code",{text:x.latex})]);if(x.explanation)c.appendChild(el("div",{text:x.explanation}));f.appendChild(c)});s.appendChild(f)}
 var ex=B.explainers||[],box=$("explainers");
 if(ex.length){box.appendChild(el("h3",{text:"Explain it to me"}));ex.forEach(function(e,i){var d=el("details",{class:"xd",id:"xd-"+i});d.appendChild(el("summary",{text:e.title}));var inner=el("div",{class:"xb"});d.appendChild(inner);var done=false;d.addEventListener("toggle",function(){if(d.open&&!done){done=true;renderExplainer(inner,e)}});box.appendChild(d)})}
})();
$("explainBtn").addEventListener("click",function(){var d=document.querySelector("details.xd");if(d){d.open=true;go("explainers",d)}else go("s-notes")});

/* ---- explainers: plain words, a site example, then a fresh question ---- */
var EX={};(B.explainers||[]).forEach(function(e){EX[e.kp_id]=e});
function keys(a){return String(a).split(/[,\s]+/).filter(Boolean).map(function(x){return x.toUpperCase()}).sort()}
function same(a,b){return a.length===b.length&&a.every(function(v,i){return v===b[i]})}
function renderExplainer(box,e){
 clear(box);
 var c=el("div",{class:"why xcard"});c.appendChild(el("strong",{text:"Let me explain: "+e.title}));
 String(e.explanation).split(/\n+/).forEach(function(t){if(t.trim())c.appendChild(el("p",{text:t}))});
 if(e.example)c.appendChild(el("p",{},[el("b",{text:"On site: "}),e.example]));
 if(e.mistake)c.appendChild(el("p",{},[el("b",{text:"Common mistake: "}),e.mistake]));
 box.appendChild(c);
 var q=e.check,key="e-"+e.kp_id,a=answers[key],tf=q.type==="true_false";
 var right=tf?[String(q.answer).toLowerCase()]:keys(q.answer);
 box.appendChild(el("p",{class:"qmeta",text:"Check yourself with a new question"}));
 box.appendChild(el("p",{class:"qtext",style:"padding-right:0",text:q.question}));
 var grid=el("div",{class:"opts"});
 var choices=tf?[["true","True"],["false","False"]]:Object.keys(q.options).sort().map(function(k){return [k.toUpperCase(),k+". "+q.options[k]]});
 choices.forEach(function(ch){var v=ch[0],cls="opt";
  if(a){if(right.indexOf(v)>-1)cls+=" right";else if(a.given.indexOf(v)>-1)cls+=" wrong"}
  var b=el("button",{class:cls,type:"button"},[el("span",{class:"rd"}),ch[1]]);if(a)b.disabled=true;
  b.addEventListener("click",function(){answers[key]={given:[v],correct:right.indexOf(v)>-1,at:new Date().toISOString()};save();renderExplainer(box,e)});
  grid.appendChild(b)});
 box.appendChild(grid);
 if(a){box.appendChild(el("p",{class:"res "+(a.correct?"good":"bad"),text:a.correct?"Correct. You have got it.":"Not yet. Read the explanation again, then try once more."}));
  if(q.explanation)box.appendChild(el("div",{class:"why"},[el("strong",{text:"Why"}),el("p",{text:q.explanation})]));
  var again=el("button",{class:"ghost",type:"button",text:"Try the check again"});again.addEventListener("click",function(){delete answers[key];save();renderExplainer(box,e)});box.appendChild(el("div",{class:"row"},[again]))}
}

/* ---- practice ---- */
var qs=(B.practice&&B.practice.questions)||[];var qi=0;
var P=$("s-practice"),PR=$("s-progress");
function isChoice(q){return q.type==="single_choice"||q.type==="multi_choice"}
var drafts={};
function draftFor(q){return drafts[q.id]||(drafts[q.id]={sel:[],text:"",reveal:false})}
function record(q,given,correct){answers[q.id]={given:given,correct:!!correct,at:new Date().toISOString()};save();renderPractice();renderProgress()}
function target(){var s=document.createElementNS(NS,"svg");s.setAttribute("viewBox","0 0 84 84");s.setAttribute("class","target");s.setAttribute("aria-hidden","true");
 [[34,"#ff6a00",.9],[25,"#1a0f08",1],[18,"#ff8a1c",1],[10,"#1a0f08",1],[5,"#ffb347",1]].forEach(function(c){var e=document.createElementNS(NS,"circle");e.setAttribute("cx","40");e.setAttribute("cy","44");e.setAttribute("r",String(c[0]));e.setAttribute("fill",c[1]);e.setAttribute("opacity",String(c[2]));s.appendChild(e)});
 var a=document.createElementNS(NS,"path");a.setAttribute("d","M40 44L74 10M66 8l9-2-2 9");a.setAttribute("stroke","#ffd27a");a.setAttribute("stroke-width","3.5");a.setAttribute("fill","none");a.setAttribute("stroke-linecap","round");s.appendChild(a);return s}
function head(sec,txt,icon){var p=el("p",{class:"lab",id:sec});p.appendChild(svgIcon(icon));p.appendChild(document.createTextNode(txt));return p}
function renderPractice(){
 clear(P);P.appendChild(head("pracLab","Practice","M4 4h16v16H4z|M8 12l3 3 5-6"));
 if(!qs.length){P.appendChild(el("p",{class:"empty",text:"No practice questions for this topic."}));return}
 var q=qs[qi],a=answers[q.id];
 P.appendChild(target());
 P.appendChild(el("p",{class:"qmeta",text:"Question "+(qi+1)+" of "+qs.length+" · "+q.marks+(q.marks===1?" mark":" marks")}));
 P.appendChild(el("p",{class:"qtext",text:q.question}));
 var draft=draftFor(q);
 if(isChoice(q)){
  var box=el("div",{class:"opts"});var multi=q.type==="multi_choice";var right=keys(q.answer);
  Object.keys(q.options).sort().forEach(function(k){
   var K=k.toUpperCase(),cls="opt"+(multi?" multi":"");if(a){if(right.indexOf(K)>-1)cls+=" right";else if(a.given.indexOf(K)>-1)cls+=" wrong"}else if(draft.sel.indexOf(K)>-1)cls+=" sel";
   if(String(q.options[k]).length>34)cls+=" wide";
   var b=el("button",{class:cls,type:"button",role:multi?"checkbox":"radio","aria-checked":String(draft.sel.indexOf(K)>-1)},[el("span",{class:"rd"}),q.options[k]]);
   if(a)b.disabled=true;
   b.addEventListener("click",function(){var i=draft.sel.indexOf(K);if(multi){if(i>-1)draft.sel.splice(i,1);else draft.sel.push(K)}else draft.sel=[K];renderPractice()});
   box.appendChild(b)});
  P.appendChild(box);
  if(multi&&!a)P.appendChild(el("p",{class:"qmeta",text:"Choose all that apply."}));
  if(!a){var c=el("button",{class:"go",type:"button"},["Submit Answer",svgIcon("M9 6l6 6-6 6")]);c.disabled=!draft.sel.length;c.addEventListener("click",function(){var g=draft.sel.slice().sort();record(q,g,same(g,right))});P.appendChild(c)}
 }else if(q.type==="true_false"){
  var box2=el("div",{class:"opts"});["true","false"].forEach(function(v){
   var cls="opt";if(a){if(q.answer.toLowerCase()===v)cls+=" right";else if(a.given[0]===v)cls+=" wrong"}
   var b=el("button",{class:cls,type:"button"},[el("span",{class:"rd"}),v==="true"?"True":"False"]);if(a)b.disabled=true;
   b.addEventListener("click",function(){record(q,[v],q.answer.toLowerCase()===v)});box2.appendChild(b)});P.appendChild(box2);
 }else{
  if(!a){var ta=q.type==="fill_blank"?el("input",{class:"ans",type:"text","aria-label":"Your answer",autocomplete:"off"}):el("textarea",{rows:"4","aria-label":"Your answer"});ta.value=draft.text;ta.addEventListener("input",function(){draft.text=ta.value});P.appendChild(ta);
   if(!draft.reveal){var show=el("button",{class:"go",type:"button"},["Show model answer",svgIcon("M9 6l6 6-6 6")]);show.addEventListener("click",function(){draft.reveal=true;renderPractice()});P.appendChild(show)}
   else{P.appendChild(el("div",{class:"why"},[el("strong",{text:"Model answer"}),el("p",{text:q.answer})]));
    var yes=el("button",{class:"go",type:"button",text:"I got it right"}),no=el("button",{class:"ghost",type:"button",text:"Not yet"});
    yes.addEventListener("click",function(){record(q,[draft.text],true)});no.addEventListener("click",function(){record(q,[draft.text],false)});P.appendChild(el("div",{class:"row"},[yes,no]))}
  }
 }
 if(a){
  P.appendChild(el("p",{class:"res "+(a.correct?"good":"bad"),text:a.correct?"Correct":"Not correct"}));
  if(!isChoice(q)&&q.type!=="true_false")P.appendChild(el("div",{class:"why"},[el("strong",{text:"Model answer"}),el("p",{text:q.answer})]));
  if(q.explanation)P.appendChild(el("div",{class:"why"},[el("strong",{text:"Why"}),el("p",{text:q.explanation})]));
  var ex=EX[q.knowledge_point_id];
  if(!a.correct&&ex){var xb=el("div",{});renderExplainer(xb,ex);P.appendChild(xb)}
  var redo=el("button",{class:"ghost",type:"button",text:"Try this question again"});redo.addEventListener("click",function(){delete answers[q.id];delete drafts[q.id];save();renderPractice();renderProgress()});P.appendChild(el("div",{class:"row"},[redo]));
 }
 var prev=el("button",{class:"ghost",type:"button",text:"Back"}),next=el("button",{class:"ghost",type:"button",text:qi===qs.length-1?"See progress":"Next question"});
 prev.disabled=qi===0;prev.addEventListener("click",function(){qi--;renderPractice();keepInView()});
 next.addEventListener("click",function(){if(qi<qs.length-1){qi++;renderPractice();keepInView()}else go("s-progress")});
 P.appendChild(el("div",{class:"nav2"},[prev,next]));
}
function keepInView(){var r=P.getBoundingClientRect();if(r.top<0||r.top>window.innerHeight*.5)go("s-practice")}

/* ---- progress ---- */
function stats(){var total=0,got=0,done=0,byKp={};
 qs.forEach(function(q){total+=q.marks;var a=answers[q.id];var k=q.knowledge_point_id||"";var s=byKp[k]||(byKp[k]={n:0,done:0,right:0});s.n++;if(a){done++;s.done++;if(a.correct){got+=q.marks;s.right++}}});
 return {total:total,got:got,done:done,byKp:byKp}}
function renderProgress(){
 clear(PR);PR.appendChild(head("progLab","Progress","M5 20V12|M10 20V5|M15 20v-6|M20 20V9"));
 var st=stats(),pct=st.total?Math.round(st.got/st.total*100):0,done=qs.length?Math.round(st.done/qs.length*100):0;
 $("pfill").style.width=done+"%";$("pbar").setAttribute("aria-valuenow",String(done));$("ptext").textContent=done+"% Complete";
 var grid=el("div",{class:"prog"});
 var ring=el("div",{class:"ring",role:"img","aria-label":"Score "+pct+" percent"});var s=document.createElementNS(NS,"svg");s.setAttribute("viewBox","0 0 132 132");
 var C=2*Math.PI*54;[["tr",0],["val",1]].forEach(function(x){var c=document.createElementNS(NS,"circle");c.setAttribute("cx","66");c.setAttribute("cy","66");c.setAttribute("r","54");c.setAttribute("class",x[0]);if(x[1]){c.setAttribute("stroke-dasharray",String(C));c.setAttribute("stroke-dashoffset",String(C));setTimeout(function(){c.setAttribute("stroke-dashoffset",String(C*(1-pct/100)))},60)}s.appendChild(c)});
 ring.appendChild(s);ring.appendChild(el("b",{text:pct+"%"}));ring.appendChild(el("small",{text:"SCORE"}));grid.appendChild(ring);
 var path=(B.progress&&B.progress.mastery_path)||[],weak=[];var ol=el("ul",{class:"path"});
 path.forEach(function(m){var k=st.byKp[m.id]||{n:0,done:0,right:0};var status="new";
  if(k.n&&k.done===k.n&&k.right===k.n)status="mastered";else if(k.done)status="learning";
  if(k.done&&k.right<k.done)weak.push(m.title);
  var dot=el("span",{class:"st-d "+status,title:status});if(status==="mastered")dot.appendChild(svgIcon("M5 12l4 4 10-10",""));
  var li=el("li",{},[dot,m.title]);if(k.n)li.appendChild(el("small",{text:k.right+"/"+k.n}));ol.appendChild(li)});
 if(!path.length)ol.appendChild(el("li",{class:"empty",text:"No mastery path for this topic."}));
 grid.appendChild(ol);PR.appendChild(grid);
 var loose=st.byKp[""];if(loose&&loose.done>loose.right){var n0=loose.done-loose.right;weak.push(n0+(n0===1?" other question":" other questions")+" missed")}
 var big,small;
 if(!st.done){big="Ready when you are";small="Start with question 1 in Practice."}
 else if(pct>=80){big="Excellent!";small="You are close to exam ready on this topic."}
 else if(pct>=50){big="Keep Going!";small="You're doing great."}
 else{big="Keep Going!";small="Read the explanations, then try again."}
 var keep=el("div",{class:"keep"});
 var tr=document.createElementNS(NS,"svg");tr.setAttribute("viewBox","0 0 24 24");tr.setAttribute("class","tr2");tr.setAttribute("aria-hidden","true");
 [["M8 4h8v4a4 4 0 0 1-8 0z","#ffb347"],["M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4","none"],["M12 12v4M9 20h6M10 16h4v4h-4z","none"]].forEach(function(p){var e=document.createElementNS(NS,"path");e.setAttribute("d",p[0]);e.setAttribute("fill",p[1]);e.setAttribute("stroke","#ff9a2c");e.setAttribute("stroke-width","1.8");e.setAttribute("stroke-linejoin","round");tr.appendChild(e)});
 keep.appendChild(tr);keep.appendChild(el("div",{},[el("b",{text:big}),el("span",{text:small})]));
 var up=document.createElementNS(NS,"svg");up.setAttribute("viewBox","0 0 110 56");up.setAttribute("class","up");up.setAttribute("aria-hidden","true");var pl=document.createElementNS(NS,"path");pl.setAttribute("d","M4 50L38 32L58 40L100 8M86 8h14v14");pl.setAttribute("fill","none");pl.setAttribute("stroke","#ff7a18");pl.setAttribute("stroke-width","5");pl.setAttribute("stroke-linecap","round");pl.setAttribute("stroke-linejoin","round");up.appendChild(pl);keep.appendChild(up);
 PR.appendChild(keep);
 if(weak.length){var w=el("div",{class:"weak"},[el("h4",{text:"Weak areas"})]);var u=el("ul");weak.forEach(function(x){u.appendChild(el("li",{text:x}))});w.appendChild(u);PR.appendChild(w)}
 var pf=el("details",{class:"pf"});pf.appendChild(el("summary",{text:"Your progress file"}));
 pf.appendChild(el("p",{class:"msg",text:store?"Progress is saved in this browser on this phone.":"This browser cannot keep progress after you close the page. Use Save progress file."}));
 var ex=el("button",{class:"ghost",type:"button",text:"Save progress file"});ex.addEventListener("click",exportProgress);
 var im=el("button",{class:"ghost",type:"button",text:"Load progress file"});var inp=el("input",{type:"file",accept:"application/json,.json",hidden:"hidden"});
 im.addEventListener("click",function(){inp.click()});inp.addEventListener("change",function(){importProgress(inp.files&&inp.files[0])});
 var rs=el("button",{class:"ghost",type:"button",text:"Start over"}),armed=false;
 rs.addEventListener("click",function(){if(!armed){armed=true;rs.textContent="Tap again to delete all answers";setTimeout(function(){armed=false;rs.textContent="Start over"},4000);return}answers={};drafts={};save();renderPractice();renderProgress();say("All answers deleted.")});
 pf.appendChild(el("div",{class:"row"},[ex,im,rs,inp]));pf.appendChild(el("p",{class:"msg",id:"pmsg",role:"status"}));PR.appendChild(pf);
}
function say(t){var m=$("pmsg");if(m){m.textContent=t;m.parentNode.open=true}}
function exportProgress(){
 var data={board_id:B.board_id,generated_at:B.generated_at,exported_at:new Date().toISOString(),answers:answers};
 var blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"});var a=document.createElement("a");
 a.href=URL.createObjectURL(blob);a.download="progress-"+B.board_id+".json";document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},2000);say("Progress file saved to your downloads.")}
function importProgress(f){
 if(!f)return;var r=new FileReader();r.onload=function(){try{var d=JSON.parse(r.result);
  if(!d||d.board_id!==B.board_id||typeof d.answers!=="object"||d.answers===null){say("That file is for a different board.");return}
  var ok={},ids={};qs.forEach(function(q){ids[q.id]=1});(B.explainers||[]).forEach(function(e){ids["e-"+e.kp_id]=1});
  Object.keys(d.answers).forEach(function(k){var a=d.answers[k];if(ids[k]&&a&&Array.isArray(a.given)&&typeof a.correct==="boolean")ok[k]={given:a.given.map(String),correct:a.correct,at:String(a.at||"")}});
  answers=ok;save();renderPractice();renderProgress();say("Progress loaded.")}catch(e){say("That file could not be read.")}};r.readAsText(f)}

/* ---- search ---- */
var IDX=[];
(nb.sections||[]).forEach(function(s,i){IDX.push({k:"Notes",t:s.heading+" "+(s.points||[]).join(" "),l:s.heading,go:function(){go("ns-"+i,$("ns-"+i))}})});
(nb.key_terms||[]).forEach(function(t,i){IDX.push({k:"Key concept",t:t.term+" "+t.meaning,l:t.term,go:function(){go("kt-"+i,$("kt-"+i))}})});
(nb.formulas||[]).forEach(function(f,i){IDX.push({k:"Formula",t:f.name+" "+f.explanation,l:f.name,go:function(){go("fx-"+i,$("fx-"+i))}})});
(B.explainers||[]).forEach(function(e,i){IDX.push({k:"Explanation",t:e.title+" "+e.explanation,l:e.title,go:function(){var d=$("xd-"+i);d.open=true;go("xd-"+i,d)}})});
qs.forEach(function(q,i){IDX.push({k:"Question "+(i+1),t:q.question,l:short(q.question,80),go:function(){qi=i;renderPractice();go("s-practice",P)}})});
var R=$("results");
function hideResults(){R.hidden=true;clear(R)}
$("q").addEventListener("input",function(){var v=$("q").value.trim().toLowerCase();clear(R);if(v.length<2){R.hidden=true;return}
 var hits=IDX.filter(function(x){return x.t.toLowerCase().indexOf(v)>-1}).slice(0,6);
 if(!hits.length){R.appendChild(el("p",{class:"msg",style:"padding:8px 10px;margin:0",text:"Nothing found on this board."}))}
 hits.forEach(function(h){var b=el("button",{type:"button"},[el("small",{text:h.k}),h.l]);b.addEventListener("click",function(){hideResults();$("q").value="";h.go()});R.appendChild(b)});R.hidden=false});
document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".search"))hideResults()});

/* ---- print / PDF ---- */
function buildPrint(){var o=$("printOut");clear(o);
 o.appendChild(el("h1",{text:B.topic}));o.appendChild(el("p",{text:[B.level,B.subject,reviewed?"Approved":"Draft, not yet checked"].filter(Boolean).join(" • ")}));
 var svg=document.querySelector("#frame svg");if(svg){var pp=el("div",{class:"pp"});pp.appendChild(svg.cloneNode(true));o.appendChild(pp)}
 if(nb.summary)o.appendChild(el("p",{text:nb.summary}));
 (nb.sections||[]).forEach(function(s){o.appendChild(el("h2",{text:s.heading}));var u=el("ul");(s.points||[]).forEach(function(p){u.appendChild(el("li",{text:p}))});o.appendChild(u)});
 if((nb.formulas||[]).length){o.appendChild(el("h2",{text:"Formulas"}));nb.formulas.forEach(function(f){o.appendChild(el("p",{},[el("b",{text:f.name+": "}),f.latex+(f.explanation?" ("+f.explanation+")":"")]))})}
 if((nb.key_terms||[]).length){o.appendChild(el("h2",{text:"Key terms"}));var u=el("ul");nb.key_terms.forEach(function(t){u.appendChild(el("li",{},[el("b",{text:t.term+": "}),t.meaning]))});o.appendChild(u)}
 if(qs.length){o.appendChild(el("h2",{text:"Practice"}));var ol=el("ol");qs.forEach(function(q){var li=el("li",{text:q.question+" ["+q.marks+"]"});var ks=Object.keys(q.options||{}).sort();if(ks.length){var u2=el("ul");ks.forEach(function(k){u2.appendChild(el("li",{text:k+". "+q.options[k]}))});li.appendChild(u2)}ol.appendChild(li)});o.appendChild(ol);
  o.appendChild(el("h2",{text:"Answer key"}));var ak=el("ol");qs.forEach(function(q){ak.appendChild(el("li",{text:q.answer+(q.explanation?" — "+q.explanation:"")}))});o.appendChild(ak)}
}
window.addEventListener("beforeprint",buildPrint);
$("pdfBtn").addEventListener("click",function(){buildPrint();window.print()});

renderPractice();renderProgress();
})();
</script>
</body>
</html>
"""


@lru_cache(maxsize=1)
def _brand() -> dict:
    return json.loads(_BRAND_FILE.read_text(encoding="utf-8"))


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
    # One pass over the template, so text inside a value can never be read as a marker.
    values = {
        "__TITLE__": _escape_html(f"{board.topic} - {board.subject}"),
        "__FONTS__": _font_css(),
        "__LOGO__": _brand()["logo_svg"],
        "__SVG__": _prefix_ids(svg or ""),
        "__BOARD_JSON__": _json_for_script(board.model_dump(mode="json")),
    }
    return re.sub(
        r"__TITLE__|__FONTS__|__LOGO__|__SVG__|__BOARD_JSON__",
        lambda m: values[m.group(0)],
        _TEMPLATE,
    )


def write_bundle(store: BoardStore, board_id: str, out: Path | str | None = None) -> Path:
    board = store.load(board_id)
    svg = store.read_asset(board)
    target = Path(out) if out else store.board_dir(board_id) / f"{board_id}.html"
    atomic_write_text(target, render_bundle(board, svg))
    return target


__all__ = ["render_bundle", "write_bundle"]
