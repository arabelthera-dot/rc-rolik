"""Ролик и аудиогид дня — машиной при выходе дня (r685, Р685). Запускает avto.yml по сигналу rc-site и раз в 5 мин (Р763).
Что делает (stdout — команды gh, по одной на строку; их исполняет avto.yml):
1) день сайта (rc-site main, src/content/dni-shablon/<музей>/ММ-ДД.yaml), изменённый за окно, с audioguide.transcript
   и audioSrc — audiogid.yml; ключ = sha1 текста гида. Прогон с таким именем уже был — второй раз не запускается.
2) сценарий ролика days/<id>.json (id: изобретения 02feb, НС ns02feb) с полем sajt — render.yml; ключ = sha1 файла.
   У НС сценарий собирает в облаке scripts/scenarij.mjs (r699), поэтому ключ — sha1 того, из чего он собран:
   карточка src/content/days/ne-sdayutsya/ММ-ДД.json + yaml страницы + копия src/data/utverzhdeno/ne-sdayutsya/ММ-ДД.json (если есть).
   Источник — день сайта из п.1 (и для НС — изменённые за окно карточка или копия утверждённого) или свой days/*.json.
3) упавший прогон audiogid/render с ключом: попытка 1–2 — gh run rerun --failed (пауза ≥ 25 мин — PAUZA);
   после 3-й — карточка с первой строкой ошибки (печатает строку KARTOCHKA <run> <текст>).
4) открытые заявки дней rc-site (r763, Р763): заявка из этого же репо меняет yaml страницы дня — гид и ролик
   по ветке заявки (audiogid.yml vetka_sajta=<ветка>, render.yml vetka_sajta=<ветка> для НС) сразу, до слияния.
   Ключ тот же, что посчитается на main после слияния, — второй раз после слияния не запускается. Ролику НС свой
   days/<id>.json не нужен: сценарий собирает scenarij.mjs из ветки. Выключатель: ZAYAVKI=0 (avto.yml — MEDIA_AVTO_ZAYAVKI).
Запуск: python scripts/avto.py <папка rc-site> <окно, напр. '3 days ago'> [<музей/ММ-ДД> …]"""
import hashlib, json, os, pathlib, re, subprocess, sys, time
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MAKS = 4  # не больше 4 новых прогонов каждого вида за опрос
MAKS_DNEJ = 2  # заявка дня меняет 1–2 страницы; больше — правка многих дней, ролики по ней не запускаются (r763)
PAUZA = 25 * 60  # перезапуск — не раньше чем через 25 мин после отказа
REPO = "arabelthera-dot/rc-rolik"
SITE = "arabelthera-dot/rc-site"
DEN = r"src/content/dni-shablon/([a-z-]+/\d\d-\d\d)\.yaml"

def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout

def runs(wf):
    return json.loads(sh("gh", "run", "list", "-R", REPO, "-w", wf, "-L", "200", "--json",
                         "databaseId,displayTitle,status,conclusion,attempt,updatedAt"))

def kluch(b):
    return hashlib.sha1(b).hexdigest()[:10]

# файл rc-site: ref None — из папки (main), иначе из коммита ветки заявки (git show; blob докачивается сам)
def chitalka(site, ref=None):
    def chit(rel):
        if ref is None:
            p = site / rel
            return p.read_bytes() if p.is_file() else None
        r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=site, capture_output=True)
        return r.stdout if r.returncode == 0 else None
    return chit

# ключ ролика НС: изменилось любое из того, из чего scenarij.mjs собирает сценарий, — новый прогон
def kluch_ns(chit, i):
    key = f"{MES.index(i[4:]) + 1:02d}-{i[2:4]}"
    chasti = [f"src/content/days/ne-sdayutsya/{key}.json",
              f"src/content/dni-shablon/ne-sdayutsya/{key}.yaml",
              f"src/data/utverzhdeno/ne-sdayutsya/{key}.json"]
    return kluch(b"".join(rel.encode() + b"\0" + b for rel in chasti if (b := chit(rel)) is not None))

# открытые заявки дней rc-site из этого же репо: [(день, ветка, читалка)] — ветка приносится в refs/zayavki/<N>
def zayavki(site):
    out = []
    for z in json.loads(sh("gh", "pr", "list", "-R", SITE, "--state", "open", "-L", "100", "--json",
                           "number,headRefName,isCrossRepository,isDraft,files")):
        dni = sorted({m.group(1) for f in z["files"] if (m := re.fullmatch(DEN, f["path"]))})
        if z["isCrossRepository"] or z["isDraft"] or not dni:
            continue
        if len(dni) > MAKS_DNEJ:
            print(f"# заявка {z['number']}: дней {len(dni)} — не заявка дня, пропуск", file=sys.stderr); continue
        ref = f"refs/zayavki/{z['number']}"
        try:
            sh("git", "fetch", "-q", "origin", f"+refs/pull/{z['number']}/head:{ref}", cwd=site)
        except subprocess.CalledProcessError:
            print(f"# заявка {z['number']}: ветку не забрать", file=sys.stderr); continue
        out += [(d, z["headRefName"], chitalka(site, ref)) for d in dni]
    return out

