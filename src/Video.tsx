import React from 'react';
import {
  AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, continueRender, delayRender, interpolate,
  random, staticFile, useCurrentFrame, useVideoConfig, Easing,
} from 'remotion';
import {DaySeg, ImgMeta, Props, TSeg, Word} from './types';
import LAYOUT from './layout.json';

const AMBER = '#f2b84b';
const INK = '#0c0b09';
const XF = 9; // кадров на перекрёстный переход

// ---------- шрифты ----------
let fontsPromise: Promise<void> | null = null;
const useFonts = () => {
  const [h] = React.useState(() => delayRender('fonts'));
  React.useEffect(() => {
    if (!fontsPromise) {
      const f1 = new FontFace('Inter', `url(${staticFile('fonts/Inter.ttf')})`, {weight: '100 900'});
      const f2 = new FontFace('Playfair', `url(${staticFile('fonts/PlayfairDisplay.ttf')})`, {weight: '400 900'});
      fontsPromise = Promise.all([f1.load(), f2.load()]).then((fs) => fs.forEach((f) => document.fonts.add(f)));
    }
    fontsPromise.then(() => continueRender(h));
  }, [h]);
};

const ease = Easing.bezier(0.33, 0, 0.2, 1);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// время (с) произнесения первого слова, начинающегося с key
const wordTime = (seg: TSeg, key: string, fallback = 0) => {
  const w = seg.words.find((x) => x.w.toLowerCase().replace(/[«»"(),.:—]/g, '').startsWith(key.toLowerCase()));
  return w ? w.t : fallback;
};

// ---------- 2.5D: фон + передний план с разной скоростью ----------
const Layered: React.FC<{
  day: string; k: string; meta: ImgMeta; W: number; H: number; p: number; mode: 'zoom' | 'pan'; dim?: number; video?: string;
}> = ({day, k, meta, W, H, p, mode, dim = 0, video}) => {
  const m = meta[k] || {w: 1920, h: 1080, fg: false};
  const cover = Math.max(W / m.w, H / m.h);
  const e = ease(p);
  const sBg = cover * (mode === 'zoom' ? 1.06 + 0.10 * e : 1.04 + 0.03 * e);
  const sFg = cover * (mode === 'zoom' ? 1.06 + 0.13 * e : 1.04 + 0.06 * e);
  const spanBg = Math.max(0, m.w * sBg - W) / 2;
  const spanFg = Math.max(0, m.w * sFg - W) / 2;
  const dxBg = mode === 'pan' ? interpolate(e, [0, 1], [spanBg * 0.85, -spanBg * 0.85]) : -18 * e;
  const dxFg = mode === 'pan' ? interpolate(e, [0, 1], [spanFg * 0.95, -spanFg * 0.95]) : -36 * e;
  const box = (s: number, dx: number, dy: number): React.CSSProperties => ({
    position: 'absolute', width: m.w * s, height: m.h * s,
    left: (W - m.w * s) / 2 + dx, top: (H - m.h * s) / 2 + dy, maxWidth: 'none',
  });
  if (video) {
    return (
      <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
        <OffthreadVideo src={staticFile(`days/${day}/${video}`)} muted style={box(sBg, dxBg, 0)} />
        <AbsoluteFill style={{background: `rgba(0,0,0,${dim})`}} />
      </div>
    );
  }
  return (
    <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
      <Img src={staticFile(`days/${day}/${k}-bg.jpg`)} style={box(sBg, dxBg, 6 * e)} />
      {m.fg && <Img src={staticFile(`days/${day}/${k}-fg.png`)} style={box(sFg, dxFg, -10 * e)} />}
      <AbsoluteFill style={{background: `rgba(0,0,0,${dim})`}} />
    </div>
  );
};

// ---------- частицы: пыль и дым ----------
const Particles: React.FC<{kind: 'dust' | 'smoke' | 'embers'; n: number; W: number; H: number; seed: string}> = ({kind, n, W, H, seed}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{pointerEvents: 'none', overflow: 'hidden'}}>
      {Array.from({length: n}).map((_, i) => {
        const r = (s: string) => random(`${seed}-${kind}-${i}-${s}`);
        if (kind === 'smoke') {
          const size = (0.25 + 0.35 * r('s')) * Math.max(W, H);
          const life = 240 + 200 * r('l');
          const t = ((f + r('o') * life) % life) / life;
          const x = r('x') * W + Math.sin(t * 3 + i) * 60 + t * 120;
          const y = H * (0.75 - 0.6 * t) + r('y') * 0.2 * H;
          const op = Math.sin(Math.PI * t) * (0.10 + 0.08 * r('a'));
          return <div key={i} style={{position: 'absolute', left: x - size / 2, top: y - size / 2, width: size, height: size,
            borderRadius: '50%', background: 'radial-gradient(circle, rgba(215,205,190,1) 0%, rgba(215,205,190,0) 65%)', opacity: op}} />;
        }
        if (kind === 'embers') {
          const life = 70 + 60 * r('l');
          const t = ((f + r('o') * life) % life) / life;
          const x = r('x') * W + Math.sin(t * 6 + i) * 30;
          const y = H * (1.0 - 0.7 * t * (0.6 + r('v')));
          const s = 3 + 5 * r('s');
          return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: '50%',
            background: '#ffb347', boxShadow: '0 0 12px 4px rgba(255,140,40,.7)', opacity: Math.sin(Math.PI * t) * 0.9}} />;
        }
        const life = 260 + 200 * r('l');
        const t = ((f + r('o') * life) % life) / life;
        const x = (r('x') * W + t * (80 + 160 * r('v'))) % W;
        const y = r('y') * H + Math.sin(t * 6.28 + i) * 25 - t * 40;
        const s = 2 + 4 * r('s');
        return <div key={i} style={{position: 'absolute', left: x, top: y, width: s, height: s, borderRadius: '50%',
          background: 'rgba(240,225,200,1)', filter: s > 4.5 ? 'blur(1.5px)' : undefined, opacity: Math.sin(Math.PI * t) * (0.25 + 0.4 * r('a'))}} />;
      })}
    </AbsoluteFill>
  );
};

