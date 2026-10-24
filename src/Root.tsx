import React from 'react';
import {Composition, staticFile, CalculateMetadataFunction} from 'remotion';
import {Video} from './Video';
import {Props} from './types';

export const FPS = 30;

// параметры дня берутся из public/days/<day>/ — один шаблон на все дни
const calc: CalculateMetadataFunction<Props> = async ({props}) => {
  const base = `days/${props.day}/`;
  const [cfg, timeline, images] = await Promise.all(
    ['day.json', 'timeline.json', 'images.json'].map((f) => fetch(staticFile(base + f)).then((r) => r.json())),
  );
  return {durationInFrames: Math.ceil(timeline.total * FPS), props: {...props, cfg, timeline, images}};
};

export const Root: React.FC = () => (
  <>
    <Composition id="Day16x9" component={Video} width={1920} height={1080} fps={FPS} durationInFrames={300}
      defaultProps={{day: '05jan', variant: 'A'} as Props} calculateMetadata={calc} />
    <Composition id="Day9x16" component={Video} width={1080} height={1920} fps={FPS} durationInFrames={300}
      defaultProps={{day: '05jan', variant: 'A'} as Props} calculateMetadata={calc} />
  </>
);
