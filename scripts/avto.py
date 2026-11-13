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
Запуск: python scripts/avto.py <папка rc-site> <окно, напр. '3 days ago'> [<музей/ММ-ДД> …]"""
import hashlib, json, pathlib, re, subprocess, sys, time
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MAKS = 4  # не больше 4 новых прогонов каждого вида за опрос
PAUZA = 25 * 60  # перезапуск — не раньше чем через 25 мин после отказа
REPO = "arabelthera-dot/rc-rolik"

def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout

def runs(wf):
    return json.loads(sh("gh", "run", "list", "-R", REPO, "-w", wf, "-L", "200", "--json",
                         "databaseId,displayTitle,status,conclusion,attempt,updatedAt"))

def kluch(b):
    return hashlib.sha1(b).hexdigest()[:10]

# ключ ролика НС: изменилось любое из того, из чего scenarij.mjs собирает сценарий, — новый прогон
def kluch_ns(site, i):
    key = f"{MES.index(i[4:]) + 1:02d}-{i[2:4]}"
    chasti = [site / "src/content/days/ne-sdayutsya" / f"{key}.json",
              site / "src/content/dni-shablon/ne-sdayutsya" / f"{key}.yaml",
              site / "src/data/utverzhdeno/ne-sdayutsya" / f"{key}.json"]
    return kluch(b"".join(str(p.relative_to(site)).encode() + b"\0" + p.read_bytes() for p in chasti if p.is_file()))

def rid(muzei, key):
    mm, dd = key.split("-")
    return ("ns" if muzei == "ne-sdayutsya" else "") + dd + MES[int(mm) - 1]

def main(site, okno, dni):
    site = pathlib.Path(site)
    if not dni:
        f = sh("git", "log", f"--since={okno}", "--name-only", "--format=", "--", "src/content/dni-shablon/",
               "src/content/days/ne-sdayutsya/", "src/data/utverzhdeno/ne-sdayutsya/", cwd=site)
        dni = sorted({m.group(1) for m in re.finditer(r"src/content/dni-shablon/([a-z-]+/\d\d-\d\d)\.yaml", f)}
                     | {f"ne-sdayutsya/{m.group(1)}" for m in re.finditer(r"src/(?:content/days|data/utverzhdeno)/ne-sdayutsya/(\d\d-\d\d)\.json", f)})
        f = sh("git", "log", f"--since={okno}", "--name-only", "--format=", "--", "days/", cwd=ROOT)
        svoi = sorted({m.group(1) for m in re.finditer(r"days/([a-z0-9]+)\.json", f)})
    else:
        svoi = []
    ag, rn = runs("audiogid.yml"), runs("render.yml")
    imena = {r["displayTitle"].strip() for r in ag + rn}
    novye_ag, novye_rn = [], []
    ids = list(svoi)
    for d in dni:
        p = site / "src/content/dni-shablon" / f"{d}.yaml"
        if not p.is_file():
            print(f"# {d}: нет на main", file=sys.stderr); continue
        y = yaml.safe_load(p.read_text())
        ids.append(rid(*d.split("/")))
        g = y.get("audioguide") or {}
        if not (g.get("transcript") and g.get("audioSrc")):
            print(f"# {d}: нет audioguide.transcript или audioSrc — гида нет", file=sys.stderr); continue
        k = kluch(json.dumps(g["transcript"], ensure_ascii=False).encode())
        put = f"src/content/dni-shablon/{d}.yaml"
        if f"audiogid {put} {k}" not in imena:
            novye_ag.append(f"gh workflow run audiogid.yml -R {REPO} -f put={put} -f vetka_sajta=main -f klyuch={k}")
    for i in dict.fromkeys(ids):
        p = ROOT / "days" / f"{i}.json"
        if not p.is_file():
            print(f"# {i}: нет сценария days/{i}.json — ролика нет", file=sys.stderr); continue
        sj = json.loads(p.read_text()).get("sajt")
        if not sj:
            print(f"# {i}: в days/{i}.json нет sajt — ролик на сайт не идёт", file=sys.stderr); continue
        z, k = f"{i}:{sj.get('variant', 'A')}", kluch_ns(site, i) if i.startswith("ns") else kluch(p.read_bytes())
        if f"render {z} {k}" not in imena:
            novye_rn.append(f"gh workflow run render.yml -R {REPO} -f zadacha={z} -f klyuch={k}")
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