// ---------- анимированные схемы ----------
const PipeSweep: React.FC<{W: number; H: number; y: number}> = ({W, H, y}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const draw = interpolate(f, [0.2 * fps, 2.2 * fps], [0, 1], {...clamp, easing: ease});
  const L = W * 1.05;
  const d = `M ${-0.02 * W} ${y} C ${0.3 * W} ${y - 0.03 * H}, ${0.6 * W} ${y + 0.03 * H}, ${1.02 * W} ${y - 0.01 * H}`;
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      <defs><filter id="glow"><feGaussianBlur stdDeviation="6" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
      <path d={d} stroke="rgba(0,0,0,.55)" strokeWidth={W * 0.016} fill="none" strokeDasharray={L} strokeDashoffset={L * (1 - draw)} strokeLinecap="round" />
      <path d={d} stroke={AMBER} strokeWidth={W * 0.006} fill="none" filter="url(#glow)" strokeDasharray={L} strokeDashoffset={L * (1 - draw)} strokeLinecap="round" />
      <path d={d} stroke="#fff6dd" strokeWidth={W * 0.0025} fill="none" strokeDasharray={`${W * 0.02} ${W * 0.03}`} strokeDashoffset={-f * 9} opacity={draw > 0.98 ? 0.9 : 0} />
    </svg>
  );
};

const Formulas: React.FC<{W: number; H: number; seg: TSeg; t0: number; labels: string[]}> = ({W, H, seg, t0, labels}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tNow = t0 + f / fps;
  const on = (key: string, fb: number) => interpolate(tNow, [wordTime(seg, key, fb) - 0.1, wordTime(seg, key, fb) + 0.5], [0, 1], clamp);
  const a = on('диаметр', seg.start + 3), b = on('давлен', seg.start + 4), c = on('вязк', seg.start + 5);
  const base = interpolate(f, [5, 40], [0, 1], {...clamp, easing: ease});
  const s = Math.min(W, H * 1.4) / 900;
  const cx = W * 0.3, cy = H * 0.42, R = 120 * s;
  const pipeX0 = cx + R * 0.2, pipeX1 = W * 0.94, py = cy;
  const lineLen = pipeX1 - pipeX0;
  const lab: React.CSSProperties = {fontFamily: 'Inter', fontWeight: 700, fontSize: 34 * s, fill: AMBER};
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      <g stroke="rgba(235,225,205,.9)" strokeWidth={3 * s} fill="none">
        {/* труба вдоль */}
        <path d={`M ${pipeX0} ${py - R * 0.55} H ${pipeX1} M ${pipeX0} ${py + R * 0.55} H ${pipeX1}`} strokeDasharray={lineLen} strokeDashoffset={lineLen * (1 - base)} />
        {/* сечение */}
        <circle cx={cx} cy={cy} r={R} strokeDasharray={2 * Math.PI * R} strokeDashoffset={2 * Math.PI * R * (1 - base)} />
      </g>
      {/* диаметр */}
      <g opacity={a} stroke={AMBER} strokeWidth={3 * s}>
        <line x1={cx - R} y1={cy} x2={cx - R + 2 * R * a} y2={cy} />
        <polygon points={`${cx - R},${cy} ${cx - R + 16 * s},${cy - 8 * s} ${cx - R + 16 * s},${cy + 8 * s}`} fill={AMBER} />
        <text x={cx} y={cy + R + 52 * s} textAnchor="middle" style={lab} stroke="none">d — диаметр</text>
      </g>
      {/* давление: стрелки в трубе */}
      <g opacity={b} fill={AMBER}>
        {[0, 1, 2].map((i) => {
          const x = pipeX0 + 60 * s + ((i * 140 * s + f * 6 * s) % (lineLen - 120 * s));
          return <polygon key={i} points={`${x},${py - 22 * s} ${x + 40 * s},${py} ${x},${py + 22 * s}`} />;
        })}
        <text x={(pipeX0 + pipeX1) / 2} y={py - R * 0.55 - 26 * s} textAnchor="middle" style={lab}>P — давление</text>
      </g>
      {/* вязкость: волны */}
      <g opacity={c} stroke="rgba(242,184,75,.8)" strokeWidth={2.5 * s} fill="none">
        {[-0.28, 0.28].map((k, i) => (
          <path key={i} d={Array.from({length: 40}).map((_, j) => {
            const x = pipeX0 + 20 * s + (j / 39) * (lineLen - 40 * s);
            const y = py + k * R + Math.sin(j * 0.8 - f * 0.25) * 6 * s;
            return `${j ? 'L' : 'M'} ${x} ${y}`;
          }).join(' ')} />
        ))}
        <text x={(pipeX0 + pipeX1) / 2} y={py + R * 0.55 + 52 * s} textAnchor="middle" style={lab} stroke="none">ν — вязкость нефти</text>
      </g>
    </svg>
  );
};

