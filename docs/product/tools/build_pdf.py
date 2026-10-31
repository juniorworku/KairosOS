from pathlib import Path
import re,html
root=Path(__file__).resolve().parents[3]
(root/"tmp/pdfs").mkdir(parents=True, exist_ok=True)
def inline(s):
 s=html.escape(s)
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m: '<a href="'+m[2]+'">'+m[1]+'</a>' if m[2].startswith('https://') else m[1],s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
 return s

def markdown(s):
 lines=s.splitlines(); out=[];i=0
 while i<len(lines):
  x=lines[i].strip()
  if not x: i+=1;continue
  if x.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    row=[v.strip() for v in lines[i].strip().strip('|').split('|')]
    if not all(re.match(r'^:?-+:?$',v) for v in row): rows.append(row)
    i+=1
   out.append('<table><thead><tr>'+''.join('<th>'+inline(v)+'</th>' for v in rows[0])+'</tr></thead><tbody>')
   for row in rows[1:]:out.append('<tr>'+''.join('<td>'+inline(v)+'</td>' for v in row)+'</tr>')
   out.append('</tbody></table>');continue
  m=re.match(r'^(#{1,3}) (.*)',x)
  if m:out.append(f'<h{len(m[1])}>{inline(m[2])}</h{len(m[1])}>');i+=1;continue
  if x.startswith('- '):out.append('<p class="bullet">'+inline(x[2:])+'</p>');i+=1;continue
  if re.match(r'^\d+\. ',x):out.append('<p class="step">'+inline(x)+'</p>');i+=1;continue
  para=[x];i+=1
  while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||- |\d+\. )',lines[i].strip()):para.append(lines[i].strip());i+=1
  out.append('<p>'+inline(' '.join(para))+'</p>')
 return '\n'.join(out)

purple='#6438E8'
def wireframe():
 s=['<svg viewBox="0 0 1000 560" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Calendar workspace concept">','<rect width="1000" height="560" rx="12" fill="#F6F7F9"/>']
 def rect(x,y,w,h,fill='#FFFFFF',stroke='#E2E5EB'):s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}"/>')
 def text(x,y,t,size=12,fill='#17191F'):s.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{fill}">{html.escape(t)}</text>')
 text(20,30,'KAIROS',17);text(245,30,'Today    /    Week',12);text(790,30,'Daily coach sync',12)
 rect(12,48,220,498);rect(242,48,496,498);rect(748,48,240,498)
 text(28,78,'GOALS & TASKS',11);text(28,115,'Launch paid beta',14)
 for y,t in [(145,'Define the offer'),(176,'Interview customers'),(207,'Prepare landing page'),(265,'SUPPORT AREAS'),(299,'Inbox'),(330,'Life Admin'),(361,'Relationships')]:text(35,y,t,12)
 text(255,78,'November 2 - 8',14);text(635,78,'<   Today   >',10)
 for n,t in enumerate(['MON','TUE','WED','THU','FRI','SAT','SUN']):text(283+n*64,108,t,9)
 for j in range(8):
  y=130+j*48;text(250,y+4,str(8+j)+':00',8,'#596170');s.append(f'<path d="M280 {y}H725" stroke="#E2E5EB"/>')
 for j in range(8):s.append(f'<path d="M{280+j*64} 118V500" stroke="#E2E5EB"/>')
 for x,y,w,h,t in [(283,135,59,90,'Research'),(347,183,59,65,'Meeting'),(411,135,59,90,'Build'),(475,279,59,65,'Review'),(539,183,59,90,'Outreach')]:rect(x,y,w,h,'#F0EBFF');text(x+4,y+17,t,8)
 rect(283,332,59,75,'#FFFFFF',purple);text(287,350,'Proposed',8,purple)
 text(764,78,'Your priorities',15);text(764,105,'1. Validate the offer',11);text(764,131,'2. Prepare customer calls',11)
 rect(762,158,212,130,'#F6F7F9');text(774,181,'Proposed adjustment',12);text(774,207,'Move research to 12:00',10);text(774,227,'Reason: meeting conflict',10);rect(774,246,92,28,purple,purple);text(787,264,'Review',11,'#FFFFFF')
 rect(762,305,212,75);text(775,330,'Ready to focus?',12);text(775,354,'Start your core task',11,purple)
 rect(762,466,212,60);text(774,492,'Ask your coach...',11,'#596170')
 s.append('</svg>');return ''.join(s)

