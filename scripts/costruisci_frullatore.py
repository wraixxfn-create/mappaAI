#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
costruisci_frullatore.py — Modello 3D di un frullatore (blender da cucina)
=========================================================================
Costruisce da zero, in modo procedurale e parametrico, un frullatore con:
  • corpo motore con collare di alloggiamento, pannello comandi, display,
    manopola e pulsanti
  • brocca in vetro con beccuccio e manico
  • coperchio con tappo dosatore
  • gruppo lame a quattro punte in acciaio
  • guarnizione in gomma e piedini

Output:
  models/frullatore.blend   → file nativo Blender (modello + studio luci + camera)
  models/frullatore.glb     → glTF binario (viewer web, game engine, AR)
  renders/*.png             → rendering Cycles (con --render)

Uso con Blender installato:
  blender --background --python scripts/costruisci_frullatore.py -- --render
Uso con il modulo bpy (pip install bpy):
  python3 scripts/costruisci_frullatore.py --render

Scala reale: 1 unità Blender = 1 metro. Ingombro ≈ 17,6 x 17 x 42 cm.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy                      # va importato per primo: registra i moduli bmesh/mathutils
import bmesh                    # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

# --------------------------------------------------------------------------- #
#  PARAMETRI — modifica qui le dimensioni (metri)
# --------------------------------------------------------------------------- #

class Dim:
    """Dimensioni principali del frullatore."""

    # --- corpo motore ---
    BASE_H = 0.1750             # altezza corpo motore (escluso collare)
    BASE_R_MAX = 0.0880         # raggio massimo del corpo motore
    COLLARE_R = 0.0590          # raggio esterno del collare
    SEDE_R = 0.0525             # raggio della sede della brocca
    SEDE_Z = 0.1540             # fondo della sede (piano d'appoggio brocca)

    # --- brocca ---
    BROCCA_Z0 = 0.1560          # z di appoggio della brocca
    BROCCA_H = 0.2450           # altezza brocca
    BROCCA_R_MAX = 0.0802       # raggio massimo brocca
    BECC_H = 0.0700             # altezza della zona beccuccio
    BECC_SPORTE = 0.0150        # sporgenza del beccuccio
    MANICO_BULGE = 0.0570       # sporgenza manico

    # --- coperchio ---
    COPERCHIO_Z0 = 0.4005       # ~ bordo superiore della brocca
    TAPPO_R = 0.0210

    # --- gruppo lame ---
    LAMA_LUNGA = 0.0560
    LAMA_CORTA = 0.0390
    LAMA_SPESSORE = 0.0016
    LAMA_PASSO_DEG = 22.0       # inclinazione (passo) delle lame
    GRUPPO_LAME_Z = 0.1900      # z del piano delle lame

    # --- qualità geometria ---
    SEGMENTI = 96               # segmenti di rivoluzione (circonferenza)


# --------------------------------------------------------------------------- #
#  UTILITÀ GEOMETRICHE
# --------------------------------------------------------------------------- #

def pulisci_scena() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.objects):
        for item in list(blk):
            blk.remove(item)


def nuovo_oggetto(nome: str, bm: bmesh.types.BMesh, collection: bpy.types.Collection):
    """Finalizza un bmesh in un oggetto mesh collegato alla collection data."""
    me = bpy.data.meshes.new(nome)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(nome, me)
    collection.objects.link(ob)
    return ob


def rivoluziona(profilo, nome, segmenti: int = Dim.SEGMENTI, collection=None):
    """Solido di rivoluzione da un profilo 2D [(raggio, quota), ...]."""
    bm = bmesh.new()
    verts = [bm.verts.new((float(r), 0.0, float(z))) for r, z in profilo]
    bm.verts.ensure_lookup_table()
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(
        bm,
        geom=verts + edges,
        cent=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
        dvec=(0.0, 0.0, 0.0),
        angle=2.0 * math.pi,
        steps=segmenti,
        use_merge=True,
        use_duplicate=False,
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return nuovo_oggetto(nome, bm, collection or bpy.context.scene.collection)


def tubo(percorso, raggi, nome, sezioni: int = 24, ellittico=None, collection=None):
    """Tubo estruso lungo un percorso, con frames a trasporto parallelo."""
    pts = [Vector(p) for p in percorso]
    n = len(pts)
    tang = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        tang.append(t.normalized())

    rif = Vector((1.0, 0.0, 0.0))
    if abs(rif.dot(tang[0])) > 0.9:
        rif = Vector((0.0, 1.0, 0.0))
    normale = (rif - tang[0] * rif.dot(tang[0])).normalized()
    frames = []
    for i in range(n):
        if i > 0:
            normale = normale - tang[i] * normale.dot(tang[i])
            if normale.length < 1e-8:
                normale = Vector((0.0, 0.0, 1.0))
            normale.normalize()
        frames.append((normale, tang[i].cross(normale).normalized()))

    bm = bmesh.new()
    anelli = []
    for i, p in enumerate(pts):
        nrm, bnr = frames[i]
        r = raggi[i]
        a, b = (r, r) if ellittico is None else (r * ellittico[0], r * ellittico[1])
        anello = []
        for k in range(sezioni):
            th = 2.0 * math.pi * k / sezioni
            anello.append(bm.verts.new(p + nrm * (a * math.cos(th)) + bnr * (b * math.sin(th))))
        anelli.append(anello)
    for i in range(n - 1):
        for k in range(sezioni):
            k2 = (k + 1) % sezioni
            bm.faces.new((anelli[i][k], anelli[i][k2], anelli[i + 1][k2], anelli[i + 1][k]))
    bm.faces.new(list(reversed(anelli[0])))
    bm.faces.new(anelli[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return nuovo_oggetto(nome, bm, collection or bpy.context.scene.collection)


def primitivo(tipo: str, nome: str, collection, **kw):
    op = {
        "cylinder": bpy.ops.mesh.primitive_cylinder_add,
        "cube": bpy.ops.mesh.primitive_cube_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
    }[tipo]
    op(**kw)
    ob = bpy.context.object
    ob.name = nome
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def cubo(nome, dimensioni, collection, posizione=(0, 0, 0), rotazione=(0, 0, 0)):
    """Parallelepipedo con dimensioni piene (non scale) già applicate."""
    ob = primitivo("cube", nome, collection, size=1.0)
    ob.scale = dimensioni
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.location = posizione
    ob.rotation_euler = rotazione
    return ob


def applica_modificatori(ob) -> None:
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError:
            ob.modifiers.remove(m)


def smussa(ob, larghezza: float, segmenti: int = 2, angolo_deg: float = 40.0) -> None:
    """Modificatore bevel applicato: spigoli più realistici."""
    mod = ob.modifiers.new("Smusso", "BEVEL")
    mod.width = larghezza
    mod.segments = segmenti
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angolo_deg)
    applica_modificatori(ob)


def shade(obj, angolo_deg: float = 35.0) -> None:
    """Sfuma le facce e marca netti gli spigoli oltre l'angolo indicato."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    ang = math.radians(angolo_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) <= ang
        else:
            e.smooth = True
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True


# --------------------------------------------------------------------------- #
#  MATERIALI
# --------------------------------------------------------------------------- #

def materiale(nome, base, metallic=0.0, roughness=0.4, transmission=0.0,
              ior=1.45, emissione=None, emissione_forza=1.0, bump=0.0,
              bump_scala=140.0, alpha=1.0):
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, alpha if alpha < 1 else 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = ior
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if emissione is not None:
        bsdf.inputs["Emission Color"].default_value = (*emissione, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emissione_forza
    if alpha < 1.0:
        mat.blend_method = "BLEND"
    if bump > 0.0:
        # micro-rilievo "buccia d'arancia" tipico delle plastiche stampate
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = bump_scala
        noise.inputs["Detail"].default_value = 2.0
        noise.location = (-560, -260)
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        bmp.inputs["Distance"].default_value = 0.0006
        bmp.location = (-300, -260)
        nt.links.new(noise.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def crea_materiali() -> dict:
    return {
        "corpo": materiale("Acciaio_Spazzolato", (0.620, 0.630, 0.645), metallic=0.85,
                           roughness=0.30, bump=0.22, bump_scala=320.0),
        "plastica": materiale("Plastica_Chiara", (0.700, 0.712, 0.730), metallic=0.0,
                              roughness=0.34, bump=0.12),
        "scuro": materiale("Plastica_Nera", (0.028, 0.029, 0.032), roughness=0.36,
                           bump=0.12),
        "gomma": materiale("Gomma_Nera", (0.014, 0.014, 0.016), roughness=0.75),
        "vetro": materiale("Vetro_Brocca", (0.94, 0.97, 0.98), roughness=0.015,
                           transmission=1.0, ior=1.46),
        "vetro_tappo": materiale("Vetro_Tappo", (0.90, 0.94, 0.98), roughness=0.04,
                                 transmission=1.0, ior=1.5),
        "acciaio": materiale("Acciaio_Inox", (0.910, 0.918, 0.928), metallic=1.0,
                             roughness=0.14),
        "display": materiale("Display_LED", (0.02, 0.03, 0.04), roughness=0.12,
                             emissione=(0.35, 0.72, 1.0), emissione_forza=5.0),
    }


# --------------------------------------------------------------------------- #
#  PEZZI DEL MODELLO
# --------------------------------------------------------------------------- #

def corpo_motore(coll, mat):
    """Base del frullatore con piedini, collare di alloggiamento e feritoie."""
    profilo = [
        (0.0000, 0.0030),
        (0.0420, 0.0000),
        (0.0640, 0.0000),
        (0.0700, 0.0022),
        (0.0780, 0.0065),
        (0.0830, 0.0140),
        (0.0865, 0.0290),
        (0.0880, 0.0480),
        (0.0875, 0.0680),
        (0.0855, 0.0890),
        (0.0820, 0.1080),
        (0.0770, 0.1260),
        (0.0710, 0.1400),
        (0.0645, 0.1500),
        (0.0600, 0.1565),
        (0.0585, 0.1610),
        (0.0592, 0.1660),
        (0.0590, 0.1750),   # bordo superiore del collare
        (0.0530, 0.1752),
        (0.0525, 0.1680),   # parete interna del collare
        (0.0520, 0.1590),
        (0.0440, 0.1550),   # fondo della sede
        (0.0200, 0.1542),
        (0.0000, 0.1540),
    ]
    base = rivoluziona(profilo, "Corpo_Motore", collection=coll)
    base.data.materials.append(mat["corpo"])
    smussa(base, 0.0018, 2, 30)
    shade(base, 30.0)

    # feritoia di aerazione: fascia scura incassata sul fianco
    anello = rivoluziona(
        [(0.0864, 0.0430), (0.0873, 0.0458), (0.0873, 0.0542), (0.0864, 0.0570)],
        "Feritoia_Aria", collection=coll,
    )
    anello.data.materials.append(mat["scuro"])
    shade(anello, 25.0)

    # piedini in gomma
    for i in range(4):
        th = math.radians(45 + 90 * i)
        p = primitivo("cylinder", f"Piedino_{i+1}", coll, vertices=24, radius=0.0100,
                      depth=0.0040,
                      location=(0.055 * math.cos(th), 0.055 * math.sin(th), 0.0020))
        p.data.materials.append(mat["gomma"])
    return base


def pannello_comandi(coll, mat):
    """Pannello inclinato con display, manopola e tre pulsanti."""
    pezzi = []

    # --- guscio del pannello: settore che sporge dal corpo, inclinato ---
    M = (Matrix.Translation(Vector((0.0, -0.0805, 0.1015)))
         @ Matrix.Rotation(math.radians(-12.0), 4, "X"))

    def posto(obj, locale, rot=(0, 0, 0)):
        obj.matrix_world = (M @ Matrix.Translation(Vector(locale))
                            @ Euler(rot, "XYZ").to_matrix().to_4x4())

    guscio = cubo("Pannello", (0.0600, 0.0280, 0.0620), coll)
    posto(guscio, (0.0, 0.0080, 0.0))
    guscio.data.materials.append(mat["plastica"])
    smussa(guscio, 0.0105, 4, 30)
    shade(guscio, 30.0)
    pezzi.append(guscio)

    # --- display ---
    display = cubo("Display", (0.0300, 0.0030, 0.0135), coll)
    posto(display, (0.0, -0.0115, 0.0190))
    display.data.materials.append(mat["display"])
    smussa(display, 0.0020, 2, 30)
    shade(display, 30.0)
    pezzi.append(display)

    # --- manopola con tacca ---
    manopola = primitivo("cylinder", "Manopola", coll, vertices=64, radius=0.0148,
                         depth=0.0170, rotation=(math.pi / 2, 0, 0))
    posto(manopola, (-0.0345, -0.0130, -0.0130))
    manopola.data.materials.append(mat["scuro"])
    smussa(manopola, 0.0026, 3, 35)
    shade(manopola, 35.0)
    pezzi.append(manopola)

    tacca = cubo("Tacca_Manopola", (0.0022, 0.0030, 0.0090), coll)
    posto(tacca, (-0.0345, -0.0212, -0.0085))
    tacca.data.materials.append(mat["plastica"])
    shade(tacca, 35.0)
    pezzi.append(tacca)

    # --- pulsanti ---
    for i, x in enumerate((0.0090, 0.0280, 0.0470)):
        p = primitivo("cylinder", f"Pulsante_{i+1}", coll, vertices=32, radius=0.0058,
                      depth=0.0050, rotation=(math.pi / 2, 0, 0))
        posto(p, (x, -0.0135, -0.0130))
        p.data.materials.append(mat["scuro"])
        smussa(p, 0.0012, 2, 35)
        shade(p, 35.0)
        pezzi.append(p)
    return pezzi


def brocca(coll, mat):
    """Brocca in vetro: profilo cavo, beccuccio frontale e manico laterale."""
    profilo = [
        (0.0000, 0.0000),
        (0.0450, 0.0000),   # fondo della brocca (giunto)
        (0.0490, 0.0040),
        (0.0505, 0.0120),
        (0.0510, 0.0190),   # gonna che entra nel collare
        (0.0560, 0.0225),   # flangia che appoggia sul bordo del collare
        (0.0575, 0.0270),
        (0.0585, 0.0330),
        (0.0620, 0.0500),
        (0.0670, 0.0850),
        (0.0715, 0.1250),
        (0.0760, 0.1650),
        (0.0790, 0.2000),
        (Dim.BROCCA_R_MAX, 0.2280),
        (0.0800, 0.2420),
        (0.0785, 0.2450),   # bordo esterno della bocca
        (0.0742, 0.2455),
        (0.0728, 0.2420),   # labbro interno
        (0.0728, 0.2280),
        (0.0745, 0.2000),
        (0.0715, 0.1650),
        (0.0670, 0.1250),
        (0.0620, 0.0850),
        (0.0585, 0.0500),
        (0.0552, 0.0330),
        (0.0522, 0.0270),
        (0.0492, 0.0225),   # parete interna della flangia
        (0.0455, 0.0190),
        (0.0445, 0.0120),
        (0.0430, 0.0040),
        (0.0000, 0.0030),
    ]
    ob = rivoluziona(profilo, "Brocca", collection=coll)
    ob.location.z = Dim.BROCCA_Z0
    ob.data.materials.append(mat["vetro"])

    # --- beccuccio: deformazione dolce della parete frontale (-Y) ---
    z_lo, z_hi = Dim.BROCCA_H - Dim.BECC_H, Dim.BROCCA_H
    for v in ob.data.vertices:
        z = v.co.z
        if not (z_lo < z < z_hi) or v.co.y >= 0.0:
            continue
        wz = math.sin(math.pi * (z - z_lo) / (z_hi - z_lo)) ** 0.85
        wy = min(1.0, (-v.co.y) / 0.038) ** 1.8
        # il beccuccio agisce sul bordo: peso crescente verso la bocca
        wr = min(1.0, max(0.0, (v.co.x ** 2 + v.co.y ** 2) ** 0.5 - 0.055) / 0.025)
        peso = wz * wy * (0.35 + 0.65 * wr)
        v.co.y -= Dim.BECC_SPORTE * peso
        v.co.x *= 1.0 + 0.045 * peso
    ob.data.update()

    ob.data.update()

    # --- manico: ansa laterale (+X) che si fonde nella parete ---
    tavola = [(0.000, 0.0450), (0.019, 0.0510), (0.027, 0.0575), (0.033, 0.0585),
              (0.050, 0.0620), (0.085, 0.0670), (0.125, 0.0715), (0.165, 0.0760),
              (0.200, 0.0790), (0.228, 0.0802), (0.245, 0.0790)]

    def raggio_brocca(z):
        for (z0, r0), (z1, r1) in zip(tavola, tavola[1:]):
            if z0 <= z <= z1:
                t = (z - z0) / (z1 - z0)
                return r0 + (r1 - r0) * t
        return tavola[-1][1]

    percorso, raggi = [], []
    passi = 34
    for i in range(passi):
        t = i / (passi - 1)
        z = 0.0500 + t * 0.1870
        x = raggio_brocca(z) - 0.0055 + Dim.MANICO_BULGE * math.sin(math.pi * t) ** 1.05
        percorso.append((x, 0.0, z))
        raggi.append(0.0115 + 0.0036 * math.sin(math.pi * t))
    manico = tubo(percorso, raggi, "Manico", sezioni=22, ellittico=(1.0, 0.70),
                  collection=coll)
    manico.location.z = Dim.BROCCA_Z0
    manico.data.materials.append(mat["vetro"])
    shade(manico, 40.0)
    return ob


def gruppo_lame(coll, mat):
    """Albero, mozzo, dado e quattro lame inclinate in acciaio."""
    pezzi = []
    z = Dim.GRUPPO_LAME_Z

    albero = primitivo("cylinder", "Albero", coll, vertices=24, radius=0.0046,
                       depth=0.0500, location=(0, 0, Dim.BROCCA_Z0 + 0.0470))
    albero.data.materials.append(mat["acciaio"])
    shade(albero, 40.0)
    pezzi.append(albero)

    mozzo = rivoluziona(
        [(0.0000, 0.0000), (0.0118, 0.0000), (0.0132, 0.0028), (0.0132, 0.0098),
         (0.0112, 0.0126), (0.0000, 0.0126)],
        "Mozzo_Lame", collection=coll,
    )
    mozzo.location.z = z - 0.0105
    mozzo.data.materials.append(mat["acciaio"])
    shade(mozzo, 40.0)
    pezzi.append(mozzo)

    dado = primitivo("cylinder", "Dado_Lame", coll, vertices=6, radius=0.0076,
                     depth=0.0064, location=(0, 0, z + 0.0052))
    dado.data.materials.append(mat["acciaio"])
    shade(dado, 20.0)
    pezzi.append(dado)

    # guarnizione di tenuta sotto la brocca
    guar = primitivo("torus", "Guarnizione_Vetro", coll, major_radius=0.0480,
                     minor_radius=0.0038, major_segments=64, minor_segments=12,
                     location=(0, 0, Dim.BROCCA_Z0 + 0.0050))
    guar.data.materials.append(mat["gomma"])
    shade(guar, 60.0)
    pezzi.append(guar)

    def lama(nome, lunghezza, larghezza, angolo_z):
        bm = bmesh.new()
        pts2d = [
            (0.0110, -0.0068),
            (lunghezza * 0.45, -0.0100),
            (lunghezza * 0.92, -larghezza * 0.60),
            (lunghezza, -larghezza * 0.20),
            (lunghezza, larghezza * 0.20),
            (lunghezza * 0.92, larghezza * 0.68),
            (lunghezza * 0.45, 0.0092),
            (0.0110, 0.0062),
        ]
        vs = [bm.verts.new((x, y, 0.0)) for x, y in pts2d]
        bm.faces.new(vs)
        res = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        vs_new = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=vs_new, vec=(0.0, 0.0, Dim.LAMA_SPESSORE))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        ob = nuovo_oggetto(nome, bm, coll)
        ob.matrix_world = (Matrix.Translation(Vector((0.0, 0.0, z + Dim.BROCCA_Z0 - 0.155)))
                           @ Matrix.Rotation(angolo_z, 4, "Z")
                           @ Matrix.Rotation(math.radians(Dim.LAMA_PASSO_DEG), 4, "X"))
        ob.data.materials.append(mat["acciaio"])
        shade(ob, 30.0)
        pezzi.append(ob)

    lama("Lama_1", Dim.LAMA_LUNGA, 0.0150, 0.0)
    lama("Lama_2", Dim.LAMA_LUNGA, 0.0150, math.pi)
    lama("Lama_3", Dim.LAMA_CORTA, 0.0140, math.pi / 2)
    lama("Lama_4", Dim.LAMA_CORTA, 0.0140, -math.pi / 2)
    return pezzi


def coperchio(coll, mat):
    """Coperchio con bordo di tenuta e tappo dosatore trasparente."""
    pezzi = []
    # guscio a capsula: gonna che abbraccia il bordo della brocca + cupola
    # con foro centrale per il tappo dosatore.  Il profilo è un anello chiuso
    # con raggio sempre >= 0 (vincolo delle superfici di rivoluzione).
    profilo = [
        # bordo di tenuta (gonna) + cupola con foro centrale per il tappo
        (0.0840, -0.0210),
        (0.0846, -0.0125),
        (0.0843, -0.0055),
        (0.0838, 0.0000),
        (0.0780, 0.0045),
        (0.0700, 0.0072),
        (0.0600, 0.0102),
        (0.0500, 0.0128),
        (0.0400, 0.0146),
        (0.0300, 0.0158),
        (0.0190, 0.0166),
        (0.0145, 0.0168),   # bordo del foro
        # superficie interna, di ritorno verso la gonna
        (0.0145, 0.0136),
        (0.0250, 0.0129),
        (0.0350, 0.0119),
        (0.0450, 0.0105),
        (0.0550, 0.0087),
        (0.0640, 0.0065),
        (0.0710, 0.0041),
        (0.0760, 0.0011),
        (0.0790, -0.0025),
        (0.0805, -0.0080),
        (0.0810, -0.0210),
        (0.0840, -0.0210),  # chiusura dell'anello
    ]
    ob = rivoluziona(profilo, "Coperchio", collection=coll)
    ob.location.z = Dim.COPERCHIO_Z0
    ob.data.materials.append(mat["scuro"])
    smussa(ob, 0.0012, 2, 35)
    shade(ob, 35.0)
    pezzi.append(ob)

    tappo = rivoluziona(
        [(0.0000, 0.0000), (0.0122, 0.0000), (0.0130, 0.0035), (0.0152, 0.0055),
         (0.0208, 0.0072), (0.0208, 0.0128), (0.0196, 0.0152), (0.0000, 0.0154)],
        "Tappo_Dosatore", collection=coll,
    )
    tappo.location.z = Dim.COPERCHIO_Z0 + 0.0125
    tappo.data.materials.append(mat["vetro_tappo"])
    shade(tappo, 35.0)
    pezzi.append(tappo)

    ling = cubo("Linguetta_Tappo", (0.0115, 0.0235, 0.0038), coll,
                posizione=(0.0, 0.0252, Dim.COPERCHIO_Z0 + 0.0240),
                rotazione=(math.radians(9.0), 0.0, 0.0))
    ling.data.materials.append(mat["vetro_tappo"])
    smussa(ling, 0.0016, 2, 35)
    shade(ling, 35.0)
    pezzi.append(ling)
    return pezzi


# --------------------------------------------------------------------------- #
#  SCENA DA STUDIO
# --------------------------------------------------------------------------- #

def studio(coll):
    """Ciclorama fotografico + schema luci a tre punti + softbox dall'alto."""
    prof = [(-1.80, 0.0), (0.30, 0.0), (0.95, 0.02), (1.15, 0.40),
            (1.22, 1.20), (1.24, 2.80)]
    bm = bmesh.new()
    vs = [bm.verts.new((-2.60, y, z)) for y, z in prof]
    vs2 = [bm.verts.new((2.60, y, z)) for y, z in prof]
    for i in range(len(prof) - 1):
        bm.faces.new((vs[i], vs[i + 1], vs2[i + 1], vs2[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cic = nuovo_oggetto("Ciclorama", bm, coll)
    cic.data.materials.append(materiale("Studio_Bianco", (0.88, 0.885, 0.89),
                                        roughness=0.5))

    def area(nome, loc, energia, size, bersaglio=(0.0, 0.0, 0.22), forma="RECTANGLE"):
        lt = bpy.data.lights.new(nome, "AREA")
        lt.energy = energia
        lt.shape = forma
        if forma == "RECTANGLE":
            lt.size, lt.size_y = size
        else:
            lt.size = size
        ob = bpy.data.objects.new(nome, lt)
        coll.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(bersaglio) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    area("Luce_Chiave", (1.50, -1.60, 1.70), 430.0, (1.60, 1.60))
    area("Luce_Riempimento", (-2.30, -1.45, 0.90), 70.0, (2.20, 2.20))
    area("Luce_Contro", (-0.70, 1.95, 1.50), 430.0, (0.9, 1.8))
    area("Softbox_Alto", (0.20, -0.40, 2.20), 60.0, (1.20, 1.20))

    mondo = bpy.data.worlds.new("Studio")
    bpy.context.scene.world = mondo
    mondo.use_nodes = True
    bg = mondo.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.42, 0.44, 0.49, 1.0)
    bg.inputs["Strength"].default_value = 0.22


def camera_modello(coll):
    cam_data = bpy.data.cameras.new("Camera_Hero")
    cam_data.lens = 80.0
    cam = bpy.data.objects.new("Camera_Hero", cam_data)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def posiziona_camera(cam, azimut_deg, elev_deg, distanza, bersaglio=(0.0, 0.0, 0.215),
                     lens=None):
    if lens:
        cam.data.lens = lens
    az, el = math.radians(azimut_deg), math.radians(elev_deg)
    b = Vector(bersaglio)
    cam.location = b + Vector((
        distanza * math.cos(el) * math.sin(az),
        -distanza * math.cos(el) * math.cos(az),
        distanza * math.sin(el),
    ))
    cam.rotation_euler = (b - cam.location).to_track_quat("-Z", "Y").to_euler()


def configura_render(risoluzione, campioni: int, trasparente=False) -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = campioni
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.01
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.max_bounces = 10
    sc.cycles.transmission_bounces = 12
    sc.cycles.transparent_max_bounces = 12
    sc.cycles.caustics_refractive = False
    sc.render.resolution_x, sc.render.resolution_y = risoluzione
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = trasparente
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 70
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Punchy", "AgX - Medium High Contrast", "Punchy"):
        try:
            sc.view_settings.look = look
            break
        except TypeError:
            continue
    sc.view_settings.exposure = 0.0


def rendi(percorso: str, risoluzione, campioni: int) -> None:
    sc = bpy.context.scene
    sc.render.filepath = percorso
    print(f"→ rendering {percorso} ({risoluzione[0]}x{risoluzione[1]}, {campioni} campioni)")
    bpy.ops.render.render(write_still=True)


# --------------------------------------------------------------------------- #
#  MAIN
# --------------------------------------------------------------------------- #

def costruisci():
    pulisci_scena()
    scena = bpy.context.scene
    scena.unit_settings.system = "METRIC"
    scena.unit_settings.scale_length = 1.0

    coll_modello = bpy.data.collections.new("Frullatore")
    scena.collection.children.link(coll_modello)

    mat = crea_materiali()
    corpo_motore(coll_modello, mat)
    pannello_comandi(coll_modello, mat)
    brocca(coll_modello, mat)
    gruppo_lame(coll_modello, mat)
    coperchio(coll_modello, mat)
    return coll_modello


def salva_blend(cartella_modelli: Path) -> None:
    """Salva il file nativo Blender (modello + studio luci + camera)."""
    cartella_modelli.mkdir(parents=True, exist_ok=True)
    blend = cartella_modelli / "frullatore.blend"
    preferenze = bpy.context.preferences.filepaths
    preferenze.save_version = 0            # niente copie .blend1
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    print(f"✓ salvato {blend}")


def esporta_glb(cartella_modelli: Path, coll_modello) -> None:
    """Esporta solo le mesh del modello in un unico GLB."""
    cartella_modelli.mkdir(parents=True, exist_ok=True)
    glb = cartella_modelli / "frullatore.glb"
    bpy.ops.object.select_all(action="DESELECT")
    for ob in coll_modello.objects:
        if ob.type == "MESH":
            ob.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(glb),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_texcoords=False,
        export_normals=True,
        export_materials="EXPORT",
    )
    print(f"✓ esportato {glb}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Genera il modello 3D di un frullatore.")
    p.add_argument("--render", action="store_true", help="esegue anche i rendering Cycles")
    p.add_argument("--campioni", type=int, default=128, help="campioni Cycles (default 128)")
    p.add_argument("--risoluzione", type=int, nargs=2, default=[820, 1040],
                   metavar=("L", "A"))
    p.add_argument("--solo-render", action="store_true",
                   help="salta l'export dei file")
    p.add_argument("--radice", type=str, default=None, help="cartella radice del progetto")
    args = p.parse_args(argv)

    radice = Path(args.radice) if args.radice else Path(__file__).resolve().parent.parent
    modelli = radice / "models"
    renders = radice / "renders"

    coll_modello = costruisci()

    # studio fotografico e camera fanno parte della scena salvata
    coll_scena = bpy.data.collections.new("Studio")
    bpy.context.scene.collection.children.link(coll_scena)
    studio(coll_scena)
    cam = camera_modello(coll_scena)
    posiziona_camera(cam, 38.0, 15.0, 1.52)
    configura_render(tuple(args.risoluzione), args.campioni)

    if not args.solo_render:
        salva_blend(modelli)
        esporta_glb(modelli, coll_modello)

    if args.render:
        renders.mkdir(parents=True, exist_ok=True)

        configura_render(tuple(args.risoluzione), args.campioni)
        posiziona_camera(cam, 38.0, 15.0, 1.52)
        rendi(str(renders / "hero_3-4.png"), tuple(args.risoluzione), args.campioni)

        quadrata = args.risoluzione[1]
        configura_render((quadrata, quadrata), args.campioni)
        posiziona_camera(cam, 24.0, 32.0, 0.90, bersaglio=(0.0, -0.04, 0.14), lens=66.0)
        rendi(str(renders / "dettaglio_comandi.png"), (quadrata, quadrata), args.campioni)

        orizz = int(args.risoluzione[0] * 0.80)
        configura_render((orizz, args.risoluzione[1]), args.campioni)
        posiziona_camera(cam, 0.0, 4.0, 1.48, lens=85.0)
        rendi(str(renders / "vista_frontale.png"), (orizz, args.risoluzione[1]),
              args.campioni)

    print("Fatto.")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None
    main(argv)