const PipelineMap: React.FC<{W: number; H: number; seg: TSeg; t0: number; area: [number, number, number, number]; labels: any}> = ({W, H, seg, t0, area, labels}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tNow = t0 + f / fps;
  const [ax, ay, aw, ah] = area;
  const s = aw / 1100;
  const P0 = {x: ax + aw * 0.1, y: ay + ah * 0.32}, P2 = {x: ax + aw * 0.9, y: ay + ah * 0.62}, P1 = {x: ax + aw * 0.5, y: ay + ah * 0.05};
  const q = (t: number) => ({x: (1 - t) ** 2 * P0.x + 2 * (1 - t) * t * P1.x + t * t * P2.x, y: (1 - t) ** 2 * P0.y + 2 * (1 - t) * t * P1.y + t * t * P2.y});
  const tA = wordTime(seg, labels.from_key, seg.start + 5);
  const tB = wordTime(seg, labels.to_key, seg.start + 7);
  const draw = interpolate(tNow, [tA, tB + 0.4], [0, 1], {...clamp, easing: ease});
  const card = interpolate(f, [0, 12], [0, 1], clamp);
  const pts = Array.from({length: 61}).map((_, i) => q((i / 60) * draw));
  const d = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
  const tKm = wordTime(seg, labels.km_key, tA);
  const tVol = wordTime(seg, labels.vol_key, tB + 1);
  const km = interpolate(tNow, [tKm, tKm + 0.4], [0, 1], clamp);
  const vol = interpolate(tNow, [tVol, tVol + 0.5], [0, 1], clamp);
  const txt = (sz: number, c = '#f4ecdc'): React.CSSProperties => ({fontFamily: 'Inter', fontWeight: 700, fontSize: sz * s, fill: c});
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
      <rect x={ax} y={ay} width={aw} height={ah} rx={24 * s} fill="rgba(10,9,7,.72)" stroke="rgba(242,184,75,.35)" strokeWidth={2} opacity={card} />
      <g opacity={card}>
        <path d={d} stroke="#000" strokeWidth={22 * s} fill="none" strokeLinecap="round" opacity={0.6} />
        <path d={d} stroke={AMBER} strokeWidth={10 * s} fill="none" strokeLinecap="round" />
        {draw > 0.99 && Array.from({length: 7}).map((_, i) => {
          const p = q(((i / 7) + f / 90) % 1);
          return <circle key={i} cx={p.x} cy={p.y} r={6 * s} fill="#fff4d6" />;
        })}
        <circle cx={P0.x} cy={P0.y} r={16 * s} fill={AMBER} opacity={draw > 0 ? 1 : 0.3} />
        <circle cx={P2.x} cy={P2.y} r={16 * s} fill={AMBER} opacity={draw > 0.99 ? 1 : 0.3} />
        <text x={P0.x} y={P0.y + 62 * s} textAnchor="middle" style={txt(40)} opacity={interpolate(tNow, [tA - 0.2, tA + 0.3], [0, 1], clamp)}>{labels.from}</text>
        <text x={P2.x} y={P2.y + 62 * s} textAnchor="middle" style={txt(40)} opacity={interpolate(tNow, [tB - 0.2, tB + 0.3], [0, 1], clamp)}>{labels.to}</text>
        <text x={q(0.5).x} y={q(0.5).y - 34 * s} textAnchor="middle" style={txt(54, AMBER)} opacity={km}>{labels.km}</text>
        <text x={ax + aw / 2} y={ay + ah - 34 * s} textAnchor="middle" style={txt(44, '#fff')} opacity={vol}>{labels.vol}</text>
      </g>
    </svg>
  );
};