def rid(muzei, key):
    mm, dd = key.split("-")
    return ("ns" if muzei == "ne-sdayutsya" else "") + dd + MES[int(mm) - 1]

def main(site, okno, dni):
    site = pathlib.Path(site)
    dni_rukami = bool(dni)
    if not dni:
        f = sh("git", "log", f"--since={okno}", "--name-only", "--format=", "--", "src/content/dni-shablon/",
               "src/content/days/ne-sdayutsya/", "src/data/utverzhdeno/ne-sdayutsya/", cwd=site)
        dni = sorted({m.group(1) for m in re.finditer(DEN, f)}
                     | {f"ne-sdayutsya/{m.group(1)}" for m in re.finditer(r"src/(?:content/days|data/utverzhdeno)/ne-sdayutsya/(\d\d-\d\d)\.json", f)})
        f = sh("git", "log", f"--since={okno}", "--name-only", "--format=", "--", "days/", cwd=ROOT)
        svoi = sorted({m.group(1) for m in re.finditer(r"days/([a-z0-9]+)\.json", f)})
    else:
        svoi = []
    glavnaya = chitalka(site)
    istochniki = {d: ("main", glavnaya) for d in dni}
    if not dni_rukami and os.environ.get("ZAYAVKI", "1") != "0":
        istochniki |= {d: (vetka, chit) for d, vetka, chit in zayavki(site)}  # заявка новее main
    ag, rn = runs("audiogid.yml"), runs("render.yml")
    imena = {r["displayTitle"].strip() for r in ag + rn}
    novye_ag, novye_rn = [], []
    ids = {i: ("main", glavnaya) for i in svoi}
    for d, (vetka, chit) in istochniki.items():
        put = f"src/content/dni-shablon/{d}.yaml"
        b = chit(put)
        if b is None:
            print(f"# {d}: нет на {vetka}", file=sys.stderr); continue
        y = yaml.safe_load(b.decode())
        ids[rid(*d.split("/"))] = (vetka, chit)
        g = y.get("audioguide") or {}
        if not (g.get("transcript") and g.get("audioSrc")):
            print(f"# {d} ({vetka}): нет audioguide.transcript или audioSrc — гида нет", file=sys.stderr); continue
        k = kluch(json.dumps(g["transcript"], ensure_ascii=False).encode())
        if f"audiogid {put} {k}" not in imena:
            imena.add(f"audiogid {put} {k}")
            novye_ag.append(f"gh workflow run audiogid.yml -R {REPO} -f put={put} -f vetka_sajta={vetka} -f klyuch={k}")
    for i, (vetka, chit) in ids.items():
        p = ROOT / "days" / f"{i}.json"
        ns = i.startswith("ns")
        # НС из заявки: сценарий соберёт scenarij.mjs из ветки, своего days/<id>.json может ещё не быть (r763)
        sj = json.loads(p.read_text()).get("sajt") if p.is_file() else ({} if ns and vetka != "main" else None)
        if sj is None:
            print(f"# {i}: нет сценария days/{i}.json — ролика нет", file=sys.stderr); continue
        if not sj and not (ns and vetka != "main"):
            print(f"# {i}: в days/{i}.json нет sajt — ролик на сайт не идёт", file=sys.stderr); continue
        z, k = f"{i}:{sj.get('variant', 'A')}", kluch_ns(chit, i) if ns else kluch(p.read_bytes())
        if f"render {z} {k}" not in imena:
            imena.add(f"render {z} {k}")
            v = f" -f vetka_sajta={vetka}" if ns and vetka != "main" else ""
            novye_rn.append(f"gh workflow run render.yml -R {REPO} -f zadacha={z} -f klyuch={k}{v}")
    for c in novye_ag[:MAKS] + novye_rn[:MAKS]:
        print(c)
    # перезапуск упавших прогонов avto (имя с ключом: три слова)
    for r in ag + rn:
        if r["status"] != "completed" or r["conclusion"] != "failure" or len(r["displayTitle"].split()) < 3:
            continue
        t = time.mktime(time.strptime(r["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
        if time.time() - t > 2 * 86400:
            continue
        if r["attempt"] < 3:
            if time.time() - t >= PAUZA:
                print(f"gh run rerun {r['databaseId']} --failed -R {REPO}")
        else:
            print(f"KARTOCHKA {r['databaseId']} {r['displayTitle']}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
