// Общая библиотека коротких движений кадра (r713 п.71): наезд, панорама, появление, сдвиг, растворение.
// Формулы и числа — те же, что были в Video.tsx; новая сцена берёт движение отсюда, а не пишет своё.
import {Easing, interpolate} from 'remotion';

export const ease = Easing.bezier(0.33, 0, 0.2, 1);
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
export const XF = 9; // кадров на перекрёстный переход

// появление 0→1 на отрезке [a, b] (кадры или секунды); plavno — с тем же сглаживанием ease
export const rost = (x: number, a: number, b: number, plavno = false) =>
  interpolate(x, [a, b], [0, 1], plavno ? {...clamp, easing: ease} : clamp);

// выезд: при k=0 сдвинуто на px, при k=1 на месте
export const vyezd = (k: number, px: number) => (1 - k) * px;

// растворение сцены: первая сцена и прямая склейка — сразу 1, иначе за XF кадров
export const rastvorenie = (f: number, bezPerehoda: boolean) => (bezPerehoda ? 1 : rost(f, 0, XF));

// точка главного предмета (доли 0..1 кадра) — предложение scripts/tochka.py, по умолчанию не применяется
export type Fokus = {x: number; y: number};

// наезд (zoom), панорама (pan), вписать (contain) — масштаб и сдвиги фона и переднего плана в момент p∈[0,1].
// fokus (только если задан): кадр держится на точке, панорама — малая, вокруг неё, без выхода за край.
export const dvizhenieKadra = (
  m: {w: number; h: number}, W: number, H: number, p: number, mode: 'zoom' | 'pan' | 'contain', fokus?: Fokus,
) => {
  const cover = mode === 'contain' ? Math.min(W / m.w, H / m.h) : Math.max(W / m.w, H / m.h);
  const e = ease(p);
  const sBg = cover * (mode === 'contain' ? 1 + 0.04 * e : mode === 'zoom' ? 1.06 + 0.10 * e : 1.04 + 0.03 * e);
  const sFg = cover * (mode === 'zoom' ? 1.06 + 0.13 * e : 1.04 + 0.06 * e);
  const spanBg = Math.max(0, m.w * sBg - W) / 2;
  const spanFg = Math.max(0, m.w * sFg - W) / 2;
  let dxBg = mode === 'pan' ? interpolate(e, [0, 1], [spanBg * 0.85, -spanBg * 0.85]) : mode === 'contain' ? 0 : -18 * e;
  let dxFg = mode === 'pan' ? interpolate(e, [0, 1], [spanFg * 0.95, -spanFg * 0.95]) : -36 * e;
  let dyBg = mode === 'contain' ? 0 : 6 * e;
  let dyFg = -10 * e;
  if (fokus && mode !== 'contain') {
    const naTochku = (s: number, span: number, sdvig: number) => {
      const c = (0.5 - fokus.x) * m.w * s; // сдвиг, ставящий точку в центр окна
      return Math.max(-span, Math.min(span, c + (mode === 'pan' ? interpolate(e, [0, 1], [span * 0.15, -span * 0.15]) : sdvig)));
    };
    const naTochkuY = (s: number, sdvig: number) => {
      const span = Math.max(0, m.h * s - H) / 2;
      return Math.max(-span, Math.min(span, (0.5 - fokus.y) * m.h * s + sdvig));
    };
    dxBg = naTochku(sBg, spanBg, -18 * e);
    dxFg = naTochku(sFg, spanFg, -36 * e);
    dyBg = naTochkuY(sBg, 6 * e);
    dyFg = naTochkuY(sFg, -10 * e);
  }
  return {sBg, sFg, dxBg, dxFg, dyBg, dyFg};
};
