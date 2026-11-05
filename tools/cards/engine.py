"""휴머니티 light 카드 엔진 — 원고 한 장에서 카드를 찍고, 카드 문구가 본문과 같은지 검사한다.

사용:
  python3 engine.py <원고.txt> [--out 출력폴더] [--check-only] [--preview 미리보기.png]

원고.txt 는 규칙서(판 4) 10번 형식(【글 코드】【글 종류】【카테고리】【본문】【카드 데이터】 …)의 일반 텍스트.
처음 한 번: cd tools/cards && npm i   (글꼴)
결과: <출력폴더>/<글 코드>/<글 코드>_<번호>_<이름>.png|jpg, 그리고 같은 폴더에 report.json
일치 검사에 실패하면 카드를 만들지 않고 종료 코드 2.
"""
import html, json, os, re, subprocess, sys, unicodedata

D = os.path.dirname(os.path.abspath(__file__))
E = html.escape

# ---------- 원고 읽기 ----------
def sections(text):
    parts = re.split(r'【([^】]+)】', text)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i].strip()] = parts[i + 1].strip()
    return out

def card_data(block):
    d = {}
    for line in block.splitlines():
        m = re.match(r'\s*([^:：\s][^:：]*?)\s*[:：]\s*(.*)$', line)
        if m:
            d[m.group(1).strip()] = m.group(2).strip()
    return d

def norm(s):
    s = unicodedata.normalize('NFC', s)
    s = s.replace('\\', '')  # 드라이브 마크다운 이스케이프 제거
    return re.sub(r'\s+', ' ', s).strip()

# ---------- 일치 검사 ----------
MUST_IN_BODY = ['표지.한줄', '한장틀.큰질문', '한장틀.작은질문1', '한장틀.작은질문2', '한장틀.틀릴수있는경우',
                '아이말.질문', '아이말.대답1', '아이말.대답2',
                '집에서.질문1', '집에서.질문2', '집에서.질문3', '집에서.맺음',
                '근거1.결과', '근거2.결과', '원고지.예문',
                '갈림길.질문', '갈림길.가', '갈림길.나']
SHORT_SKIP = ['아이말.질문', '아이말.대답1', '아이말.대답2', '근거1.결과', '근거2.결과', '원고지.예문']

def check_sentence(meta, d, body):
    """‘문장 글’(원장 노트 연재): 표지 + 본문 문장 카드 3장. 카드 문장은 본문에 글자 그대로 있어야 한다."""
    problems = []
    nb = norm(body)
    for k in ('표지.제목', '문장1', '문장2', '문장3'):
        if not d.get(k):
            problems.append(f'{k}: 비어 있음')
    for k in ('문장1', '문장2', '문장3'):
        v = norm(d.get(k, ''))
        if v and v not in nb:
            problems.append(f'{k}: 본문에 같은 문장이 없음 → “{d[k]}”')
        if len(v) > 60:
            problems.append(f'{k}: 60자 이하로(카드 한 장에 네 줄 안) → “{d[k]}”')
    got = set(re.findall(r'\[카드 (\d)\]', body))
    if got != {'1', '2', '3', '4'}:
        problems.append(f'본문의 [카드 n] 자리: {sorted(got)} → 문장 글은 1~4')
    if not meta.get('머리 줄'):
        problems.append('【머리 줄】: 비어 있음')
    return problems

def check(meta, d, body):
    if meta.get('글 종류', '').startswith('문장'):
        return check_sentence(meta, d, body)
    b = norm(body)
    kind_short = meta.get('글 종류', '').startswith('짧')
    problems = []
    for k in MUST_IN_BODY:
        if k not in d or not d[k]:
            continue
        if kind_short and k in SHORT_SKIP:
            continue
        v = norm(d[k]).strip('“”"')
        if v not in b:
            problems.append(f'{k}: 본문에 같은 문장이 없음 → “{d[k]}”')
    need = ['표지.제목', '한장틀.큰질문', '집에서.질문1', '집에서.질문2', '집에서.질문3', '집에서.맺음',
            '갈림길.질문', '갈림길.가', '갈림길.나']
    if not kind_short:
        need += ['아이말.질문', '아이말.대답1', '아이말.대답2']
    for k in need:
        if not d.get(k):
            problems.append(f'{k}: 값이 비어 있음')
    cards_in_body = set(re.findall(r'\[카드 (\d)\]', body))
    want = {'1', '3', '5', '6'} if kind_short else {'1', '2', '3', '4', '5', '6'}
    if cards_in_body != want:
        problems.append(f'본문의 카드 자리 {sorted(cards_in_body)} ≠ 필요한 자리 {sorted(want)}')
    if not meta.get('머리 줄'):
        problems.append('【머리 줄】: 비어 있음(카드 서명 줄에 씀)')
    for k in ('갈림길.가', '갈림길.나'):
        if len(d.get(k, '')) > 26:
            problems.append(f'{k}: 26자 이하로(카드 한 칸에 두 줄 안) → “{d[k]}”')
    return problems

