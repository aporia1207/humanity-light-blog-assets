"""휴머니티 light 카드 엔진 — 원고 한 장에서 카드를 찍고, 카드 문구가 본문과 같은지 검사한다.

사용:
  python3 engine.py <원고.txt> [--out 출력폴더] [--check-only]

원고.txt 는 규칙서 v2 9번 형식(【글 코드】【글 종류】【카테고리】【본문】【카드 데이터】 …)의 일반 텍스트.
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
                '근거1.결과', '근거2.결과', '원고지.예문']
SHORT_SKIP = ['아이말.질문', '아이말.대답1', '아이말.대답2', '근거1.결과', '근거2.결과', '원고지.예문']

def check(meta, d, body):
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
    need = ['표지.제목', '한장틀.큰질문', '집에서.질문1', '집에서.질문2', '집에서.질문3', '집에서.맺음']
    if not kind_short:
        need += ['아이말.질문', '아이말.대답1', '아이말.대답2']
    for k in need:
        if not d.get(k):
            problems.append(f'{k}: 값이 비어 있음')
    cards_in_body = set(re.findall(r'\[카드 (\d)\]', body))
    want = {'1', '3', '5'} if kind_short else {'1', '2', '3', '4', '5'}
    if cards_in_body != want:
        problems.append(f'본문의 카드 자리 {sorted(cards_in_body)} ≠ 필요한 자리 {sorted(want)}')
    return problems

# ---------- 카드 HTML ----------
def bk(d):
    return d.get('표지.제목', '')

def cardC(d, photo):
    chips = [d.get('표지.칩1', ''), d.get('표지.칩2', '')]
    ch = ''.join(f'<span class="chip{" g" if i == 0 else ""}">{E(c)}</span>' for i, c in enumerate(chips) if c)
    return f'''<div class="c C" id="k"><img class="bg" src="{photo}"><div class="vg"></div><div class="gl"></div><div class="tag">{E(chips[1])}</div><img class="lg" src="assets/logo.png">
<div class="glass"><div class="chips">{ch}</div><div class="t fit2">{E(bk(d))}</div><div class="s">{E(d.get('표지.한줄', ''))}</div></div></div>'''

def cardB1(d):
    return f'''<div class="c B" id="k"><div class="k">{E(d.get('표지.칩2', ''))}</div><div class="q">{E(d.get('표지.한줄', ''))}</div><div class="rule"></div><div class="sub">{E(bk(d))}</div><img class="lg" src="assets/logo_navy.png"><div class="ft">휴머니티 light · {E(d.get('표지.칩1', ''))}</div></div>'''

def cardF(d):
    rows = [('글 · 그림', '책.글그림'), ('출판사', '책.출판사'), ('쪽수', '책.쪽수'), ('함께 읽는 학년', '책.학년'), ('주제어', '책.주제어'), ('기록', '책.기록')]
    dl = ''.join(f'<dt>{E(a)}</dt><dd>{E(d[b])}</dd>' for a, b in rows if d.get(b))
    return f'''<div class="c F" id="k"><div class="card"><div class="rl"></div><div class="hd"><span>책 한 장 정보</span><span>{E(d.get('표지.칩2', ''))}</span></div>
<div class="tt fit">{E(d.get('책.제목', bk(d)))}</div><dl>{dl}</dl><img class="stamp" src="assets/logo_brown.png"><div class="hole"></div></div></div>'''

def cardE(d):
    def box(i, lab):
        return f'''<div class="box {'a' if i == 1 else 'b'}"><span class="lab">{lab}</span><div class="n">{E(d.get(f'근거{i}.숫자', ''))}</div><div class="who">{E(d.get(f'근거{i}.대상', ''))}</div><div class="r">{E(d.get(f'근거{i}.결과', ''))}</div></div>'''
    return f'''<div class="c E" id="k"><div class="grid"></div><div class="k">전문가의 눈 · 오늘의 근거</div><div class="t">{E(d.get('한장틀.작은질문1', ''))}</div><img class="lg" src="assets/logo_navy.png">
{box(1, '연구')}{box(2, '다른 결과')}<div class="ft">연구 초록 기준 요약 · 휴머니티 light</div></div>'''

def cardD(d):
    t = d.get('원고지.예문', '')
    cells = ''.join(f'<span>{E(c) if c != " " else ""}</span>' for c in t)
    pad = (15 - len(t) % 15) % 15
    cells += '<span></span>' * pad + '<span style="color:#c0472b">왜</span><span style="color:#c0472b">?</span>' + '<span></span>' * 28
    return f'''<div class="c D" id="k"><div class="k">쓰기 이야기</div><div class="t">{E(bk(d))}</div><img class="lg" src="assets/logo_navy.png">
<div class="grid">{cells}</div><div class="cap">원고에 예로 든 글이에요. 끝에 <b>“왜 그렇게 느꼈는지”</b> 한 문장을 붙이면 한 문단이 됩니다.</div><div class="ft">휴머니티 light · {E(d.get('표지.칩1', ''))}</div></div>'''

def cardB3(d):
    band = d.get('한장틀.띠') or '이 이야기는 무슨 질문에 대한 답일까?'
    return f'''<div class="c B" id="k"><div class="k">휴머니티의 한 장 틀 · {E(band)}</div><div class="q" style="font-size:64px;top:200px">{E(d.get('한장틀.큰질문', ''))}</div><div class="rule" style="top:420px"></div>
<div class="bl"><p><b>작은 질문</b>{E(d.get('한장틀.작은질문1', ''))}</p><p><b>작은 질문</b>{E(d.get('한장틀.작은질문2', ''))}</p><p style="margin-top:34px"><b>틀릴 수 있는 경우</b><br>{E(d.get('한장틀.틀릴수있는경우', ''))}</p></div>
<img class="lg" src="assets/logo_navy.png"><div class="ft">{E(bk(d))}</div></div>'''

def cardG(d):
    q = lambda s: E(s.strip('“”"'))
    return f'''<div class="c G" id="k"><div class="k">아이의 말로 보기 · {E(bk(d))}</div><div class="t">{E(d.get('아이말.질문', ''))}</div>
<div class="wrap"><div class="bb b1"><small>그 학년다운 대답</small>“{q(d.get('아이말.대답1', ''))}”</div><div class="bb b2"><small>한 걸음 나아간 대답</small>“{q(d.get('아이말.대답2', ''))}”</div></div>
<div class="ft">예로 들어 본 대답이에요 · 휴머니티 light</div><img class="lg" src="assets/logo_navy.png"></div>'''

def cardA(d):
    return f'''<div class="c A" id="k"><div class="lines"></div><div class="mg"></div><div class="holes"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="tape"></div>
<div class="ln pen lab fit" style="top:80px">집에서 해 보기 · {E(bk(d))}</div>
<div class="ln pen big" style="top:160px;height:160px">오늘 저녁,&nbsp;<span class="mark">세&nbsp;가지만</span>&nbsp;물어봐&nbsp;주세요</div>
<div class="ln pen q" style="top:400px"><span class="no">하나</span><span class="fit">{E(d.get('집에서.질문1', ''))}</span></div>
<div class="ln pen q" style="top:480px"><span class="no">둘</span><span class="fit">{E(d.get('집에서.질문2', ''))}</span></div>
<div class="ln pen q" style="top:560px"><span class="no">셋</span><span class="fit">{E(d.get('집에서.질문3', ''))}</span></div>
<div class="ln pen q fit" style="top:720px;color:#b8572f">→ {E(d.get('집에서.맺음', ''))}</div><img class="lg" src="assets/logo.png"></div>'''

FIT = '''<script>document.fonts.ready.then(()=>{document.querySelectorAll('.fit,.fit2').forEach(e=>{let p=e.parentElement;let w=p.getBoundingClientRect().right-e.getBoundingClientRect().left;let fs=parseFloat(getComputedStyle(e).fontSize);while(e.scrollWidth>w+1&&fs>20){fs-=1;e.style.fontSize=fs+'px';}});
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
    problems = check(meta, d, meta.get('본문', ''))
    folder = os.path.join(out, code); os.makedirs(folder, exist_ok=True)
    report = {'code': code, 'problems': problems, 'cards': []}
    if problems or '--check-only' in args:
        json.dump(report, open(os.path.join(folder, 'report.json'), 'w'), ensure_ascii=False, indent=1)
        print(json.dumps(report, ensure_ascii=False, indent=1)); sys.exit(2 if problems else 0)
    kind = meta.get('카테고리', '')
    short = meta.get('글 종류', '').startswith('짧')
    photo = get_photo(d.get('표지.사진', ''), folder)
    cards = [('1_표지', cardC(d, photo) if photo else cardB1(d), bool(photo))]
    if not short:
        two = cardE(d) if '교육관' in kind else cardD(d) if '쓰기' in kind else cardF(d)
        cards.append(('2_' + ('근거' if '교육관' in kind else '원고지' if '쓰기' in kind else '책정보'), two, False))
    cards.append(('3_한장틀', cardB3(d), False))
    if not short:
        cards.append(('4_아이의말', cardG(d), False))
    cards.append(('5_집에서', cardA(d), False))
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
    report['cover'] = 'C(사진)' if photo else 'B(사진 없음·대체)'
    json.dump(report, open(os.path.join(folder, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
