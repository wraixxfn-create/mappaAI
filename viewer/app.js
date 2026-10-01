/**
 * app.js — viewer web del frullatore generato con Blender.
 *
 * Carica models/frullatore.glb con three.js, ricostruisce un piccolo studio
 * virtuale (ambiente, luci, piano d'appoggio con ombra) e offre i comandi di
 * rotazione automatica, vista esplosa e wireframe.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const PERCORSO_MODELLO = '../models/frullatore.glb';

/* ------------------------------------------------------------------ *
 *  Studio virtuale
 * ------------------------------------------------------------------ */

const contenitore = document.getElementById('scena');

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.92;
renderer.outputColorSpace = THREE.SRGBColorSpace;
contenitore.appendChild(renderer.domElement);

const scena = new THREE.Scene();
scena.background = new THREE.Color(0x0e1116);
scena.fog = new THREE.Fog(0x0e1116, 3.2, 7.5);

const camera = new THREE.PerspectiveCamera(38, window.innerWidth / window.innerHeight, 0.05, 40);
camera.position.set(0.62, 0.46, 0.78);

const controlli = new OrbitControls(camera, renderer.domElement);
controlli.target.set(0, 0.22, 0);
controlli.enableDamping = true;
controlli.dampingFactor = 0.06;
controlli.minDistance = 0.35;
controlli.maxDistance = 3.2;
controlli.maxPolarAngle = Math.PI * 0.52;
controlli.autoRotate = true;
controlli.autoRotateSpeed = 0.9;

// ambiente per riflessi e rifrazioni credibili
const pmrem = new THREE.PMREMGenerator(renderer);
scena.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scena.environmentIntensity = 0.85;

// luci: chiave, riempimento, controluce
const chiave = new THREE.DirectionalLight(0xffffff, 2.6);
chiave.position.set(1.4, 2.1, 1.6);
chiave.castShadow = true;
chiave.shadow.mapSize.set(2048, 2048);
chiave.shadow.camera.near = 0.5;
chiave.shadow.camera.far = 6;
chiave.shadow.camera.left = -1.1;
chiave.shadow.camera.right = 1.1;
chiave.shadow.camera.top = 1.1;
chiave.shadow.camera.bottom = -1.1;
chiave.shadow.bias = -0.0007;
chiave.shadow.radius = 2.5;
scena.add(chiave);

const riempimento = new THREE.DirectionalLight(0xbcd2ff, 0.5);
riempimento.position.set(-1.8, 0.9, 0.7);
scena.add(riempimento);

const controluce = new THREE.DirectionalLight(0xffe9d0, 1.4);
controluce.position.set(-0.8, 1.3, -1.9);
scena.add(controluce);

// piano d'appoggio
const piano = new THREE.Mesh(
  new THREE.CircleGeometry(6, 64),
  new THREE.MeshStandardMaterial({ color: 0x1a1f27, roughness: 0.62, metalness: 0.05 })
);
piano.rotation.x = -Math.PI / 2;
piano.receiveShadow = true;
scena.add(piano);

const griglia = new THREE.GridHelper(6, 60, 0x2b3442, 0x1e242e);
griglia.position.y = 0.0012;
griglia.material.transparent = true;
griglia.material.opacity = 0.55;
scena.add(griglia);

/* ------------------------------------------------------------------ *
 *  Vista esplosa: offset per ogni gruppo di pezzi
 * ------------------------------------------------------------------ */

const ESPLOSIONE = {
  Coperchio: [0, 0.20, 0],
  Tappo_Dosatore: [0, 0.30, 0],
  Linguetta_Tappo: [0, 0.30, 0],
  Brocca: [0, 0.13, 0],
  Manico: [0, 0.13, 0],
  Guarnizione_Vetro: [0, 0.05, 0],
  Dado_Lame: [0, 0.04, 0],
  Lama_1: [0, 0.015, 0],
  Lama_2: [0, 0.015, 0],
  Lama_3: [0, -0.015, 0],
  Lama_4: [0, -0.015, 0],
  Albero: [0, -0.03, 0],
  Mozzo_Lame: [0, -0.045, 0],
  Pannello: [0, -0.02, -0.05],
  Display: [0, -0.02, -0.075],
  Manopola: [0, -0.02, -0.085],
  Tacca_Manopola: [0, -0.02, -0.085],
  Pulsante_1: [0, -0.02, -0.075],
  Pulsante_2: [0, -0.02, -0.075],
  Pulsante_3: [0, -0.02, -0.075],
  Feritoia_Aria: [0, 0, -0.06],
};

/* ------------------------------------------------------------------ *
 *  Caricamento del modello
 * ------------------------------------------------------------------ */

const stato = document.getElementById('stato');
const avanzamento = document.getElementById('avanzamento');
const schermata = document.getElementById('caricamento');

const modello = new THREE.Group();
scena.add(modello);

/** @type {{oggetto: THREE.Object3D, base: THREE.Vector3, offset: THREE.Vector3, materiali: THREE.Material[]}[]} */
const pezzi = [];
let vertici = 0;
let triangoli = 0;
const nomiMateriali = new Set();