# ---------- 카드 HTML ----------
SIG = {'t': ''}  # 모든 카드 아래 같은 서명 줄(머리 줄의 첫 칸)

def sig(cls=''):
    return f'<div class="sig {cls}">휴머니티 light&nbsp;&nbsp;│&nbsp;&nbsp;{E(SIG["t"])}</div>'
def bk(d):
    return d.get('표지.제목', '')

def cardC(d, photo):
    tag = ' · '.join(x for x in (d.get('표지.칩2', ''), d.get('표지.칩1', '')) if x)
    return f'''<div class="c C" id="k"><img class="bg" src="{photo}"><div class="vg"></div><div class="tag">{E(tag)}</div><img class="lg" src="assets/logo.png">
<div class="glass"><div class="t fit2" id="ttl">{E(bk(d))}</div><div class="s">{E(d.get('표지.한줄', ''))}</div></div>{sig('w')}</div>'''

def cardB1(d):
    return f'''<div class="c B" id="k"><div class="k">{E(d.get('표지.칩2', ''))}</div><div class="q fit2" id="ttl">{E(bk(d))}</div><div class="rule"></div><div class="sub">{E(d.get('표지.한줄', ''))}</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardF(d):
    rows = [('글 · 그림', '책.글그림'), ('출판사', '책.출판사'), ('쪽수', '책.쪽수'), ('함께 읽는 학년', '책.학년'), ('주제어', '책.주제어'), ('기록', '책.기록')]
    dl = ''.join(f'<dt>{E(a)}</dt><dd>{E(d[b])}</dd>' for a, b in rows if d.get(b))
    return f'''<div class="c F" id="k"><div class="card"><div class="rl"></div><div class="hd"><span>책 한 장 정보</span><span>{E(d.get('표지.칩2', ''))}</span></div>
<div class="tt fit">{E(d.get('책.제목', bk(d)))}</div><dl>{dl}</dl><img class="stamp" src="assets/logo_brown.png"><div class="hole"></div></div>{sig('w')}</div>'''

def cardE(d):
    def box(i, lab):
        return f'''<div class="box {'a' if i == 1 else 'b'}"><span class="lab">{lab}</span><div class="n">{E(d.get(f'근거{i}.숫자', ''))}</div><div class="who">{E(d.get(f'근거{i}.대상', ''))}</div><div class="r">{E(d.get(f'근거{i}.결과', ''))}</div></div>'''
    return f'''<div class="c E" id="k"><div class="grid"></div><div class="k">전문가의 눈 · 오늘의 근거</div><div class="t">{E(d.get('한장틀.작은질문1', ''))}</div><img class="lg" src="assets/logo_navy.png">
{box(1, '연구')}{box(2, '다른 결과')}<div class="ft">연구 초록 기준 요약</div>{sig()}</div>'''

def cardD(d):
    t = d.get('원고지.예문', '')
    cells = ''.join(f'<span>{E(c) if c != " " else ""}</span>' for c in t)
    pad = (15 - len(t) % 15) % 15
    cells += '<span></span>' * pad + '<span style="color:#c0472b">왜</span><span style="color:#c0472b">?</span>' + '<span></span>' * 28
    return f'''<div class="c D" id="k"><div class="k">쓰기 이야기</div><div class="t">{E(bk(d))}</div><img class="lg" src="assets/logo_navy.png">
<div class="grid">{cells}</div><div class="cap">원고에 예로 든 글이에요. 끝에 <b>“왜 그렇게 느꼈는지”</b> 한 문장을 붙이면 한 문단이 됩니다.</div>{sig()}</div>'''

def cardB3(d):
    band = d.get('한장틀.띠') or '이 이야기는 무슨 질문에 대한 답일까?'
    return f'''<div class="c B" id="k"><div class="k">휴머니티의 한 장 틀 · {E(band)}</div><div class="q" style="font-size:64px;top:200px">{E(d.get('한장틀.큰질문', ''))}</div><div class="rule" style="top:420px"></div>