// гиперболоид: прямые стержни между двумя кольцами, ярусы
const TowerMesh: React.FC<{W: number; H: number; cx: number; top: number; bottom: number; width: number; delay?: number; opacity?: number}> = ({W, H, cx, top, bottom, width, delay = 0, opacity = 1}) => {
  // гиперболоид Шухова: 6 секций, каждая — сетка прямых между двумя кольцами, повёрнутыми на угол (отсюда «талия»);
  // радиусы колец плавно сужаются кверху, как на Шаболовке
  const f = useCurrentFrame() - delay;
  const N = 24, tiers = 6, ry = 0.14;
  const lines: JSX.Element[] = [];
  const tierH = (bottom - top) / tiers;
  const rad = (k: number) => (width / 2) * (1 - 0.8 * k / tiers);
  for (let k = 0; k < tiers; k++) {
    const rB = rad(k), rT = rad(k + 1);
    const yB = bottom - k * tierH, yT = yB - tierH;
    const twist = Math.PI * (k === 0 ? 0.32 : 0.22);
    const prog = interpolate(f, [k * 12, k * 12 + 28], [0, 1], {...clamp, easing: ease});
    for (let i = 0; i < N; i++) {
      for (const dir of [1, -1]) {
        const a = (i / N) * Math.PI * 2, b = a + dir * twist;
        const x1 = cx + rB * Math.cos(a), y1 = yB + rB * ry * Math.sin(a);
        const x2 = cx + rT * Math.cos(b), y2 = yT + rT * ry * Math.sin(b);
        const back = Math.sin(a) < 0 && Math.sin(b) < 0;
        lines.push(<line key={`${k}-${i}-${dir}`} x1={x1} y1={y1} x2={x1 + (x2 - x1) * prog} y2={y1 + (y2 - y1) * prog}
          stroke={back ? 'rgba(242,184,75,.3)' : AMBER} strokeWidth={back ? 1.2 : 2} />);
      }
    }
    lines.push(<ellipse key={`e${k}`} cx={cx} cy={yB} rx={rB} ry={rB * ry} fill="none" stroke={AMBER} strokeWidth={2.5} opacity={prog} />);
    // промежуточные горизонтальные кольца — на гиперболе секции
    for (const t of [0.33, 0.66]) {
      const r0 = rB + (rT - rB) * t, waist = Math.cos(twist / 2) + (1 - Math.cos(twist / 2)) * Math.abs(2 * t - 1) ** 2;
      lines.push(<ellipse key={`m${k}-${t}`} cx={cx} cy={yB - tierH * t} rx={r0 * waist} ry={r0 * waist * ry} fill="none"
        stroke="rgba(242,184,75,.55)" strokeWidth={1.2} opacity={prog} />);
    }
    if (k === tiers - 1) lines.push(<ellipse key="top" cx={cx} cy={yT} rx={rT} ry={rT * ry} fill="none" stroke={AMBER} strokeWidth={2.5} opacity={prog} />);
  }
  return <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity, filter: 'drop-shadow(0 0 6px rgba(242,184,75,.5))'}}>{lines}</svg>;
};

// высота шара: счётчик от 0 до labels.alt (м) между словами alt_from и alt_key
const Altitude: React.FC<{W: number; H: number; seg: TSeg; t0: number; area: [number, number, number, number]; labels: any}> = ({W, H, seg, t0, area, labels}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tNow = t0 + f / fps;
  const [ax, ay, aw, ah] = area;
  const a = wordTime(seg, labels.alt_from, seg.start), b = wordTime(seg, labels.alt_key, seg.start + 4);
  const k = interpolate(tNow, [a, b + 0.3], [0, 1], {...clamp, easing: ease});
  const card = interpolate(f, [0, 12], [0, 1], clamp);
  const s = Math.min(aw, ah) / 400;
  const barX = ax + aw * 0.5, top = ay + ah * 0.12, bot = ay + ah * 0.78, y = bot - (bot - top) * k;
  return (
    <svg width={W} height={H} style={{position: 'absolute', inset: 0, opacity: card}}>
      <rect x={ax} y={ay} width={aw} height={ah} rx={20 * s} fill="rgba(10,9,7,.74)" stroke="rgba(242,184,75,.35)" strokeWidth={2} />
      <line x1={barX} y1={top} x2={barX} y2={bot} stroke="rgba(255,255,255,.25)" strokeWidth={6 * s} strokeLinecap="round" />
      <line x1={barX} y1={y} x2={barX} y2={bot} stroke={AMBER} strokeWidth={6 * s} strokeLinecap="round" />
      <circle cx={barX} cy={y - 26 * s} r={24 * s} fill="#e9dfc8" stroke={AMBER} strokeWidth={3 * s} />
      <line x1={barX - 10 * s} y1={y - 4 * s} x2={barX + 10 * s} y2={y - 4 * s} stroke="#e9dfc8" strokeWidth={4 * s} />
      <text x={ax + aw / 2} y={ay + ah * 0.93} textAnchor="middle" style={{fontFamily: 'Inter', fontWeight: 800, fontSize: 64 * s, fill: k > 0.99 ? AMBER : '#fff'}}>
        {Math.round(labels.alt * k).toLocaleString('ru-RU')} м</text>
    </svg>
  );
};

