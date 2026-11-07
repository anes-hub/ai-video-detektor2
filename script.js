const menuToggle = document.querySelector('.menu-toggle');
const navLinks = document.querySelector('.nav-links');
menuToggle.addEventListener('click', () => {
  const open = navLinks.classList.toggle('open');
  menuToggle.setAttribute('aria-expanded', String(open));
});
navLinks.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  navLinks.classList.remove('open');
  menuToggle.setAttribute('aria-expanded', 'false');
}));

document.getElementById('year').textContent = new Date().getFullYear();

const input = document.getElementById('videoInput');
const zone = document.getElementById('uploadZone');
const title = document.getElementById('uploadTitle');
const subtitle = document.getElementById('uploadSubtitle');
const fileRow = document.getElementById('fileRow');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const analyzeButton = document.getElementById('analyzeButton');
const demoResult = document.getElementById('demoResult');
let selectedFile = null;
const MAX_SIZE = 100 * 1024 * 1024;

function setFile(file) {
  demoResult.hidden = true;
  if (!file) return;
  if (!file.type.startsWith('video/')) {
    alert('Prosim izberi veljavno video datoteko.');
    return;
  }
  if (file.size > MAX_SIZE) {
    alert('Datoteka je večja od 100 MB. V predstavitvi je omejitev 100 MB.');
    return;
  }
  selectedFile = file;
  title.textContent = 'Video je izbran';
  subtitle.textContent = 'Datoteka je pripravljena za naslednji korak';
  fileName.textContent = file.name;
  fileSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
  fileRow.hidden = false;
  analyzeButton.disabled = false;
}
input.addEventListener('change', () => setFile(input.files[0]));
['dragenter', 'dragover'].forEach(eventName => zone.addEventListener(eventName, event => {
  event.preventDefault();
  zone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach(eventName => zone.addEventListener(eventName, event => {
  event.preventDefault();
  zone.classList.remove('dragover');
}));
zone.addEventListener('drop', event => setFile(event.dataTransfer.files[0]));
document.getElementById('removeFile').addEventListener('click', () => {
  selectedFile = null;
  input.value = '';
  fileRow.hidden = true;
  analyzeButton.disabled = true;
  demoResult.hidden = true;
  title.textContent = 'Povleci video sem';
  subtitle.textContent = 'ali klikni za izbiro datoteke iz naprave';
});

analyzeButton.addEventListener('click', async () => {
  if (!selectedFile) return;

  analyzeButton.disabled = true;
  analyzeButton.textContent = 'Analyzing video...';

  demoResult.hidden = false;
  demoResult.textContent = 'Video se trenutno analizira. Molimo sačekajte...';

  demoResult.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest'
  });

  try {
    const data = new FormData();
    data.append('file', selectedFile);

    const response = await fetch(
'https://ai-video-detektor2.onrender.com/api/analyze'
      method: 'POST',
        body: data
      }
    );

    const result = await response.json();

    if (!response.ok) {
  const errorMessage = typeof result.detail === 'string'
    ? result.detail
    : JSON.stringify(result.detail);

  throw new Error(errorMessage || 'Greška prilikom analize videa.');
}

    
const fakeResult = result.fake_result;

const isFake = fakeResult.label.toLowerCase() === 'fake';
const percentage = (fakeResult.score * 100).toFixed(2);


demoResult.innerHTML = `
  <div class="analysis-result">
    <div class="result-header">
      <h3>Analiza videoposnetka z umetno inteligenco</h3>
      <span class="complete-badge">● ANALIZA ZAKLJUČENA</span>
    </div>

    <div class="result-card">
      <p>Rezultat analize</p>

      <span class="result-badge ${isFake ? 'fake-badge' : 'real-badge'}">
        ${isFake ? 'PONAREJEN VIDEO' : 'PRAVI VIDEO'}
      </span>

      <div class="confidence">
        <strong>${percentage}%</strong>
        <span>Stopnja zaupanja modela</span>
      </div>

      <div class="confidence-bar">
        <div style="width: ${percentage}%"></div>
      </div>
    </div>

    <div class="analysis-details">
      <div>
        <span>Trajanje</span>
        <strong>${result.duration} sekunde</strong>
      </div>
      <div>
        <span>Ločljivost</span>
        <strong>${result.width} × ${result.height}</strong>
      </div>
      <div>
        <span>Število analiziranih sličic</span>
        <strong>${result.analyzed_frames}</strong>
      </div>
      <div>
        <span>Naprava</span>
        <strong>${result.device}</strong>
      </div>
    </div>

    <p class="result-disclaimer">
      Rezultat predstavlja napoved modela umetne inteligence
      in ni dokončen dokaz, da je videoposnetek ponarejen ali pristen.
    </p>
  </div>
`;



  } catch (error) {
    demoResult.textContent =
      'Došlo je do greške: ' + error.message;
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = 'Analyze video';
  }
});

