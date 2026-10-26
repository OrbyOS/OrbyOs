#!/bin/sh
# Compila tools/segmentar (solo Mac: Vision + AVFoundation). El overlay de VFS tapa el bridging.modulemap de las
# Command Line Tools, que choca con el de Swift; se genera aquí porque lleva rutas absolutas de cada máquina.
set -e
cd "$(dirname "$0")"
overlay="$(mktemp -t overlay).yaml"
cat > "$overlay" <<YAML
{ "version": 0, "case-sensitive": "false", "roots": [ { "type": "file",
  "name": "/Library/Developer/CommandLineTools/usr/include/swift/bridging.modulemap",
  "external-contents": "$(pwd)/empty.modulemap" } ] }
YAML
swiftc -O -vfsoverlay "$overlay" segmentar.swift -o segmentar
rm -f "$overlay"
echo "Compilado: $(pwd)/segmentar"
