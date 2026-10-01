#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_blender_env.sh — prepara Blender "headless" su una macchina senza
#                         display (container, CI, sandbox) usando il modulo
#                         Python ufficiale `bpy`.
#
#   ./tools/setup_blender_env.sh            # installa bpy + librerie stub
#   source tools/attiva_ambiente.sh         # esporta LD_LIBRARY_PATH
#
# Perché serve: il pacchetto `bpy` (Blender 4.2 LTS) richiede a runtime alcune
# librerie X11/GL che nelle immagini server minimali non sono presenti e i
# repository di sistema non sempre sono raggiungibili.  Questo script compila
# delle librerie "stub" con i soli simboli richiesti dai binari di Blender:
# sono sufficienti per il rendering CPU (Cycles) e per l'export glTF, cioè
# tutto ciò che serve a generare il modello.
# ---------------------------------------------------------------------------
set -euo pipefail

RADICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STUB_DIR="${RADICE}/tools/blender_stubs"
BPY_VERSION="${BPY_VERSION:-4.2.0}"

echo "==> 1/4  controllo dipendenze (python3, pip, gcc, nm)"
command -v python3 >/dev/null || { echo "python3 mancante"; exit 1; }
command -v gcc     >/dev/null || { echo "gcc mancante (apt install build-essential)"; exit 1; }
command -v nm      >/dev/null || { echo "nm mancante (apt install binutils)"; exit 1; }

echo "==> 2/4  installazione del modulo bpy ${BPY_VERSION}"
if python3 -c "import bpy" >/dev/null 2>&1; then
  echo "    bpy già importabile, salto l'installazione."
else
  python3 -m pip install --user --break-system-packages "bpy==${BPY_VERSION}" \
    || python3 -m pip install --user "bpy==${BPY_VERSION}"
fi

SITE="$(python3 -c 'import site; print(site.getusersitepackages())')"
BPY_PATH="${SITE}/bpy"
[ -d "${BPY_PATH}" ] || BPY_PATH="$(python3 -c 'import bpy, os; print(os.path.dirname(bpy.__file__))')"

echo "==> 3/4  compilazione delle librerie stub"
mkdir -p "${STUB_DIR}/src" "${STUB_DIR}/lib"

# simboli esterni (X11, GL, xkbcommon, Intel L0...) richiesti dai binari .so di bpy
find "${BPY_PATH}" -name "*.so*" -type f -print0 \
  | xargs -0 nm -D --undefined-only --format=posix 2>/dev/null \
  | awk '{print $1}' | sed 's/@.*//' \
  | grep -E '^(_?X[a-zA-Z0-9_]*|_?ICE[a-zA-Z0-9_]*|_?Ice[a-zA-Z0-9_]*|_?Sm[A-Za-z0-9_]*|_?Sms[A-Za-z0-9_]*|_?Smc[A-Za-z0-9_]*|_?gl[a-zA-Z0-9_]*|_?glX[a-zA-Z0-9_]*|_?egl[a-zA-Z0-9_]*|_?EGL[a-zA-Z0-9_]*|_?wl_[A-Za-z0-9_]+|_?ze[A-Za-z0-9_]+|xkb_[A-Za-z0-9_]+)$' \
  | sort -u > "${STUB_DIR}/src/simboli.txt" || true   # xargs/nm escono 123 su alcuni .so

# simboli con symbol-versioning (xkbcommon espone V_0.5.0, Intel L0 hip_*)
find "${BPY_PATH}" -name "*.so*" -type f -print0 \
  | xargs -0 nm -D --undefined-only --with-symbol-versions --format=posix 2>/dev/null \
  | awk '{print $1}' | grep -E '@' | sed 's/@.*//' | sort -u \
    > "${STUB_DIR}/src/simboli_versionati.txt" || true

grep -v '^xkb_' "${STUB_DIR}/src/simboli.txt" > "${STUB_DIR}/src/simboli_core.txt" || true
grep    '^xkb_' "${STUB_DIR}/src/simboli.txt" > "${STUB_DIR}/src/simboli_xkb.txt"  || true

# --- stub "core" (X11, GL, ICE/SM, Intel L0) ---------------------------------
{
  echo '#include <stdlib.h>'
  grep -v '^XOpenDisplay$' "${STUB_DIR}/src/simboli_core.txt" \
    | while read -r s; do [ -n "$s" ] && echo "void $s(void) { }"; done
  echo 'void *XOpenDisplay(void *name) { (void)name; return NULL; }'
} > "${STUB_DIR}/src/stub_core.c"
gcc -shared -fPIC -O0 -o "${STUB_DIR}/src/libstub_blender.so" "${STUB_DIR}/src/stub_core.c"

# --- stub xkbcommon con la versione richiesta (V_0.5.0) ----------------------
{
  echo '#include <stdlib.h>'
  while read -r s; do [ -n "$s" ] && echo "void $s(void) { }"; done \
    < "${STUB_DIR}/src/simboli_xkb.txt"
} > "${STUB_DIR}/src/stub_xkb.c"
printf 'V_0.5.0 { global: *; };\n' > "${STUB_DIR}/src/xkb.map"
gcc -shared -fPIC -O0 -o "${STUB_DIR}/src/libxkbcommon.so.0" \
    "${STUB_DIR}/src/stub_xkb.c" -Wl,--version-script="${STUB_DIR}/src/xkb.map"

# --- copie con i nomi attesi dal loader --------------------------------------
NOMI_CORE=(libXrender.so.1 libXrender.so libXfixes.so.3 libXfixes.so
           libXi.so.6 libXi.so libSM.so.6 libSM.so libICE.so.6 libICE.so
           libXxf86vm.so.1 libXxf86vm.so libGL.so.1 libGL.so
           libGLX.so.0 libGLX.so libOpenGL.so.0 libOpenGL.so
           libXt.so.6 libXt.so libEGL.so.1 libEGL.so
           libGLESv2.so.2 libGLESv2.so)
for nome in "${NOMI_CORE[@]}"; do
  cp "${STUB_DIR}/src/libstub_blender.so" "${STUB_DIR}/lib/${nome}"
done
cp "${STUB_DIR}/src/libxkbcommon.so.0" "${STUB_DIR}/lib/libxkbcommon.so.0"
cp "${STUB_DIR}/src/libxkbcommon.so.0" "${STUB_DIR}/lib/libxkbcommon.so"

cat > "${RADICE}/tools/attiva_ambiente.sh" <<EOF
# ambiente per usare bpy su questa macchina:  source tools/attiva_ambiente.sh
export LD_LIBRARY_PATH="\${LD_LIBRARY_PATH:-}:${STUB_DIR}/lib"
EOF

echo "==> 4/4  verifica"
if LD_LIBRARY_PATH="${STUB_DIR}/lib" python3 -c "import bpy; print('    Blender', bpy.app.version_string, 'pronto')"; then
  echo
  echo "Fatto.  Ora puoi generare il modello con:"
  echo "    source tools/attiva_ambiente.sh"
  echo "    python3 scripts/costruisci_frullatore.py --render"
else
  echo "ERRORE: bpy non si importa nemmeno con gli stub. Segnala l'errore completo." >&2
  exit 1
fi