<div class="bl"><p><b>작은 질문</b>{E(d.get('한장틀.작은질문1', ''))}</p><p><b>작은 질문</b>{E(d.get('한장틀.작은질문2', ''))}</p><p style="margin-top:34px"><b>틀릴 수 있는 경우</b><br>{E(d.get('한장틀.틀릴수있는경우', ''))}</p></div>
<img class="lg" src="assets/logo_navy.png"><div class="ft">{E(bk(d))}</div>{sig()}</div>'''

def cardG(d):
    q = lambda s: E(s.strip('“”"'))
    return f'''<div class="c G" id="k"><div class="k">아이의 말로 보기 · {E(bk(d))}</div><div class="t">{E(d.get('아이말.질문', ''))}</div>
<div class="wrap"><div class="bb b1"><small>그 학년다운 대답</small>“{q(d.get('아이말.대답1', ''))}”</div><div class="bb b2"><small>한 걸음 나아간 대답</small>“{q(d.get('아이말.대답2', ''))}”</div></div>
<div class="ft">예로 들어 본 대답이에요</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardS0(d):
    return f'''<div class="c S S0" id="k"><div class="fr"></div><div class="lab">{E(SIG["t"])}</div>
<div class="t fit2" id="ttl">{E(d.get('표지.제목', ''))}</div><div class="rule"></div><div class="sub">{E(d.get('표지.한줄', ''))}</div>
<img class="lg" src="assets/logo_brown.png">{sig()}</div>'''

def cardS(d, k, n):
    return f'''<div class="c S" id="k"><div class="no">{n}</div><div class="t">{E(d.get(k, ''))}</div><div class="rule"></div>
<img class="lg" src="assets/logo_brown.png">{sig()}</div>'''

def cardH(d):
    return f'''<div class="c H" id="k"><div class="k">갈림길 · 너라면?</div><div class="t">{E(d.get('갈림길.질문', ''))}</div>
<div class="opt o1"><b>가</b><span>{E(d.get('갈림길.가', ''))}</span></div><div class="vs">VS</div><div class="opt o2"><b>나</b><span>{E(d.get('갈림길.나', ''))}</span></div>
<div class="ft">정답은 없어요. 고른 까닭을 말해 보면 됩니다 · {E(bk(d))}</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardA(d):
    return f'''<div class="c A" id="k"><div class="lines"></div><div class="mg"></div><div class="holes"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="tape"></div>
<div class="ln pen lab fit" style="top:80px">집에서 해 보기 · {E(bk(d))}</div>
<div class="ln pen big" style="top:160px;height:160px">오늘 저녁,&nbsp;<span class="mark">세&nbsp;가지만</span>&nbsp;물어봐&nbsp;주세요</div>
<div class="ln pen q" style="top:400px"><span class="no">하나</span><span class="fit">{E(d.get('집에서.질문1', ''))}</span></div>
<div class="ln pen q" style="top:480px"><span class="no">둘</span><span class="fit">{E(d.get('집에서.질문2', ''))}</span></div>
<div class="ln pen q" style="top:560px"><span class="no">셋</span><span class="fit">{E(d.get('집에서.질문3', ''))}</span></div>
<div class="ln pen q fit" style="top:720px;color:#b8572f">→ {E(d.get('집에서.맺음', ''))}</div><img class="lg" src="assets/logo.png">{sig()}</div>'''

# ---------- 판 5: 다변화 — 글마다 색 테마 하나 + 카드마다 배치 두 가지 중 하나 ----------
import zlib
def pick(code, key, n):
    return zlib.crc32((code + ':' + key).encode()) % n

def cardC2(d, photo):
    tag = ' · '.join(x for x in (d.get('표지.칩2', ''), d.get('표지.칩1', '')) if x)
    return f'''<div class="c C C2" id="k"><img class="bg" src="{photo}"><div class="vg2"></div>
<div class="top"><div class="tag2">{E(tag)}</div><div class="t fit2" id="ttl">{E(bk(d))}</div><div class="s">{E(d.get('표지.한줄', ''))}</div></div>
<img class="lg" src="assets/logo.png">{sig('w')}</div>'''

def cardF2(d):
    rows = [('글 · 그림', '책.글그림'), ('출판사', '책.출판사'), ('쪽수', '책.쪽수'), ('함께 읽는 학년', '책.학년'), ('주제어', '책.주제어'), ('기록', '책.기록')]
    dl = ''.join(f'<div class="r"><span>{E(a)}</span><b>{E(d[b])}</b></div>' for a, b in rows if d.get(b))
    return f'''<div class="c F2" id="k"><div class="strip"></div><div class="hd">책 한 장 정보 · {E(d.get('표지.칩2', ''))}</div>
