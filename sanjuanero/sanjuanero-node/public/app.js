const photo = document.getElementById('photo');
const fileName = document.getElementById('fileName');
const photoAnalysis = document.getElementById('photoAnalysis');
const strength = document.getElementById('strength');
const strengthValue = document.getElementById('strengthValue');
const generate = document.getElementById('generate');
const loading = document.getElementById('loading');
const result = document.getElementById('result');
const resultImage = document.getElementById('resultImage');
const download = document.getElementById('download');
const status = document.getElementById('status');
const costumeTitle = document.getElementById('costumeTitle');
const singleCostume = document.getElementById('singleCostume');
const pairCostume = document.getElementById('pairCostume');
let analysisRequest = 0;

// La foto activa. Puede venir del selector de archivos o de la cámara, y a
// partir de aquí el resto del flujo la trata igual.
let fotoActual = null;

const abrirCamara = document.getElementById('abrirCamara');
const camara = document.getElementById('camara');
const video = document.getElementById('video');
const camaraAviso = document.getElementById('camaraAviso');
const capturar = document.getElementById('capturar');
const cerrarCamara = document.getElementById('cerrarCamara');
const previsualizacion = document.getElementById('previsualizacion');
const previsualizacionImg = document.getElementById('previsualizacionImg');
const repetirFoto = document.getElementById('repetirFoto');

let flujo = null;

function detenerCamara() {
  if (flujo) {
    flujo.getTracks().forEach(pista => pista.stop());
    flujo = null;
  }
  video.srcObject = null;
  camara.classList.add('hidden');
}

abrirCamara.addEventListener('click', async () => {
  camara.classList.remove('hidden');
  camaraAviso.textContent = 'Pidiendo permiso para usar la cámara...';
  try {
    flujo = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: false
    });
    video.srcObject = flujo;
    camaraAviso.textContent = 'Colócate de frente, con luz en la cara.';
  } catch (error) {
    camaraAviso.textContent =
      'No se pudo abrir la cámara: ' + error.message +
      '. Comprueba que ninguna otra aplicación la esté usando.';
  }
});

cerrarCamara.addEventListener('click', detenerCamara);

capturar.addEventListener('click', () => {
  if (!video.videoWidth) {
    camaraAviso.textContent = 'La cámara todavía no da imagen, espera un momento.';
    return;
  }

  const lienzo = document.createElement('canvas');
  lienzo.width = video.videoWidth;
  lienzo.height = video.videoHeight;
  const contexto = lienzo.getContext('2d');

  // La vista previa va en espejo porque es más natural para encuadrarse, así
  // que aquí se invierte de vuelta: si no, la foto saldría del revés.
  contexto.translate(lienzo.width, 0);
  contexto.scale(-1, 1);
  contexto.drawImage(video, 0, 0);

  lienzo.toBlob(blob => {
    const archivo = new File([blob], 'camara.jpg', { type: 'image/jpeg' });
    detenerCamara();
    usarFoto(archivo);
  }, 'image/jpeg', 0.95);
});

repetirFoto.addEventListener('click', () => {
  previsualizacion.classList.add('hidden');
  fotoActual = null;
  photo.value = '';
  fileName.textContent = '';
  photoAnalysis.classList.add('hidden');
  abrirCamara.click();
});
let analyzingPhoto = false;

function syncCostumeMode() {
  const isPair = document.querySelector('input[name="peopleCount"]:checked').value === '2';
  costumeTitle.textContent = isPair ? '2. Composición y vestuario' : '2. Vestuario';
  singleCostume.classList.toggle('hidden', isPair);
  pairCostume.classList.toggle('hidden', !isPair);
}

document.querySelectorAll('input[name="peopleCount"]').forEach(
  input => input.addEventListener('change', syncCostumeMode)
);
syncCostumeMode();

strength.addEventListener('input', () => strengthValue.textContent = Number(strength.value).toFixed(2));
photo.addEventListener('change', () => usarFoto(photo.files[0]));

