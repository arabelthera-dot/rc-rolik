#!/bin/bash
# r579: кадры облёта булата <с> <по> <папка>, 1280×720, 32 сэмпла (BL — путь к Блендеру 4.2)
mkdir -p "$3"; "${BL:-blender}" -b --factory-startup -t 0 -P bulat_scena.py -- kadry "$3" "$1" "$2" 1280 720 32