// квадрат пластинки с подписью размера, появляется на слове key.
// Рамка — только с содержимым (r254): labels.image — кадр дня внутри рамки, labels.steklo — рамка сама изображает
// стеклянную пластинку (26jan). Без содержимого пустой рамки нет — только надпись крупно (проверка — scripts/check.mjs).
const PlateFrame: React.FC<{W: number; H: number; seg: TSeg; t0: number; cx: number; cy: number; side: number; labels: any; day: string; shade?: boolean}> = ({W, H, seg, t0, cx, cy, side, labels, day, shade}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tk = wordTime(seg, labels.key, seg.start + 4);
  const k = interpolate(t0 + f / fps, [tk - 0.2, tk + 0.6], [0, 1], {...clamp, easing: ease});
  const L = side * 4;
  const img: string | undefined = labels.image;
  if (!img && !labels.steklo) {
    const fs = Math.max(side * 0.3, 64);
    const uw = Math.min(W * 0.4, side * 1.4);
    return (
      <>
      {shade && <AbsoluteFill style={{opacity: k, background: 'linear-gradient(90deg, rgba(0,0,0,.62) 0%, rgba(0,0,0,.45) 40%, rgba(0,0,0,0) 70%)'}} />}
      <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
        <text x={cx} y={cy + fs * 0.35} textAnchor="middle" opacity={k} style={{fontFamily: 'Inter', fontWeight: 800, fontSize: fs, fill: AMBER}}>{labels.text}</text>
        <line x1={cx - uw / 2} y1={cy + fs * 0.75} x2={cx - uw / 2 + uw * k} y2={cy + fs * 0.75} stroke={AMBER} strokeWidth={4} strokeLinecap="round" opacity={0.8} />
      </svg>
      </>
    );
  }
  return (
    <>
      {img && (
        <div style={{position: 'absolute', left: cx - side / 2, top: cy - side / 2, width: side, height: side, overflow: 'hidden', opacity: k}}>
          <Img src={staticFile(`days/${day}/${img}-bg.jpg`)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </div>
      )}
      <svg width={W} height={H} style={{position: 'absolute', inset: 0}}>
        <rect x={cx - side / 2} y={cy - side / 2} width={side} height={side} fill={img ? 'none' : `rgba(200,225,235,${0.10 * k})`} stroke={AMBER} strokeWidth={4}
          strokeDasharray={L} strokeDashoffset={L * (1 - k)} />
        {!img && <line x1={cx - side / 2 + side * 0.1} y1={cy - side / 2 + side * 0.12} x2={cx - side / 2 + side * 0.3} y2={cy - side / 2 + side * 0.08} stroke="#fff" strokeWidth={3} opacity={0.6 * k} />}
        <text x={cx} y={cy + side / 2 + side * 0.2} textAnchor="middle" opacity={k} style={{fontFamily: 'Inter', fontWeight: 800, fontSize: Math.max(side * 0.16, 48), fill: AMBER}}>{labels.text}</text>
      </svg>
    </>
  );
};

// лента лет: карточки появляются на своём слове; win — подсвечена.
// r265: первая карточка — с начала сцены (иначе в 16:9 правая половина пустая до слова key, 03/06 янв.);
// год — одной строкой (было «40–/50 к.»), длинный год мельче (до LAYOUT.y_max знаков — scripts/check.mjs)
const Years: React.FC<{seg: TSeg; t0: number; area: [number, number, number, number]; labels: any; vertical: boolean}> = ({seg, t0, area, labels, vertical}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const tNow = t0 + f / fps;
  const [ax, ay, aw, ah] = area;
  const items: any[] = labels.items || [];
  const gap = 18, rowH = (ah - gap * (items.length - 1)) / Math.max(3, items.length);
  return (
    <div style={{position: 'absolute', left: ax, top: ay, width: aw, height: ah}}>
      {items.map((it, i) => {
        const tk = it.key ? wordTime(seg, it.key, seg.start + 1 + i) : -1;
        const k = i === 0 ? interpolate(f, [0, 12], [0, 1], {...clamp, easing: ease})
          : it.key ? interpolate(tNow, [tk - 0.15, tk + 0.35], [0, 1], {...clamp, easing: ease}) : 1;
        const yLen = String(it.y).length;
        return (
          <div key={i} style={{position: 'absolute', left: 0, top: i * (rowH + gap), width: aw, height: rowH, opacity: k,
            transform: `translateX(${(1 - k) * 40}px)`, display: 'flex', alignItems: 'center', gap: 26, padding: '0 28px', boxSizing: 'border-box',
            background: it.win ? 'rgba(242,184,75,.16)' : 'rgba(10,9,7,.76)', border: `2px solid ${it.win ? AMBER : 'rgba(255,255,255,.18)'}`, borderRadius: 18,
            fontFamily: 'Inter', color: '#fff'}}>
            <div style={{fontWeight: 800, fontSize: rowH * 0.42 * Math.min(1, 5.5 / Math.max(yLen, 1)), color: it.win ? AMBER : '#fff', letterSpacing: -1,
              whiteSpace: 'nowrap', flexShrink: 0}}>{it.y}</div>
            <div style={{fontWeight: 600, fontSize: rowH * (vertical ? 0.24 : 0.22), lineHeight: 1.15}}>{it.t}</div>
          </div>
        );
      })}
    </div>
  );
};

const ImgLabel: React.FC<{text?: string | null; vertical: boolean}> = ({text, vertical}) => text ? (
  <div style={{position: 'absolute', right: 18, bottom: 18, padding: '6px 14px', borderRadius: 8, background: 'rgba(0,0,0,.66)', color: 'rgba(255,255,255,.9)',
    fontFamily: 'Inter', fontWeight: 600, fontSize: vertical ? 28 : 24}}>{text}</div>
) : null;

// ---------- субтитры ----------
type Chunk = {start: number; end: number; words: Word[]};
const chunkWords = (segs: TSeg[], maxChars: number): Chunk[] => {
  const out: Chunk[] = [];
  const L = (ws: Word[]) => ws.map((x) => x.w).join(' ').length;
  segs.forEach((s) => {
    // тире не живёт отдельно — приклеиваем к предыдущему слову
    const ws: Word[] = [];
    s.words.forEach((w) => { if (/^[—–-]$/.test(w.w) && ws.length) ws[ws.length - 1] = {...ws[ws.length - 1], w: ws[ws.length - 1].w + ' —'}; else ws.push(w); });
    // по предложениям, каждое — на равные куски, без «сирот»
    const sents: Word[][] = [[]];
    ws.forEach((w) => { sents[sents.length - 1].push(w); if (/[.:!?]$/.test(w.w)) sents.push([]); });
    sents.filter((x) => x.length).forEach((sw) => {
      const k = Math.ceil(L(sw) / maxChars);
      const target = L(sw) / k;
      let cur: Word[] = [];
      sw.forEach((w, i) => {
        cur.push(w);
        const rest = sw.length - i - 1;
        if (rest > 0 && out.length < 1e4 && L(cur) >= target * 0.92 && rest >= 2) { out.push({start: cur[0].t, end: 0, words: cur}); cur = []; }
      });
      if (cur.length) out.push({start: cur[0].t, end: 0, words: cur});
    });
    out[out.length - 1].end = s.start + s.dur + 0.25;
  });
  out.forEach((c, i) => { if (!c.end) c.end = out[i + 1].start; });
  return out;
};

const Subtitles: React.FC<{segs: TSeg[]; vertical: boolean; hideFrom: number}> = ({segs, vertical, hideFrom}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = f / fps;
  const chunks = React.useMemo(() => chunkWords(segs, vertical ? 30 : 44), [segs, vertical]);
  const c = chunks.find((x) => t >= x.start - 0.08 && t < x.end);
  if (!c || t >= hideFrom) return null;
  const pop = interpolate(t, [c.start - 0.08, c.start + 0.1], [0.92, 1], clamp);
  const S = LAYOUT.sub;
  const fs = vertical ? S.font_v : S.font_h;
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: height * (vertical ? S.bottom_v : S.bottom_h), display: 'flex', justifyContent: 'center'}}>
      <div style={{
        maxWidth: vertical ? width * 0.9 : width * 0.78, padding: `${vertical ? S.pad_v : S.pad_h}px 34px`, borderRadius: 18,
        background: 'rgba(8,7,5,.82)', borderBottom: `${S.border}px solid ${AMBER}`, transform: `scale(${pop})`,
        fontFamily: 'Inter', fontWeight: 800, fontSize: fs, lineHeight: S.line, color: '#fff', textAlign: 'center',
        letterSpacing: -0.5, boxShadow: '0 10px 40px rgba(0,0,0,.5)',
      }}>
        {c.words.map((w, i) => {
          const active = t >= w.t - 0.05;
          return <span key={i} style={{color: active ? (t < w.t + w.d + 0.15 ? AMBER : '#fff') : 'rgba(255,255,255,.55)'}}>{w.w}{i < c.words.length - 1 ? ' ' : ''}</span>;
        })}
      </div>
    </div>
  );
};