<div class="tt fit">{E(d.get('책.제목', bk(d)))}</div><div class="bar"></div><div class="rows">{dl}</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardH2(d):
    return f'''<div class="c H H2" id="k"><div class="k">갈림길 · 너라면?</div><div class="t">{E(d.get('갈림길.질문', ''))}</div>
<div class="cols"><div class="col c1"><b>가</b><span>{E(d.get('갈림길.가', ''))}</span></div><div class="col c2"><b>나</b><span>{E(d.get('갈림길.나', ''))}</span></div><div class="vs2">VS</div></div>
<div class="ft">정답은 없어요. 고른 까닭을 말해 보면 됩니다</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardB3b(d):
    band = d.get('한장틀.띠') or '이 이야기는 무슨 질문에 대한 답일까?'
    return f'''<div class="c B B3b" id="k"><div class="k">휴머니티의 한 장 틀</div><div class="band">{E(band)}</div>
<div class="big">{E(d.get('한장틀.큰질문', ''))}</div><div class="lines"><i></i><i></i></div>
<div class="sm s1"><em>작은 질문</em>{E(d.get('한장틀.작은질문1', ''))}</div><div class="sm s2"><em>작은 질문</em>{E(d.get('한장틀.작은질문2', ''))}</div>
<div class="wr"><em>틀릴 수 있는 경우</em>{E(d.get('한장틀.틀릴수있는경우', ''))}</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardG2(d):
    q = lambda s: E(s.strip('“”"'))
    return f'''<div class="c G G2" id="k"><div class="k">아이의 말로 보기</div><div class="t">{E(d.get('아이말.질문', ''))}</div>
<div class="qs"><div class="qq"><i>“</i><small>그 학년다운 대답</small><p class="bb">{q(d.get('아이말.대답1', ''))}</p></div><div class="qq q2"><i>“</i><small>한 걸음 나아간 대답</small><p class="bb">{q(d.get('아이말.대답2', ''))}</p></div></div>
<div class="ft">예로 들어 본 대답이에요</div><img class="lg" src="assets/logo_navy.png">{sig()}</div>'''

def cardA2(d):
    return f'''<div class="c A2" id="k"><div class="k">집에서 해 보기 · 오늘 저녁, 세 가지만</div>
<div class="nt n1"><b>하나</b><span>{E(d.get('집에서.질문1', ''))}</span></div><div class="nt n2"><b>둘</b><span>{E(d.get('집에서.질문2', ''))}</span></div><div class="nt n3"><b>셋</b><span>{E(d.get('집에서.질문3', ''))}</span></div>
<div class="end">{E(d.get('집에서.맺음', ''))}</div><img class="lg" src="assets/logo_brown.png">{sig()}</div>'''

FIT = '''<script>document.fonts.ready.then(()=>{document.querySelectorAll('.fit,.fit2').forEach(e=>{let p=e.parentElement;let cs=getComputedStyle(e);let w=cs.display==='inline'?p.getBoundingClientRect().right-e.getBoundingClientRect().left:e.clientWidth;let fs=parseFloat(getComputedStyle(e).fontSize);while(e.scrollWidth>w+1&&fs>20){fs-=1;e.style.fontSize=fs+'px';}if(e.classList.contains('fit2')){const lh=()=>parseFloat(getComputedStyle(e).lineHeight);while(e.getBoundingClientRect().height>lh()*2+4&&fs>20){fs-=2;e.style.fontSize=fs+'px';}}});
document.querySelectorAll('.bb').forEach(e=>{let fs=58;const L=e.textContent.length;if(L>45)fs=48;if(L>70)fs=42;if(L>100)fs=36;e.style.fontSize=fs+'px'});document.body.dataset.ok=1});</script>'''

