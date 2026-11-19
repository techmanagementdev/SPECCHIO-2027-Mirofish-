#!/usr/bin/env bash
# Scarica i progetti open source di riferimento in upstream/ (cartella esclusa da git).
set -e
cd "$(dirname "$0")/.."
mkdir -p upstream && cd upstream
clona() { [ -d "$2" ] && (cd "$2" && git pull --ff-only) || git clone --depth 1 "https://github.com/$1.git" "$2"; }
clona camel-ai/oasis               oasis
clona tsinghua-fib-lab/AgentSociety agentsociety
clona google-deepmind/concordia    concordia
clona microsoft/tinytroupe         tinytroupe
clona expectedparrot/edsl          edsl
clona 666ghj/MiroFish              mirofish
clona nikmcfly/MiroFish-Offline    mirofish-offline
echo "Fatto. Licenze e uso: docs/OPEN_SOURCE.md"