// ---------- сцена ----------
const Scene: React.FC<{props: Props; seg: DaySeg; tseg: TSeg; t0: number; dur: number; vertical: boolean; first: boolean; cut?: boolean; videoBg?: string}> = ({props, seg, tseg, t0, dur, vertical, first, cut, videoBg}) => {
  const f = useCurrentFrame();
  const {width: W, height: H} = useVideoConfig();
  const p = f / dur;
  const fade = first || cut ? 1 : interpolate(f, [0, XF], [0, 1], clamp);
  const meta = props.images!;
  const day = props.day;
  const k = seg.image || '';
  const fx = seg.fx;
  const labels: any = (seg as any).labels || {};
  let body: React.ReactNode;

  const panel = (x: number, y: number, w: number, h: number, mode: 'zoom' | 'pan', dim = 0) => (
    <div style={{position: 'absolute', left: x, top: y, width: w, height: h, overflow: 'hidden', borderRadius: vertical ? 0 : 0}}>
      <Layered day={day} k={k} meta={meta} W={w} H={h} p={p} mode={mode} dim={dim} video={videoBg} />
      {!videoBg && <ImgLabel text={meta[k]?.label} vertical={vertical} />}
    </div>
  );
  const blurBg = (
    <div style={{position: 'absolute', inset: 0, filter: 'blur(28px) brightness(.38)', transform: 'scale(1.15)'}}>
      <Layered day={day} k={k} meta={meta} W={W} H={H} p={p} mode="zoom" video={videoBg} />
    </div>
  );

  if (fx === 'endcard') {
    const a = interpolate(f, [4, 22], [0, 1], {...clamp, easing: ease});
    body = (
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 50% 40%, #2a2216 0%, ${INK} 70%)`}}>
        {labels.deco !== 'none' && <TowerMesh W={W} H={H} cx={vertical ? W * 0.5 : W * 0.8} top={H * (vertical ? 0.08 : 0.1)} bottom={H * (vertical ? 0.5 : 0.92)} width={vertical ? W * 0.55 : H * 0.55} opacity={0.35} />}
        <Particles kind="dust" n={40} W={W} H={H} seed="end" />
        <div style={{position: 'absolute', left: vertical ? 60 : 140, right: vertical ? 60 : W * 0.4, top: vertical ? H * 0.52 : H * 0.3,
          opacity: a, transform: `translateY(${(1 - a) * 30}px)`, fontFamily: 'Inter', color: '#fff', textAlign: vertical ? 'center' : 'left'}}>
          <div style={{fontWeight: 600, fontSize: vertical ? 64 : 64, lineHeight: 1.15}}>Смотри день целиком на</div>
          <div style={{fontWeight: 800, fontSize: vertical ? 76 : 92, color: AMBER, marginTop: 18, letterSpacing: -1}}>russian-civilization.ru</div>
        </div>
      </AbsoluteFill>
    );
  } else if (fx === 'formulas') {
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.06, W, H * 0.46, 'zoom')}
        <div style={{position: 'absolute', left: 0, top: H * 0.5, width: W, height: H * 0.26}}>
          <Formulas W={W} H={H * 0.26} seg={tseg} t0={t0} labels={labels} /></div></>
    ) : (
      <><AbsoluteFill style={{background: `linear-gradient(90deg, #15120d, ${INK})`}} />
        {panel(0, 0, W * 0.4, H, 'zoom')}
        <div style={{position: 'absolute', left: W * 0.4, top: 0, width: W * 0.6, height: H * 0.82}}>
          <Formulas W={W * 0.6} H={H * 0.82} seg={tseg} t0={t0} labels={labels} /></div></>
    );
  } else if (fx === 'tower-mesh') {
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.06, W, H * 0.48, 'zoom')}
        <TowerMesh W={W} H={H} cx={W * 0.5} top={H * 0.53} bottom={H * 0.735} width={W * 0.2} delay={10} /></>
    ) : (
      <><AbsoluteFill style={{background: `linear-gradient(90deg, ${INK}, #15120d)`}} />
        {panel(W * 0.5, 0, W * 0.5, H, 'zoom')}
        <TowerMesh W={W} H={H} cx={W * 0.25} top={H * 0.05} bottom={H * 0.8} width={H * 0.36} delay={10} /></>
    );
  } else if (fx === 'altitude') {
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.08, W, H * 0.5, 'zoom')}
        <Altitude W={W} H={H} seg={tseg} t0={t0} area={[W * 0.25, H * 0.585, W * 0.5, H * 0.145]} labels={labels} /></>
    ) : (
      <><AbsoluteFill style={{background: `linear-gradient(90deg, #15120d, ${INK})`}} />
        {panel(W * 0.08, H * 0.06, H * 0.7, H * 0.7, 'zoom')}
        <Altitude W={W} H={H} seg={tseg} t0={t0} area={[W * 0.56, H * 0.08, W * 0.3, H * 0.66]} labels={labels} /></>
    );
  } else if (fx === 'plate') {
    body = vertical ? (
      <>{blurBg}{panel(W * 0.08, H * 0.07, W * 0.84, H * 0.47, 'zoom')}
        <PlateFrame W={W} H={H} seg={tseg} t0={t0} cx={W * 0.5} cy={H * 0.64} side={H * 0.12} labels={labels} day={day} /></>
    ) : !labels.image && !labels.steklo ? (
      // без рамки (r256): фото на весь кадр с начала сцены, надпись крупно слева на слове key, под ней — затемнение
      <>{panel(0, 0, W, H, 'zoom')}
        <PlateFrame W={W} H={H} seg={tseg} t0={t0} cx={W * 0.25} cy={H * 0.36} side={H * 0.36} labels={labels} day={day} shade /></>
    ) : (
      <><AbsoluteFill style={{background: `linear-gradient(90deg, ${INK}, #15120d)`}} />
        {panel(W * 0.5, 0, W * 0.5, H, 'zoom')}
        <PlateFrame W={W} H={H} seg={tseg} t0={t0} cx={W * 0.25} cy={H * 0.36} side={H * 0.36} labels={labels} day={day} /></>
    );
  } else if (fx === 'years') {
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.06, W, H * 0.42, 'zoom')}
        <Years seg={tseg} t0={t0} area={[W * LAYOUT.years_v[0], H * LAYOUT.years_v[1], W * LAYOUT.years_v[2], H * LAYOUT.years_v[3]]} labels={labels} vertical /></>
    ) : (
      <><AbsoluteFill style={{background: `linear-gradient(90deg, #15120d, ${INK})`}} />
        {panel(0, 0, W * 0.5, H, 'zoom')}
        <Years seg={tseg} t0={t0} area={[W * LAYOUT.years_h[0], H * LAYOUT.years_h[1], W * LAYOUT.years_h[2], H * LAYOUT.years_h[3]]} labels={labels} vertical={false} /></>
    );
  } else if (fx === 'pipeline-map') {
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.06, W, H * 0.42, 'pan')}
        <Particles kind="smoke" n={6} W={W} H={H * 0.5} seed={seg.id} />
        <PipelineMap W={W} H={H} seg={tseg} t0={t0} area={[W * 0.04, H * 0.5, W * 0.92, H * 0.25]} labels={labels} /></>
    ) : (
      <>{panel(0, 0, W, H, 'zoom', 0.35)}
        <Particles kind="smoke" n={8} W={W} H={H} seed={seg.id} />
        <PipelineMap W={W} H={H} seg={tseg} t0={t0} area={[W * 0.2, H * 0.08, W * 0.6, H * 0.6]} labels={labels} /></>
    );
  } else {
    // фото на весь кадр (16:9) / фото-панель + размытый фон (9:16)
    const hook = fx === 'pipe-sweep';
    body = vertical ? (
      <>{blurBg}{panel(0, H * 0.1, W, H * 0.58, 'pan')}
        <Particles kind={hook ? 'smoke' : 'dust'} n={hook ? 7 : 50} W={W} H={H * 0.7} seed={seg.id} />
        {hook && <PipeSweep W={W} H={H} y={H * 0.72} />}</>
    ) : (
      <>{panel(0, 0, W, H, 'zoom')}
        <Particles kind={hook ? 'smoke' : 'dust'} n={hook ? 8 : 60} W={W} H={H} seed={seg.id} />
        {hook && <PipeSweep W={W} H={H} y={H * 0.74} />}</>
    );
  }
  return <AbsoluteFill style={{opacity: fade}}>{body}</AbsoluteFill>;
};