def get_photo(src, workdir):
    """표지 사진: 로컬 파일, assets 안 파일, 또는 http 주소(내려받기). 실패하면 None."""
    if not src:
        return None
    if src.startswith('http'):
        dst = os.path.join(workdir, 'cover_src.jpg')
        r = subprocess.run(['curl', '-sSL', '-m', '60', '-o', dst, src], capture_output=True)
        return dst if r.returncode == 0 and os.path.getsize(dst) > 10000 else None
    for p in (src, os.path.join(D, 'assets', src)):
        if os.path.exists(p):
            return os.path.abspath(p)
    return None

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    src = args[0]
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(D, '..', '..', 'cards')
    text = open(src, encoding='utf-8').read()
    meta = sections(text)
    d = card_data(meta.get('카드 데이터', ''))
    code = norm(meta.get('글 코드', '')).split()[0] if meta.get('글 코드') else None
    if not code or not re.fullmatch(r'[a-z0-9_-]+', code):
        print('【글 코드】가 없거나 형식이 틀림(영문 소문자·숫자)'); sys.exit(2)
    SIG['t'] = norm(meta.get('머리 줄', '')).split('│')[0].strip()
    problems = check(meta, d, meta.get('본문', ''))
    folder = os.path.join(out, code); os.makedirs(folder, exist_ok=True)
    report = {'code': code, 'problems': problems, 'cards': []}
    if problems or '--check-only' in args:
        json.dump(report, open(os.path.join(folder, 'report.json'), 'w'), ensure_ascii=False, indent=1)
        print(json.dumps(report, ensure_ascii=False, indent=1)); sys.exit(2 if problems else 0)
    kind = meta.get('카테고리', '')
    short = meta.get('글 종류', '').startswith('짧')
    sentence = meta.get('글 종류', '').startswith('문장')
    photo = None if sentence else get_photo(d.get('표지.사진', ''), folder)
    V = lambda key: pick(code, key, 2) == 1 and '--plain' not in args
    cover = cardS0(d) if sentence else (cardC2 if V('C') else cardC)(d, photo) if photo else cardB1(d)
    cards = [('1_표지', cover, bool(photo))]
    if sentence:
        cards += [(f'{i + 1}_문장', cardS(d, f'문장{i}', i), False) for i in (1, 2, 3)]
    if sentence:
        pass
    elif not short:
        two = cardE(d) if '교육관' in kind else cardD(d) if '쓰기' in kind else (cardF2 if V('F') else cardF)(d)
        cards.append(('2_' + ('근거' if '교육관' in kind else '원고지' if '쓰기' in kind else '책정보'), two, False))
    if not sentence:
        cards.append(('6_갈림길', (cardH2 if V('H') else cardH)(d), False))
        cards.append(('3_한장틀', (cardB3b if V('B') else cardB3)(d), False))
        if not short:
            cards.append(('4_아이의말', (cardG2 if V('G') else cardG)(d), False))
        cards.append(('5_집에서', (cardA2 if V('A') else cardA)(d), False))
    theme = 0 if '--plain' in args else pick(code, 'theme', 5)
    cards = [(n, h.replace('<div class="c ', f'<div class="c th{theme} ', 1), ph) for n, h, ph in cards]
    report['theme'] = theme
    head = open(os.path.join(D, 'head.html'), encoding='utf-8').read()
    css = open(os.path.join(D, 'cards.css'), encoding='utf-8').read()
    from playwright.sync_api import sync_playwright
    from PIL import Image
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={'width': 1100, 'height': 1100})
        for name, h, is_photo in cards:
            f = os.path.join(D, '_tmp.html')
            open(f, 'w', encoding='utf-8').write(head + '<style>' + css + '</style></head><body>' + h + FIT + '</body></html>')
            pg.goto('file://' + f); pg.wait_for_function('document.body.dataset.ok==1'); pg.wait_for_timeout(200)
            if name.startswith('1_'):
                # 썸네일 검사: 블로그 앨범 목록에서는 표지가 약 4분의 1(270px)로 줄어든다. 제목 글자가 그때 17px 아래면 실패.
                fs = pg.evaluate("parseFloat(getComputedStyle(document.getElementById('ttl')).fontSize)")
                report['cover_title_px'] = fs
                if fs < 68:
                    report['problems'].append(f'표지.제목: 너무 길어 썸네일에서 안 읽힘(글자 {fs:.0f}px, 68px 이상 필요) → 더 짧게')
            png = os.path.join(folder, f'{code}_{name}.png')
            pg.locator('#k').screenshot(path=png)
            im = Image.open(png).convert('RGB')
            if is_photo:
                dst = png[:-4] + '.jpg'; im.save(dst, quality=82, optimize=True, progressive=True); os.remove(png)
            else:
                dst = png; im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(dst, optimize=True)
            report['cards'].append(os.path.basename(dst))
        b.close()
    os.remove(os.path.join(D, '_tmp.html'))
    report['cover'] = '문장 표지' if sentence else 'C(사진)' if photo else 'B(사진 없음·대체)'
    if '--preview' in args:
        pv = args[args.index('--preview') + 1]
        preview(meta, folder, report['cards'], pv)
        report['preview'] = pv
    json.dump(report, open(os.path.join(folder, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if report['problems']:
        for f in report['cards']:
            os.remove(os.path.join(folder, f))  # 검사에 걸린 카드는 남기지 않는다
        sys.exit(2)

def preview(meta, folder, files, dst):
    """결재용 미리보기 한 장: 왼쪽은 블로그 앨범 목록(표지 썸네일), 오른쪽은 휴대폰 화면 흐름.
    원고 전문이 들어가므로 공개 저장소(cards/)에 두지 않는다."""
    import pathlib
    by = {re.match(r'.+?_(\d)_', f).group(1): pathlib.Path(folder, f).resolve().as_uri() for f in files}
    body = meta.get('본문', '').replace('\\', '')
    out = []
    for para in re.split(r'\n\s*\n', body):
        p = para.strip()
        if not p:
            continue
        m = re.fullmatch(r'\[카드 (\d)\]', p)
        if m:
            out.append(f'<img class="cd" src="{by.get(m.group(1), "")}">'); continue
        if p.startswith('오늘의 질문'):
            out.append(f'<div class="qt">{E(p.split(":", 1)[-1].strip())}</div>'); continue
        if re.match(r'^\d\. ', p) and '\n' not in p:
            out.append(f'<h3>{E(p)}</h3>'); continue
        if p.startswith('────'):
            out.append('<hr>'); p = p.lstrip('─').strip()
        out.append('<p>' + '<br>'.join(E(x) for x in p.splitlines()) + '</p>')
    cover = by.get('1', '')
    head = open(os.path.join(D, 'head.html'), encoding='utf-8').read()
    css = '''body{margin:0;background:#e9e6df;font-family:"Gowun Dodum";word-break:keep-all}
.wrap{display:flex;gap:40px;padding:40px;align-items:flex-start}
.col{background:#fff;border-radius:18px;box-shadow:0 6px 24px rgba(0,0,0,.08)}
.lab{font-size:15px;color:#7a6a52;margin:0 0 10px;letter-spacing:.08em}
.grid{width:390px;padding:16px;display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid div{font-size:13px;line-height:1.4;color:#222}.grid img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;display:block;margin-bottom:6px}
.grid .ph{width:100%;aspect-ratio:1;border-radius:6px;background:#ddd8cc;margin-bottom:6px}
.phone{width:390px;padding:22px 20px 40px;font-size:16px;line-height:1.75;color:#222}
.phone .hl{font-size:13px;color:#5A6470}.phone h1{font-size:21px;line-height:1.4;margin:6px 0 18px}
.phone .cd{width:100%;display:block;margin:14px 0}.phone h3{font-size:17px;margin:30px 0 8px}
.phone .qt{margin:18px 0;padding:14px 10px;text-align:center;font-family:"Gowun Batang";font-weight:700;font-size:18px;border-top:1px solid #ccc;border-bottom:1px solid #ccc}
.phone p{margin:0 0 14px}.phone hr{border:0;border-top:1px solid #ddd;margin:26px 0 10px}'''
    t = E(meta.get('제목', '').strip())
    hl = E(meta.get('머리 줄', '').strip())
    html_ = f'''{head}<style>{css}</style></head><body><div class="wrap">
<div><div class="lab">블로그 목록(앨범형) — 표지가 이 크기로 보입니다</div><div class="col grid">
<div><img src="{cover}">{t}</div><div><div class="ph"></div>지난 글</div><div><div class="ph"></div>지난 글</div><div><div class="ph"></div>지난 글</div></div></div>
<div><div class="lab">휴대폰 화면 — 글 흐름</div><div class="col phone"><div class="hl">{hl}</div><h1>{t}</h1>{''.join(out)}</div></div>
</div><script>document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>i.onload=i.onerror=r)))).then(()=>document.body.dataset.ok=1)</script></body></html>'''
    f = os.path.join(D, '_pv.html'); open(f, 'w', encoding='utf-8').write(html_)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 960, 'height': 900}, device_scale_factor=2)
        pg.goto('file://' + f); pg.wait_for_function('document.body.dataset.ok==1'); pg.wait_for_timeout(300)
        pg.screenshot(path=dst, full_page=True); b.close()
    os.remove(f)

if __name__ == '__main__':
    main()