new GLTFLoader().load(
  PERCORSO_MODELLO,
  (gltf) => {
    const radice = gltf.scene;
    radice.traverse((nodo) => {
      if (!nodo.isMesh) return;
      nodo.castShadow = true;
      nodo.receiveShadow = true;
      const geometria = nodo.geometry;
      if (geometria) {
        vertici += geometria.attributes.position?.count ?? 0;
        triangoli += geometria.index ? geometria.index.count / 3 : 0;
      }
      const materiali = Array.isArray(nodo.material) ? nodo.material : [nodo.material];
      materiali.filter(Boolean).forEach((m) => {
        nomiMateriali.add(m.name || '(senza nome)');
        m.envMapIntensity = 1.0;
      });
      const offset = ESPLOSIONE[nodo.name];
      pezzi.push({
        oggetto: nodo,
        base: nodo.position.clone(),
        offset: new THREE.Vector3(...(offset ?? [0, 0, 0])),
        materiali,
      });
    });
    modello.add(radice);
    inquadra(radice);
    aggiornaStatistiche();
    schermata.classList.add('fine');
  },
  (evento) => {
    if (!evento.total) return;
    const perc = Math.round((evento.loaded / evento.total) * 100);
    avanzamento.style.width = `${perc}%`;
    stato.textContent = `caricamento del modello… ${perc}%`;
  },
  (errore) => {
    console.error(errore);
    stato.textContent = 'modello non caricato: avvia il server con "python3 tools/serve.py"';
  }
);

function inquadra(radice) {
  const box = new THREE.Box3().setFromObject(radice);
  const centro = box.getCenter(new THREE.Vector3());
  const altezza = box.max.y - box.min.y;
  radice.position.sub(new THREE.Vector3(centro.x, box.min.y, centro.z)); // appoggio a terra
  controlli.target.set(0, altezza * 0.5, 0);
  controlli.update();
}

function aggiornaStatistiche() {
  const box = new THREE.Box3().setFromObject(modello);
  const misura = box.getSize(new THREE.Vector3());
  const cm = (v) => (v * 100).toFixed(1);
  document.getElementById('d-ingombro').textContent =
    `${cm(misura.x)} × ${cm(misura.z)} × ${cm(misura.y)} cm`;
  document.getElementById('d-poligoni').textContent =
    triangoli.toLocaleString('it-IT', { maximumFractionDigits: 0 });
  document.getElementById('d-oggetti').textContent = pezzi.length.toString();
  document.getElementById('d-materiali').textContent =
    `${nomiMateriali.size} · ${vertici.toLocaleString('it-IT')} vertici`;
}

/* ------------------------------------------------------------------ *
 *  Comandi dell'interfaccia
 * ------------------------------------------------------------------ */

const bRuota = document.getElementById('b-ruota');
const bEsplosa = document.getElementById('b-esplosa');
const bWire = document.getElementById('b-wireframe');
const rEsplosione = document.getElementById('r-esplosione');

let fattoreEsplosione = 0;
let fattoreObiettivo = 0;
let wireframe = false;

const commuta = (bottone, valore) => bottone.setAttribute('aria-pressed', String(valore));

bRuota.addEventListener('click', () => {
  controlli.autoRotate = !controlli.autoRotate;
  commuta(bRuota, controlli.autoRotate);
});

bEsplosa.addEventListener('click', () => {
  const acceso = bEsplosa.getAttribute('aria-pressed') !== 'true';
  fattoreObiettivo = acceso ? 1 : 0;
  rEsplosione.value = acceso ? 100 : 0;
  commuta(bEsplosa, acceso);
});

rEsplosione.addEventListener('input', () => {
  fattoreObiettivo = Number(rEsplosione.value) / 100;
  commuta(bEsplosa, fattoreObiettivo > 0.02);
});

bWire.addEventListener('click', () => {
  wireframe = !wireframe;
  commuta(bWire, wireframe);
  pezzi.forEach(({ materiali }) =>
    materiali.filter(Boolean).forEach((m) => {
      if ('wireframe' in m) m.wireframe = wireframe;
    })
  );
});

/* ------------------------------------------------------------------ *
 *  Ciclo di rendering
 * ------------------------------------------------------------------ */

const orologio = new THREE.Clock();

renderer.setAnimationLoop(() => {
  const dt = Math.min(orologio.getDelta(), 0.05);

  // animazione morbida dell'esplosione
  fattoreEsplosione += (fattoreObiettivo - fattoreEsplosione) * Math.min(1, dt * 4.5);
  pezzi.forEach(({ oggetto, base, offset }) => {
    oggetto.position.copy(base).addScaledVector(offset, fattoreEsplosione);
  });

  controlli.update();
  renderer.render(scena, camera);
});

addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

renderer.domElement.addEventListener('dblclick', () => {
  controlli.target.set(0, 0.22, 0);
  camera.position.set(0.62, 0.46, 0.78);
  controlli.update();
});
