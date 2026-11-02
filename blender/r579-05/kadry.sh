#!/bin/bash
# r579: кадры облёта нефтепровода <с> <по> <папка>, 1280×720, 32 сэмпла (BL — путь к Блендеру 4.2)
mkdir -p "$3"; "${BL:-blender}" -b --factory-startup -t 0 -P nefteprovod.py -- kadry "$3" "$1" "$2" 1280 720 32