files=[('01','Product description','VISION.md'),('02','Requirements & acceptance','REQUIREMENTS.md'),('03','End-to-end workflows','WORKFLOWS.md'),('04','Interface architecture','DESIGN.md'),('05','Screen design & components','SCREEN_SPECIFICATIONS.md'),('06','Features & integrations','FEATURES.md'),('07','Templates & background operation','AUTOMATION.md'),('08','Shared context & AI budgets','CONTEXT.md'),('09','Implementation & release gates','IMPLEMENTATION.md'),('10','Decisions & references','DECISIONS.md')]
css='''table.requirements th:nth-child(1){width:8%}table.requirements th:nth-child(2){width:25%}table.requirements th:nth-child(3){width:67%}table.crosscut th:nth-child(1){width:9%}table.crosscut th:nth-child(2){width:24%}table.crosscut th:nth-child(3){width:67%}@page{size:A4;margin:18mm 17mm 19mm;@bottom-left{content:"KAIROS / PRODUCT BLUEPRINT";font-size:8pt;color:#596170}@bottom-right{content:counter(page);font-size:8pt;color:#596170}}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#17191F;font-size:10pt;line-height:1.5;margin:0}h1{font-size:27pt;line-height:1.16;letter-spacing:-.7px;margin:0 0 24px}h2{font-size:16pt;line-height:1.25;margin:27px 0 10px;break-after:avoid}h3{font-size:12pt;margin-top:20px;break-after:avoid}p{margin:0 0 10px;orphans:3;widows:3}a{color:#6438E8;text-decoration:none}table{border-collapse:collapse;width:100%;font-size:8.5pt;line-height:1.4;margin:14px 0 20px;table-layout:fixed}th,td{padding:8px 7px;vertical-align:top;text-align:left;border-bottom:1px solid #E2E5EB;overflow-wrap:anywhere}th{background:#F0EBFF;color:#17191F;font-weight:700}tr{break-inside:avoid}thead{display:table-header-group}.chapter{break-before:page}.kicker{font-size:9pt;letter-spacing:1.7px;color:#6438E8;font-weight:bold;margin-bottom:15px}.cover{height:244mm;display:flex;flex-direction:column;justify-content:space-between}.cover h1{font-size:53pt;line-height:1.03;letter-spacing:-2px}.subtitle{font-size:19pt;max-width:490px;line-height:1.35}.line{width:65px;height:5px;background:#6438E8;margin:28px 0}.muted{color:#596170}.note{padding:15px 18px;background:#F6F7F9;border-left:3px solid #6438E8;margin:20px 0}.bullet{padding-left:14px;position:relative}.bullet:before{content:"•";position:absolute;left:0;color:#6438E8}.step{padding-left:12px;border-left:2px solid #E2E5EB}.tocrow{padding:14px 0;border-bottom:1px solid #E2E5EB;font-size:13pt}.tocnum{display:inline-block;width:42px;color:#6438E8}svg{width:100%;height:auto;margin:15px 0}figure{margin:0;break-inside:avoid}figcaption{font-size:9pt;color:#596170;margin:5px 0 20px}.override{background:#F0EBFF;padding:14px 16px;margin-bottom:22px}'''
parts=['<!doctype html><html><head><meta charset="utf-8"><title>Kairos Product Blueprint</title><style>'+css+'</style></head><body>']
parts.append('''<section class="cover"><div><div class="kicker">KAIROS / PRODUCT DOCUMENTATION</div><div class="line"></div><h1>Your priorities.<br>Your commitments.<br>Followed through.</h1><p class="subtitle">A full AI executive assistant with five shared engines, approved plans and server-run follow-up.</p></div><div><p><strong>Product blueprint & UI/UX specification</strong><br>Version 2.1 / 31 October 2026</p><p class="muted">Clean Tech edition / Design-stage specification<br>Includes five engines, fixed workflows, screen designs, shared context, budgets and release gates.</p></div></section>''')
parts.append('<section class="chapter"><div class="kicker">DOCUMENT GUIDE</div><h1>From intent to execution</h1><p>This document consolidates the product documentation suite and expands the screen-by-screen design. Confirmed decisions are separated from proposed defaults and unresolved platform choices.</p><div class="note"><strong>Core loop</strong><br>Clarify → Plan → Approve → Schedule → Daily coach sync → Focus → Follow through → Review → Propose adjustments → Approve.</div>')
for num,title,_ in files:parts.append(f'<div class="tocrow"><span class="tocnum">{num}</span>{title}</div>')
parts.append('<p style="margin-top:25px" class="muted">Status: design specification. This is not evidence that every feature is implemented and does not authorize deployment. Existing implementation and live-provider acceptance remain separate.</p></section>')
parts.append('<section class="chapter"><div class="kicker">WORKSPACE CONCEPT / S04</div><h1>A calm calendar at the center</h1><figure>'+wireframe()+'<figcaption>Conceptual desktop layout with the coach open. The wireframe illustrates information hierarchy, not final pixel dimensions.</figcaption></figure><h2>One workspace, three roles</h2><p><strong>Left:</strong> goals, tasks, support areas and quick capture. <strong>Center:</strong> the real week, linked work and proposed adjustments. <strong>Right:</strong> daily coaching, chat, follow-ups and explicit approvals.</p><div class="note">When the coach closes, the calendar expands. On smaller screens, drawers and day/agenda views preserve usable space.</div></section>')
parts.append('''<section class="chapter"><div class="kicker">ASSISTANT ARCHITECTURE</div><h1>Five engines. One shared context.</h1><svg viewBox="0 0 1000 620" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Shared context and five assistant engines"><rect width="1000" height="620" rx="12" fill="#F6F7F9"/><g fill="white" stroke="#E2E5EB"><rect x="30" y="30" width="290" height="65" rx="7"/><rect x="355" y="30" width="290" height="65" rx="7"/><rect x="680" y="30" width="290" height="65" rx="7"/><rect x="30" y="145" width="940" height="95" rx="7" fill="#F0EBFF"/><rect x="30" y="295" width="172" height="90" rx="7"/><rect x="222" y="295" width="172" height="90" rx="7"/><rect x="414" y="295" width="172" height="90" rx="7"/><rect x="606" y="295" width="172" height="90" rx="7"/><rect x="798" y="295" width="172" height="90" rx="7"/><rect x="30" y="440" width="940" height="65" rx="7"/><rect x="30" y="545" width="940" height="45" rx="7"/></g><g stroke="#6438E8" fill="none"><path d="M175 95V120H500V145M500 95V145M825 95V120H500M500 240V265H116V295M500 265H308V295M500 265V295M500 265H692V295M692 265H884V295M116 385V410H500V440M308 385V410M500 385V440M692 385V410M884 385V410H500M500 505V545"/></g><g font-family="Arial" fill="#17191F" text-anchor="middle"><text x="175" y="68" font-size="17">Google Calendar</text><text x="500" y="68" font-size="17">Gmail</text><text x="825" y="68" font-size="17">Meeting notes / Manual</text><text x="500" y="182" font-size="21">Shared source store + evidence + rolling summaries</text><text x="500" y="211" font-size="14">Incremental ingestion / Freshness / Bounded context packs / Purpose budgets</text><text x="116" y="329" font-size="16">Commitment</text><text x="116" y="352" font-size="16">ledger</text><text x="308" y="329" font-size="16">Calendar</text><text x="308" y="352" font-size="16">guardian</text><text x="500" y="329" font-size="16">Briefing</text><text x="500" y="352" font-size="16">composer</text><text x="692" y="341" font-size="16">Goal engine</text><text x="884" y="341" font-size="16">Insights</text><text x="500" y="478" font-size="18">Fixed templates / Server runs / Reports + notifications + proposals</text><text x="500" y="574" font-size="16">Exact approval before accepted tasks, external drafts, sends and calendar changes</text></g></svg><p class="muted">Logical modules share facts and bounded AI steps. Five engines do not require five continuously running agents or five deployed microservices.</p><div class="note">The first web release includes all five engines. Calendar → meetings → email is internal build order, not a planner-only release.</div></section>''')
for num,title,file in files:
 body=(root/'docs/product'/file).read_text()
 body=re.sub(r'^# .*\n','',body,count=1)
 parts.append(f'<section class="chapter"><div class="kicker">{num} / KAIROS BLUEPRINT</div><h1>{title}</h1>')
 rendered=markdown(body)
 if file=='REQUIREMENTS.md':
  rendered=rendered.replace('<table>', '<table class="requirements">',1)
  pos=rendered.find('<table>',rendered.find('</table>'))
  if pos>=0: rendered=rendered[:pos]+rendered[pos:].replace('<table>','<table class="crosscut">',1)
 parts.append(rendered);parts.append('</section>')
