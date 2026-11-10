"""Подбор картинки к сцене по смыслу (п.63): к тексту каждой сцены — 3 кандидата из медиатеки музея.

Медиатека — все картинки из src/content/dni-shablon/<музей>/*.yaml rc-site (обложка, кадры фактов, figures)
с их подписями: alt, podpis, podpis_chto/gde/kogda. Поиск — BM25 по подписям с лёгкой обрезкой русских
окончаний; моделей и платных API нет. Сцены — segments[].show (или say) из days/<id>.json ролика (--cfg),
без ролика — факты из утверждённого текста src/data/utverzhdeno/<музей>/<ММ-ДД>.json.
Только предложение в out/podbor/<музей>-<ММ-ДД>.json: сценарии, кадры и ролики не меняются.
Кандидат, совпавший по картинке (dHash) с кадром ролика, помечен «uzhe_v_rolike».

  RC_SITE=~/rc-site python3 scripts/podbor.py izobreteniya 02-02 [--cfg days/02feb.json] [--tolko-den] [-k 3]
"""
import argparse, json, math, os, pathlib, re
from collections import Counter
import yaml
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
KARTINKA = re.compile(r"\.(jpe?g|png|webp)$", re.I)
POLYA = ("alt", "podpis", "podpis_chto", "podpis_gde", "podpis_kogda", "podpis_ru")
# Окончания по убыванию длины: «единорогами» и «единорог» дают одну основу; «ов», «ев» не режем — это фамилии.
OKONCHANIYA = sorted("""ами ями ого его ому ему ыми ими ой ей ий ый ая яя ое ее ые ие ым им ам ям ах ях ом ем
ую юю ию ья ье а я о е ы и у ю ь й""".split(), key=len, reverse=True)
STOP = set("""это как что для его она они был была были было все всё так там тут уже ещё еще или
при над под без про они него неё нее них сам сама само чем того тот эта этот эти""".split())
# Основы, общие для всех дней музея: по ним картинку не отличить.
STOP_OSNOVY = set("год года году годы лет русск российск перв одна один одно получ сдела стал день сайт точк целик смотр".split())


def slova(t):
    out = []
    for w in re.findall(r"[a-zа-яё0-9]+", (t or "").lower().replace("ё", "е")):
        if len(w) < 3 or w in STOP:
            continue
        if not w.isdigit():
            for o in OKONCHANIYA:
                if w.endswith(o) and len(w) - len(o) >= 4:
                    w = w[: -len(o)]
                    break
        if w not in STOP_OSNOVY:
            out.append(w)
    return out


def mediateka(site, muzei):
    """{src: {"tekst": подписи, "den": ММ-ДД}} — каждая картинка один раз, подписи со всех мест слиты."""
    lib = {}

    def obhod(x, den):
        if isinstance(x, dict):
            src = x.get("src")
            if isinstance(src, str) and src.startswith("/muzei/") and KARTINKA.search(src):
                z = lib.setdefault(src, {"tekst": [], "den": den})
                z["tekst"] += [str(x[p]) for p in POLYA if x.get(p) and str(x[p]) not in z["tekst"]]
            for v in x.values():
                obhod(v, den)
        elif isinstance(x, list):
            for v in x:
                obhod(v, den)

    for f in sorted((site / "src/content/dni-shablon" / muzei).glob("*.yaml")):
        obhod(yaml.safe_load(f.read_text()), f.stem)
    return {k: {"tekst": " · ".join(v["tekst"]), "den": v["den"]} for k, v in lib.items() if v["tekst"]}


def sceny(site, muzei, key, cfg):
    if cfg:
        c = json.loads(pathlib.Path(cfg).read_text())
        # show — с цифрами годов, say — словами для голоса; сцены без кадра (титры, призыв) не подбираются.
        return [{"id": s["id"], "tekst": s.get("show") or s["say"], "seychas": c["images"][s["image"]]["src"]}
                for s in c["segments"] if s.get("image") in c["images"]], c["images"]
    u = json.loads((site / "src/data/utverzhdeno" / muzei / f"{key}.json").read_text())
    po = {f["n"]: f for f in u["fakty"]}
    return [{"id": f"fakt-{n}", "tekst": (po[n]["zagolovok"] + " " + po[n].get("podrobnee", "")).split("Источник:")[0].strip()}
            for n in u.get("poryadok") or po if n in po], {}