/** Fija la foto activa y lanza su análisis, venga de donde venga. */
async function usarFoto(f) {
  fotoActual = f || null;
  fileName.textContent = f ? `${f.name} · ${(f.size / 1048576).toFixed(2)} MB` : '';
  const requestId = ++analysisRequest;

  if (!f) {
    photoAnalysis.classList.add('hidden');
    previsualizacion.classList.add('hidden');
    return;
  }

  previsualizacionImg.src = URL.createObjectURL(f);
  previsualizacion.classList.remove('hidden');

  analyzingPhoto = true;
  generate.disabled = true;
  photoAnalysis.textContent = 'Analizando persona y rostro...';
  photoAnalysis.className = 'analysis pending';

  const form = new FormData();
  form.append('photo', f);

  try {
    const response = await fetch('/api/analyze-photo', {
      method: 'POST',
      body: form
    });
    const data = await response.json();

    if (requestId !== analysisRequest) return;
    if (!response.ok || !data.ok) {
      throw new Error(data.error || 'No se pudo analizar la foto.');
    }

    if (data.faceCount === 0) {
      photoAnalysis.textContent = 'No pude reconocer un rostro. Selecciona las opciones manualmente.';
      photoAnalysis.className = 'analysis warn';
      return;
    }

    const costume = document.querySelector(
      `input[name="costume"][value="${data.costume}"]`
    );
    const people = document.querySelector(
      `input[name="peopleCount"][value="${data.peopleCount === '2' ? '2' : '1'}"]`
    );

    if (costume) costume.checked = true;
    if (people) people.checked = true;
    syncCostumeMode();

    if (data.peopleCount === '2' && Array.isArray(data.people)) {
      const hasMinor = data.people.some(person => person.ageGroup !== 'adulto');
      const women = data.people.filter(person => person.gender === 'mujer').length;
      const detectedPairType = hasMinor
        ? 'adulto_nino'
        : women === 2
          ? 'dos_mujeres'
          : women === 0
            ? 'dos_hombres'
            : 'pareja_mixta';
      const pairType = document.querySelector(
        `input[name="pairType"][value="${detectedPairType}"]`
      );
      if (pairType) pairType.checked = true;
    }

    const detectedGender = data.costume === 'mujer' ? 'mujer' : 'hombre';
    const composition = Array.isArray(data.composition) && data.composition.length
      ? data.composition.join(' + ')
      : detectedGender;

    if (data.faceCount >= 2) {
      photoAnalysis.textContent = `Detecté ${data.faceCount} rostros principales: ${composition}. Se conservarán ambas identidades.`;
      photoAnalysis.className = 'analysis ok';
    } else {
      photoAnalysis.textContent = `Detectado automáticamente: ${composition} · una persona. Puedes corregir el vestuario manualmente.`;
      photoAnalysis.className = 'analysis ok';
    }
  } catch (error) {
    if (requestId !== analysisRequest) return;
    photoAnalysis.textContent = 'No pude analizar la foto. Selecciona las opciones manualmente.';
    photoAnalysis.className = 'analysis warn';
  } finally {
    if (requestId === analysisRequest) {
      analyzingPhoto = false;
      generate.disabled = false;
    }
  }
}

async function checkStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    if (d.fastsd) {
      status.textContent = 'FastSD instalado';
      status.className = 'badge ok';
    } else {
      status.textContent = 'FastSD no encontrado';
      status.className = 'badge err';
    }
  } catch {
    status.textContent = 'Servidor';
    status.className = 'badge err';
  }
}

async function generateImage() {
  const f = fotoActual;
  if (!f) return alert('Elige una fotografía o tómala con la cámara primero.');
  if (analyzingPhoto) return alert('Espera a que termine el análisis automático.');

  const form = new FormData();
  form.append('photo', f);
  form.append('costume', document.querySelector('input[name="costume"]:checked').value);
  form.append('peopleCount', document.querySelector('input[name="peopleCount"]:checked').value);
  form.append('pairType', document.querySelector('input[name="pairType"]:checked').value);
  form.append('strength', strength.value);

  generate.disabled = true;
  loading.classList.remove('hidden');
  result.classList.add('hidden');

  try {
    const r = await fetch('/api/generate', { method:'POST', body:form });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || 'No se pudo generar la imagen.');
    resultImage.src = d.image;
    download.href = d.image;
    result.classList.remove('hidden');
    result.scrollIntoView({behavior:'smooth'});
  } catch (e) {
    alert(e.message);
  } finally {
    generate.disabled = false;
    loading.classList.add('hidden');
  }
}

generate.addEventListener('click', generateImage);
checkStatus();
