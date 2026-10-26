export type Word = {t: number; d: number; w: string};
export type TSeg = {id: string; start: number; dur: number; words: Word[]};
export type Timeline = {total: number; segments: TSeg[]};
export type DaySeg = {id: string; say: string; show?: string; image: string | null; fx: string};
export type DayCfg = {
  id: string;
  segments: DaySeg[];
  insert_b?: {file: string; label: string; seconds: number};
};
export type ImgMeta = Record<string, {w: number; h: number; fg: boolean; label?: string | null; contain_v?: boolean}>;
export type Props = {
  day: string;
  variant: 'A' | 'B';
  cfg?: DayCfg;
  timeline?: Timeline;
  images?: ImgMeta;
};