parts.append('''<section class="chapter"><div class="kicker">FOCUS CONCEPT / S07-S08</div><h1>One task. Clear controls.</h1><svg viewBox="0 0 900 490" xmlns="http://www.w3.org/2000/svg"><rect width="900" height="490" rx="12" fill="#F6F7F9"/><rect x="35" y="35" width="830" height="340" rx="12" fill="white" stroke="#E2E5EB"/><text x="65" y="77" font-family="Arial" font-size="15" fill="#596170">FOCUS SESSION</text><text x="65" y="123" font-family="Arial" font-size="27" fill="#17191F">Prepare customer interviews</text><text x="65" y="151" font-family="Arial" font-size="14" fill="#596170">Objective: finalize the five core questions</text><text x="65" y="242" font-family="Arial" font-size="66" fill="#17191F">24:18</text><rect x="65" y="278" width="110" height="42" rx="6" fill="#6438E8"/><text x="94" y="305" font-family="Arial" font-size="16" fill="white">Pause</text><rect x="190" y="278" width="110" height="42" rx="6" fill="white" stroke="#E2E5EB"/><text x="220" y="305" font-family="Arial" font-size="16">Finish</text><text x="520" y="204" font-family="Arial" font-size="15">Browser blocking: active</text><text x="520" y="237" font-family="Arial" font-size="15">Native app blocking: not included</text><text x="520" y="290" font-family="Arial" font-size="15" fill="#6438E8">Lo-fi audio / Play / Volume</text><rect x="430" y="401" width="435" height="58" rx="10" fill="white" stroke="#E2E5EB"/><circle cx="452" cy="430" r="5" fill="#6438E8"/><text x="468" y="436" font-family="Arial" font-size="13">Interviews</text><text x="590" y="437" font-family="Arial" font-size="21">24:18</text><text x="695" y="436" font-family="Arial" font-size="13" fill="#6438E8">Pause</text><text x="765" y="436" font-family="Arial" font-size="13">Finish</text></svg><p class="muted">Conceptual workstation and floating in-app timer. Report actual device coverage; sound is optional. Desktop timer companions for macOS, Windows and Linux follow the web release. System website blocking starts later on one selected OS.</p><h2>Completion is a separate decision</h2><p>Finish the session, record the accomplishment, explicitly update task status and optionally check in on an outcome. Unfinished work can produce a new proposal; it never silently reschedules itself.</p></section>''')
parts.append('</body></html>')
(root/'tmp/pdfs/kairos-product-blueprint.html').write_text(''.join(parts))
print('Created print source from authoritative Markdown chapters')