const Grain: React.FC = () => {
  const f = useCurrentFrame();
  const {width, height} = useVideoConfig();
  return (
    <svg width={width} height={height} style={{position: 'absolute', inset: 0, opacity: 0.07, mixBlendMode: 'overlay'}}>
      <filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="1" seed={f % 6} /></filter>
      <rect width="100%" height="100%" filter="url(#n)" />
    </svg>
  );
};

export const Video: React.FC<Props> = (props) => {
  useFonts();
  const {fps, width, height, durationInFrames} = useVideoConfig();
  const vertical = height > width;
  const {cfg, timeline, day, variant} = props;
  if (!cfg || !timeline) return null;
  const segs = timeline.segments;
  const starts = segs.map((s, i) => (i === 0 ? 0 : Math.round((s.start - 0.3) * fps)));
  const insert = variant === 'B' && cfg.insert_b ? cfg.insert_b : null;
  const endStart = segs[segs.length - 1].start - 0.3;
  return (
    <AbsoluteFill style={{background: INK}}>
      {cfg.segments.map((seg, i) => {
        const from = starts[i];
        const to = i < segs.length - 1 ? starts[i + 1] + XF : durationInFrames;
        const useVideo = insert && i === 0 ? 'insert.mp4' : undefined;
        // r265: тот же снимок, что в прошлой сцене (другая обрезка) — прямая склейка: растворение двоит кадр (08 янв.: две трубы, «призрак»)
        const src = (k?: string | null) => (k ? ((cfg as any).images?.[k]?.src ?? k) : null);
        const prev = i > 0 ? cfg.segments[i - 1] : null;
        const cut = !!prev && !useVideo && src(seg.image) !== null && src(seg.image) === src(prev.image);
        return (
          <Sequence key={seg.id} from={from} durationInFrames={to - from}>
            <Scene props={props} seg={seg} tseg={segs[i]} t0={from / fps} dur={to - from} vertical={vertical} first={i === 0} cut={cut} videoBg={useVideo} />
          </Sequence>
        );
      })}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,.55) 100%)'}} />
      <Grain />
      {insert && (
        <Sequence from={0} durationInFrames={starts[1]}>
          <div style={{position: 'absolute', top: vertical ? height * 0.115 : 36, left: vertical ? 30 : 40, padding: '8px 18px', borderRadius: 10,
            background: 'rgba(0,0,0,.65)', color: '#fff', fontFamily: 'Inter', fontWeight: 600, fontSize: vertical ? 34 : 30, letterSpacing: 0.5}}>
            {insert.label}
          </div>
        </Sequence>
      )}
      {vertical && (
        <div style={{position: 'absolute', top: 40, left: 0, right: 0, textAlign: 'center', fontFamily: 'Inter', fontWeight: 700, fontSize: 32,
          color: 'rgba(255,255,255,.75)', letterSpacing: 2}}>RUSSIAN-CIVILIZATION.RU</div>
      )}
      <Subtitles segs={segs} vertical={vertical} hideFrom={endStart} />
      <Audio src={staticFile(`days/${day}/mix.mp3`)} />
    </AbsoluteFill>
  );
};
