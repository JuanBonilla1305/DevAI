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
photo.addEventListener('change', async () => {
  const f = photo.files[0];
  fileName.textContent = f ? `${f.name} · ${(f.size / 1048576).toFixed(2)} MB` : '';
  const requestId = ++analysisRequest;

  if (!f) {
    photoAnalysis.classList.add('hidden');
    return;
  }

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
});

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
  const f = photo.files[0];
  if (!f) return alert('Selecciona una fotografía primero.');
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
