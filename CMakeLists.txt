cmake_minimum_required(VERSION 3.16)

# ---------------------------------------------------------------------------
#  mappaAI — Frullatore 3D
#
#  Integra la generazione del modello Blender in un flusso CMake:
#
#     cmake -S . -B build -DBLENDER_EXECUTABLE=/usr/bin/blender
#     cmake --build build                 # genera .blend e .glb
#     cmake --build build --target rendering   # + rendering Cycles
#     cmake --build build --target viewer      # avvia il viewer web
#
#  se Blender non è installato si può usare il modulo Python `bpy`
#  (tools/setup_blender_env.sh) e la variabile -DUSO_BPY=ON
# ---------------------------------------------------------------------------

project(mappaAI_Frullatore LANGUAGES NONE)

set(FRULLATORE_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/scripts/costruisci_frullatore.py")
set(FRULLATORE_BLEND  "${CMAKE_CURRENT_SOURCE_DIR}/models/frullatore.blend")
set(FRULLATORE_GLB    "${CMAKE_CURRENT_SOURCE_DIR}/models/frullatore.glb")

option(USO_BPY "usa il modulo Python bpy invece dell'eseguibile Blender" OFF)
option(RENDER "esegue anche i rendering Cycles" OFF)
set(CAMPIONI "128" CACHE STRING "campioni Cycles")
set(RISOLUZIONE "820;1040" CACHE STRING "risoluzione dei rendering (larghezza;altezza)")

if(USO_BPY)
  find_package(Python3 COMPONENTS Interpreter REQUIRED)
  set(FRULLATORE_CMD "${Python3_EXECUTABLE};${FRULLATORE_SCRIPT}")
else()
  if(NOT BLENDER_EXECUTABLE)
    find_program(BLENDER_EXECUTABLE NAMES blender
      HINTS /usr/bin /usr/local/bin /opt/blender "$ENV{ProgramFiles}/Blender Foundation")
  endif()
  if(NOT BLENDER_EXECUTABLE)
    message(FATAL_ERROR
      "Blender non trovato. Passa -DBLENDER_EXECUTABLE=/percorso/blender oppure "
      "usa -DUSO_BPY=ON dopo aver eseguito ./tools/setup_blender_env.sh")
  endif()
  set(FRULLATORE_CMD "${BLENDER_EXECUTABLE};--background;--factory-startup;--python;${FRULLATORE_SCRIPT};--")
endif()

set(FRULLATORE_OPZIONI "--campioni;${CAMPIONI};--risoluzione;${RISOLUZIONE}")

# --- generazione del modello -------------------------------------------------
add_custom_command(
  OUTPUT "${FRULLATORE_BLEND}"
  BYPRODUCTS "${FRULLATORE_GLB}"
  COMMAND ${FRULLATORE_CMD} ${FRULLATORE_OPZIONI}
  DEPENDS "${FRULLATORE_SCRIPT}"
  COMMENT "Generazione del modello 3D del frullatore (.blend + .glb)"
  VERBATIM
)

add_custom_target(frullatore ALL DEPENDS "${FRULLATORE_BLEND}")

# --- rendering ---------------------------------------------------------------
add_custom_target(rendering
  COMMAND ${FRULLATORE_CMD} ${FRULLATORE_OPZIONI} --render --solo-render
  DEPENDS "${FRULLATORE_BLEND}"
  COMMENT "Rendering Cycles (hero, dettaglio comandi, vista frontale)"
  VERBATIM
)

# --- viewer web --------------------------------------------------------------
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
  add_custom_target(viewer
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/serve.py" 8000
    COMMENT "Viewer su http://localhost:8000/viewer/"
    USES_TERMINAL
  )
endif()

add_custom_target(pulizia
  COMMAND ${CMAKE_COMMAND} -E rm -f "${FRULLATORE_BLEND}" "${FRULLATORE_GLB}"
  COMMENT "Rimozione degli artefatti generati"
)
