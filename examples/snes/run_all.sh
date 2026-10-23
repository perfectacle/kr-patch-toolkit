#!/bin/zsh
# Play every scenario on every emulator and collect one result line per run.
# usage: run_all.sh [core ...]   -> out/<scenario>-<emulator>-<rom>/ and results.txt
#
# Layout (next to this script):
#   cores/<core>_libretro.dylib   libretro cores
#   roms/<rom>.sfc                ROMs; a name ending in h means roms/<rom>.smc (512-byte copier header)
#   roms/save.srm                 save RAM for scenarios listed in SAVE_SCENARIOS
#   s_<scenario>.txt              input scripts (see `krpatch snes run -h`)
# env:
#   SETS="new:v1,v2 cont:v1,v2"    scenario:roms pairs
#   WATCH_WRAM="7E0010:2"          WRAM value(s) logged to wram.log, comma separated
#   MESEN=/path/to/Mesen           also run Mesen 2 through `krpatch snes lua`/script.lua
#   MESEN_SAVES                    Mesen 2 save folder (it loads Saves/<rom name>.srm on power-on)
cd "$(dirname $0)"
export LRVARS=${LRVARS:-"supafaust_thread_affinity_ppu=0x0,supafaust_thread_affinity_emu=0x0"}
SETS=(${=SETS:-new:v1 cont:v1})
SAVE_SCENARIOS=(${=SAVE_SCENARIOS:-cont})
cores=($@)
(( $# )) || cores=(bsnes bsnes_hd_beta snes9x snes9x2010 mednafen_supafaust mesen-s)
watch=(); for w in ${(s:,:)WATCH_WRAM}; do watch+=(--watch $w); done
LUA=$(krpatch snes lua)
MESEN_SAVES=${MESEN_SAVES:-$HOME/Library/Application Support/Mesen2/Saves}

run() {  # emulator scenario rom
  local f=roms/$3.sfc; [[ $3 == *h ]] && f=roms/$3.smc
  local d=out/$2-$1-$3 srm=
  (( ${SAVE_SCENARIOS[(Ie)$2]} )) && srm=roms/save.srm
  rm -rf $d; mkdir -p $d
  if [[ $1 == mesen2 ]]; then
    # Mesen 2 keeps its own save per ROM name; replace or remove it so each run starts the same
    if [[ -n $srm ]]; then cp $srm "$MESEN_SAVES/${f:t:r}.srm"; else rm -f "$MESEN_SAVES/${f:t:r}.srm"; fi
    env LIBDIR=$LUA SCRIPT=$PWD/s_$2.txt SHOT_DIR=$PWD/$d WATCH_WRAM=$WATCH_WRAM ${srm:+SRM=$PWD/$srm} \
      $MESEN --testrunner $PWD/$f $LUA/script.lua > $d.log 2>&1
    echo "exit=$? last=$(tail -1 $d/wram.log 2>/dev/null)"
  else
    krpatch snes run cores/$1_libretro.dylib $f $d s_$2.txt $srm $watch > $d.log 2>&1
    echo "exit=$? $(grep -E '^OK|LOAD FAILED|terminat|Segmentation' $d.log | tail -1) last=$(tail -1 $d/wram.log 2>/dev/null)"
  fi
}

: > results.txt
emus=($cores); [[ -n $MESEN ]] && emus+=(mesen2)
for emu in $emus; do
  for s in $SETS; do
    for rom in ${(s:,:)s#*:}; do
      echo "${s%%:*} $emu $rom $(run $emu ${s%%:*} $rom)" >> results.txt
    done
  done
done