def dhash(path):
    g = Image.open(path).convert("L").resize((9, 8))
    p = list(g.tobytes())
    return sum(1 << i for i in range(64) if p[(i // 8) * 9 + i % 8] > p[(i // 8) * 9 + i % 8 + 1])


class BM25:
    """Okapi BM25 (k1=1.2, b=0.75) — как BM25Similarity в Lucene."""

    def __init__(self, docs, k1=1.2, b=0.75):
        self.docs = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / max(len(docs), 1)
        df = Counter(w for d in self.docs for w in d)
        n = len(docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def ball(self, q, i):
        d, L, s, sovp = self.docs[i], self.len[i], 0.0, []
        for w in set(q):
            if w in d:
                f = d[w]
                s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * L / self.avg))
                sovp.append(w)
        return s, sovp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("muzei")
    ap.add_argument("key", help="ММ-ДД")
    ap.add_argument("--cfg", help="days/<id>.json ролика; без него — факты утверждённого текста")
    ap.add_argument("--site", default=os.environ.get("RC_SITE", str(ROOT.parent / "rc-site")))
    ap.add_argument("--tolko-den", action="store_true", help="только картинки этого дня")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--ves-dnya", type=float, default=2.0, help="множитель балла картинкам своего дня")
    ap.add_argument("--out", default=str(ROOT / "out/podbor"))
    a = ap.parse_args()
    site = pathlib.Path(a.site).expanduser()

    lib = mediateka(site, a.muzei)
    if a.tolko_den:
        lib = {k: v for k, v in lib.items() if v["den"] == a.key}
    srcs = list(lib)
    bm = BM25([slova(lib[s]["tekst"]) for s in srcs])
    sc, images = sceny(site, a.muzei, a.key, a.cfg)
    v_rolike = {}
    for k, im in images.items():
        p = ROOT / im["src"]
        if p.exists():
            v_rolike[dhash(p)] = k

    def tot_zhe(src):
        p = site / "public" / src.lstrip("/")
        if not v_rolike or not p.exists():
            return None
        h = dhash(p)
        return next((k for hh, k in v_rolike.items() if bin(h ^ hh).count("1") <= 6), None)

    rez = []
    for s in sc:
        q = slova(s["tekst"])
        bally = []
        for i, src in enumerate(srcs):
            b, sovp = bm.ball(q, i)
            bally.append((b * (a.ves_dnya if lib[src]["den"] == a.key else 1), sovp, src))
        bally.sort(key=lambda x: -x[0])
        kand = []
        for b, sovp, src in bally[: a.k]:
            if b <= 0:
                break
            kand.append({"src": src, "den": lib[src]["den"], "ball": round(b, 2), "sovpali": sovp,
                         "podpis": lib[src]["tekst"][:200], **({"uzhe_v_rolike": t} if (t := tot_zhe(src)) else {})})
        rez.append({**s, "kandidaty": kand})
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{a.muzei}-{a.key}.json"
    f.write_text(json.dumps({"muzei": a.muzei, "key": a.key, "mediateka": len(srcs),
                             "pravilo": f"BM25 по подписям картинок (alt, podpis*) из yaml сайта, свой день x{a.ves_dnya}; только предложение, выбор не меняется",
                             "sceny": rez}, ensure_ascii=False, indent=1))
    print(f"{f}: {len(rez)} сцен, медиатека {len(srcs)} картинок")
    for s in rez:
        print(f"  {s['id']}: {s['tekst'][:70]}")
        if s.get("seychas"):
            print(f"      сейчас: {s['seychas']}")
        for k in s["kandidaty"]:
            print(f"      {k['ball']:5.2f} {k['src']}{'  [уже в ролике: ' + k['uzhe_v_rolike'] + ']' if 'uzhe_v_rolike' in k else ''}  ({', '.join(k['sovpali'][:5])})")
        if not s["kandidaty"]:
            print("      нет совпадений по подписям")


if __name__ == "__main__":
    main()
