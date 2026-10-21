// Saros Depo - QR Kodlu Stok Yonetim Sistemi

let html5QrCode = null;
let currentMaterial = null;
let locations = [];
let audioContext = null;
let isTorchOn = false;

// Sesli geri bildirim (bip)
function playBeep() {
  try {
    if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioContext.createOscillator();
    const gain = audioContext.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, audioContext.currentTime); // A5
    gain.gain.setValueAtTime(0.15, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(audioContext.destination);
    osc.start();
    osc.stop(audioContext.currentTime + 0.15);
  } catch (e) {
    console.log("Audio not allowed yet:", e);
  }
}

// Bildirim tostu
function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.style.background = isError ? "#dc2626" : "#1e293b";
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3000);
}

// Sayfa / Tab Yonetimi
function switchView(viewName) {
  document.querySelectorAll(".view").forEach(el => el.classList.remove("active"));
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.add("active");
  window.scrollTo(0, 0);

  if (viewName === "dashboard") loadStats();
  if (viewName === "materials") loadMaterials();
}

// Stats Yukle
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    
    const elItems = document.getElementById("stat-total-items");
    const elQty = document.getElementById("stat-total-qty");
    const elBreakdown = document.getElementById("stat-qty-breakdown");
    const elLocs = document.getElementById("stat-total-locs");
    const elNoPhotos = document.getElementById("stat-no-photos");

    if (elItems) elItems.textContent = data.toplam_malzeme;
    if (elQty) elQty.textContent = (data.toplam_stok_miktari || 0).toLocaleString("tr-TR");
    if (elBreakdown) elBreakdown.textContent = `${(data.toplam_adet || 0).toLocaleString("tr-TR")} adet + ${data.toplam_metre || 0} m + ${data.toplam_litre || 0} lt`;
    if (elLocs) elLocs.textContent = data.toplam_lokasyon;
    if (elNoPhotos) elNoPhotos.textContent = data.fotografsiz_sayisi;
  } catch (e) {
    console.error("Stats error:", e);
  }
}

// Lokasyonlari Yukle
async function loadLocations() {
  try {
    const res = await fetch("/api/lokasyonlar");
    locations = await res.json();

    const selects = [
      document.getElementById("filter-location"),
      document.getElementById("new-material-location"),
      document.getElementById("edit-material-location"),
      document.getElementById("print-location")
    ];

    selects.forEach(sel => {
      if (!sel) return;
      const isFilter = sel.id === "filter-location" || sel.id === "print-location";
      sel.innerHTML = isFilter ? '<option value="">Tüm Lokasyonlar</option>' : '<option value="">-- Lokasyon Seçiniz --</option>';
      locations.forEach(l => {
        const opt = document.createElement("option");
        opt.value = l.id;
        opt.textContent = `${l.ad} (${l.malzeme_sayisi || 0})`;
        sel.appendChild(opt);
      });
    });
  } catch (e) {
    console.error("Locations error:", e);
  }
}

// --- QR SCANNER (KAMERA CANLI OKUMA) ---
async function startScanner() {
  const overlay = document.getElementById("scanner-overlay");
  overlay.classList.add("active");

  try {
    if (!html5QrCode) {
      html5QrCode = new Html5Qrcode("reader");
    }

    const config = {
      fps: 12,
      qrbox: (viewfinderWidth, viewfinderHeight) => {
        const edge = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.75);
        return { width: edge, height: edge };
      },
      aspectRatio: 1.0
    };

    // Arka kamerayi sec ve direkt baslat (dosya/galeri secici acilmaz)
    await html5QrCode.start(
      { facingMode: "environment" },
      config,
      onQrCodeSuccess,
      (err) => {} // scan frame errors are ignored
    );
  } catch (err) {
    console.error("Camera start error:", err);
    alert("Kamera açılamadı: " + (err.message || err) + "\n\nNot: Telefon tarayıcılarında kamera için HTTPS veya localhost zorunludur.");
    stopScanner();
  }
}

async function stopScanner() {
  const overlay = document.getElementById("scanner-overlay");
  overlay.classList.remove("active");
  isTorchOn = false;
  if (html5QrCode && html5QrCode.isScanning) {
    try {
      await html5QrCode.stop();
    } catch (e) {
      console.log("Stop error:", e);
    }
  }
}

async function toggleTorch() {
  if (!html5QrCode || !html5QrCode.isScanning) return;
  try {
    isTorchOn = !isTorchOn;
    await html5QrCode.applyVideoConstraints({
      advanced: [{ torch: isTorchOn }]
    });
    const btn = document.getElementById("btn-torch");
    btn.style.background = isTorchOn ? "#f59e0b" : "#334155";
  } catch (e) {
    showToast("Cihazınız fener kontrolünü desteklemiyor", true);
  }
}

function printCurrentLabel() {
  if (currentMaterial && currentMaterial.id) {
    window.open(`/api/malzemeler/${currentMaterial.id}/etiket.pdf`, "_blank");
  }
}

function printEditLabel() {
  if (editingMaterialId) {
    window.open(`/api/malzemeler/${editingMaterialId}/etiket.pdf`, "_blank");
  }
}

// --- CANLI KAMERA ILE FOTOGRAF CEKME MOTORU (0 DOSYA SECICI) ---
let cameraStream = null;
let currentPhotoBlob = null;
let photoCallback = null;
let newMaterialPhotoBlob = null;

async function openCameraCapture(callback) {
  photoCallback = callback;
  const modal = document.getElementById("camera-modal");
  modal.style.display = "flex";

  const video = document.getElementById("camera-stream");
  const previewImg = document.getElementById("camera-snapshot-preview");
  const controlsStream = document.getElementById("camera-controls-stream");
  const controlsPreview = document.getElementById("camera-controls-preview");

  video.style.display = "block";
  previewImg.style.display = "none";
  controlsStream.style.display = "flex";
  controlsPreview.style.display = "none";

  try {
    const constraints = {
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      },
      audio: false
    };
    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = cameraStream;
    await video.play();
  } catch (err) {
    console.error("Camera access error:", err);
    alert("Kameraya erişilemedi: " + (err.message || err) + "\n\nNot: Telefon tarayıcılarında kameranın açılması için HTTPS zorunludur.");
    closeCameraCapture();
  }
}

function takeSnapshot() {
  const video = document.getElementById("camera-stream");
  const canvas = document.getElementById("camera-canvas");
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob((blob) => {
    currentPhotoBlob = blob;
    const previewImg = document.getElementById("camera-snapshot-preview");
    previewImg.src = URL.createObjectURL(blob);

    video.style.display = "none";
    previewImg.style.display = "block";
    document.getElementById("camera-controls-stream").style.display = "none";
    document.getElementById("camera-controls-preview").style.display = "flex";
  }, "image/jpeg", 0.88);
}

function retakeSnapshot() {
  currentPhotoBlob = null;
  document.getElementById("camera-stream").style.display = "block";
  document.getElementById("camera-snapshot-preview").style.display = "none";
  document.getElementById("camera-controls-stream").style.display = "flex";
  document.getElementById("camera-controls-preview").style.display = "none";
}

function confirmSnapshot() {
  if (currentPhotoBlob && photoCallback) {
    photoCallback(currentPhotoBlob);
  }
  closeCameraCapture();
}

function closeCameraCapture() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }
  const modal = document.getElementById("camera-modal");
  if (modal) modal.style.display = "none";
  currentPhotoBlob = null;
  photoCallback = null;
}

// 1. Stok ekraninda fotograf cek (Dogrudan Canli Kamera)
function triggerStockPhotoUpload() {
  if (!currentMaterial) return;
  openCameraCapture(async (blob) => {
    showToast("Fotoğraf yükleniyor...");
    const formData = new FormData();
    formData.append("foto", blob, `stock_${Date.now()}.jpg`);

    try {
      const res = await fetch(`/api/malzemeler/${currentMaterial.id}/fotograf`, {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error("Fotoğraf yüklenemedi");

      showToast("Fotoğraf başarıyla kaydedildi!");
      fetchMaterialAndOpenStock(currentMaterial.qr_kod);
      loadStats();
    } catch (e) {
      showToast(e.message, true);
    }
  });
}

// 2. Duzenleme ekraninda fotograf cek (Dogrudan Canli Kamera)
function openCameraForEditMaterial() {
  if (!editingMaterialId) return;
  openCameraCapture(async (blob) => {
    showToast("Fotoğraf yükleniyor...");
    const formData = new FormData();
    formData.append("foto", blob, `edit_${Date.now()}.jpg`);

    try {
      const res = await fetch(`/api/malzemeler/${editingMaterialId}/fotograf`, {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error("Fotoğraf yüklenemedi");

      showToast("Fotoğraf başarıyla eklendi!");
      openEditModal(editingMaterialId);
      loadStats();
    } catch (e) {
      showToast(e.message, true);
    }
  });
}

// 3. Yeni Malzeme ekraninda fotograf cek (Dogrudan Canli Kamera)
function openCameraForNewMaterial() {
  openCameraCapture((blob) => {
    newMaterialPhotoBlob = blob;
    const previewBox = document.getElementById("new-mat-photo-preview-box");
    const promptBox = document.getElementById("new-mat-photo-prompt");
    const img = document.getElementById("new-mat-photo-img");

    if (previewBox && promptBox && img) {
      img.src = URL.createObjectURL(blob);
      previewBox.style.display = "block";
      promptBox.style.display = "none";
    }
    showToast("Fotoğraf hazırlandı!");
  });
}

function openEditModalFromStock() {
  if (currentMaterial && currentMaterial.id) {
    openEditModal(currentMaterial.id);
  }
}

async function onQrCodeSuccess(decodedText) {
  // Basarili okuma: titresim ve bip
  if (navigator.vibrate) navigator.vibrate(200);
  playBeep();
  await stopScanner();

  // URL ise kodu ayikla
  let code = decodedText.trim();
  if (code.includes("/m/")) {
    code = code.split("/m/").pop();
  }

  showToast(`QR Okundu: ${code}`);
  fetchMaterialAndOpenStock(code);
}

// Malzemeyi QR ile getirip Ekle/Dus ekranini ac
async function fetchMaterialAndOpenStock(qrCode) {
  try {
    const res = await fetch(`/api/malzemeler/qr/${encodeURIComponent(qrCode)}`);
    if (!res.ok) {
      if (res.status === 404) {
        const createNew = confirm(`'${qrCode}' kodlu malzeme bulunamadı.\n\nYeni malzeme olarak eklemek ister misiniz?`);
        if (createNew) {
          switchView("new");
          document.getElementById("new-material-name").focus();
        }
        return;
      }
      throw new Error("Malzeme getirilemedi");
    }

    currentMaterial = await res.json();
    renderStockView(currentMaterial);
    switchView("stock");
  } catch (e) {
    showToast(e.message || "Hata olustu", true);
  }
}

// Ekle / Dus ekranini render et
function renderStockView(m) {
  document.getElementById("stock-mat-title").textContent = m.ad;
  document.getElementById("stock-mat-code").textContent = m.qr_kod;
  document.getElementById("stock-mat-loc").textContent = `${m.lokasyon_adi} - Raf: ${m.raf_no || '-'}`;
  document.getElementById("stock-mat-brand").textContent = m.marka ? `Marka: ${m.marka}` : '';
  document.getElementById("stock-mat-desc").textContent = m.tip_aciklama || '';
  
  document.getElementById("stock-current-qty").textContent = m.miktar ?? 0;
  document.getElementById("stock-current-unit").textContent = m.birim || 'adet';

  // Fotoğraf
  const imgEl = document.getElementById("stock-mat-img");
  const noPhotoEl = document.getElementById("stock-mat-no-photo");
  const btnChangePhoto = document.getElementById("btn-change-photo");

  if (m.fotograflar && m.fotograflar.length > 0) {
    imgEl.src = `${m.fotograflar[0].dosya_yolu}?t=${Date.now()}`;
    imgEl.style.display = "block";
    if (noPhotoEl) noPhotoEl.style.display = "none";
    if (btnChangePhoto) btnChangePhoto.style.display = "block";
  } else {
    imgEl.src = "";
    imgEl.style.display = "none";
    if (noPhotoEl) noPhotoEl.style.display = "flex";
    if (btnChangePhoto) btnChangePhoto.style.display = "none";
  }

  // Input sifirla
  document.getElementById("stock-change-qty").value = 1;
  document.getElementById("stock-teslim-alan").value = "";
  document.getElementById("stock-teslim-eden").value = "";
  document.getElementById("stock-sebep").value = "";

  // Gecmis hareketler
  renderMovementHistory(m.hareketler || []);
}

function renderMovementHistory(moves) {
  const list = document.getElementById("stock-moves-list");
  list.innerHTML = "";
  if (moves.length === 0) {
    list.innerHTML = '<div style="font-size:0.8rem;color:#94a3b8;padding:8px 0;">Henüz hareket kaydı yok.</div>';
    return;
  }
  moves.forEach(mv => {
    const isGiris = mv.tip === "GIRIS";
    const div = document.createElement("div");
    div.style.cssText = "display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:0.82rem;";
    div.innerHTML = `
      <div>
        <span style="font-weight:700;color:${isGiris ? '#16a34a' : '#dc2626'}">${isGiris ? '+ Giriş' : '- Çıkış'}: ${mv.miktar}</span>
        <span style="color:#64748b;margin-left:6px;">(${mv.sebep || 'Sebep yok'})</span>
        <div style="font-size:0.72rem;color:#94a3b8;">${mv.tarih ? mv.tarih.substring(0, 16) : ''} | Alan: ${mv.teslim_alan || '-'}</div>
      </div>
      <div style="font-weight:700;color:#334155;">Son: ${mv.sonraki_miktar}</div>
    `;
    list.appendChild(div);
  });
}

// Stok Miktar Butonlari (+/- 1, 5, 10)
function adjustStockInput(delta) {
  const inp = document.getElementById("stock-change-qty");
  let val = parseFloat(inp.value) || 0;
  val = Math.max(0.1, val + delta);
  inp.value = Number.isInteger(val) ? val : val.toFixed(1);
}

// Stok Hareketi Yap (GIRIS veya CIKIS)
async function submitStockChange(actionType) {
  if (!currentMaterial) return;

  const miktar = parseFloat(document.getElementById("stock-change-qty").value);
  if (!miktar || miktar <= 0) {
    showToast("Lütfen geçerli bir miktar giriniz", true);
    return;
  }

  const teslim_alan = document.getElementById("stock-teslim-alan").value.trim();
  const teslim_eden = document.getElementById("stock-teslim-eden").value.trim();
  const sebep = document.getElementById("stock-sebep").value.trim();

  try {
    const res = await fetch(`/api/malzemeler/${currentMaterial.id}/hareket`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tip: actionType,
        miktar: miktar,
        teslim_alan: teslim_alan,
        teslim_eden: teslim_eden,
        sebep: sebep,
        kullanici: "Saha"
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "İşlem başarısız");
    }

    showToast(actionType === "GIRIS" ? `+ ${miktar} ${data.birim} eklendi!` : `- ${miktar} ${data.birim} düşüldü!`);
    
    // Guncel bilgileri yeniden cek
    fetchMaterialAndOpenStock(currentMaterial.qr_kod);
  } catch (err) {
    showToast(err.message || "İşlem sırasında hata oluştu", true);
  }
}

// --- MALZEME LISTESI & DUZENLEME ---
let searchDebounce = null;
let onlyNoPhoto = false;

async function loadMaterials() {
  const q = document.getElementById("mat-search-input").value.trim();
  const locId = document.getElementById("filter-location").value;
  const listEl = document.getElementById("materials-list");
  listEl.innerHTML = '<div style="text-align:center;padding:30px;color:#94a3b8;">Yükleniyor...</div>';

  try {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (locId) params.set("lokasyon_id", locId);
    if (onlyNoPhoto) params.set("fotografsiz", "true");
    params.set("limit", "100");

    const res = await fetch(`/api/malzemeler?${params.toString()}`);
    const items = await res.json();

    if (items.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;padding:30px;color:#94a3b8;">Eşleşen malzeme bulunamadı.</div>';
      return;
    }

    listEl.innerHTML = "";
    items.forEach(m => {
      const card = document.createElement("div");
      card.className = "material-card";
      card.innerHTML = `
        <div class="material-thumb">
          ${m.foto_thumb ? `<img src="${m.foto_thumb}" style="width:100%;height:100%;object-fit:cover;border-radius:6px;">` : '📦'}
        </div>
        <div class="material-info" onclick="openEditModal(${m.id})">
          <div class="material-title">${m.ad}</div>
          <div class="material-sub">${m.lokasyon_adi} • Raf: ${m.raf_no || '-'}</div>
          <div class="material-sub" style="font-family:monospace;color:#2563eb;font-weight:600;">${m.qr_kod}</div>
        </div>
        <div class="material-qty">
          <div>${m.miktar} <span style="font-size:0.72rem;font-weight:normal;color:#64748b;">${m.birim}</span></div>
          <button class="btn btn-primary btn-sm" style="margin-top:4px;" onclick="fetchMaterialAndOpenStock('${m.qr_kod}')">İşlem</button>
        </div>
      `;
      listEl.appendChild(card);
    });
  } catch (e) {
    console.error("Load materials error:", e);
    listEl.innerHTML = '<div style="text-align:center;padding:20px;color:#dc2626;">Yükleme hatası!</div>';
  }
}

function toggleNoPhotoFilter(btn) {
  onlyNoPhoto = !onlyNoPhoto;
  btn.classList.toggle("active", onlyNoPhoto);
  loadMaterials();
}

function onSearchInput() {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadMaterials, 300);
}

// --- MALZEME DUZENLEME MODALI ---
let editingMaterialId = null;

async function openEditModal(matId) {
  editingMaterialId = matId;
  const modal = document.getElementById("edit-modal");
  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/malzemeler/${matId}`);
    const m = await res.json();

    document.getElementById("edit-material-name").value = m.ad || "";
    document.getElementById("edit-material-brand").value = m.marka || "";
    document.getElementById("edit-material-desc").value = m.tip_aciklama || "";
    document.getElementById("edit-material-location").value = m.lokasyon_id;
    document.getElementById("edit-material-rack").value = m.raf_no || "";
    document.getElementById("edit-material-unit").value = m.birim || "adet";
    document.getElementById("edit-material-shelf").value = m.raf_omru || "";
    document.getElementById("edit-material-yp").value = m.yp_kodu || "";

    // QR Goster
    document.getElementById("edit-qr-code").textContent = m.qr_kod;
    document.getElementById("edit-qr-img").src = `/api/qr/${m.qr_kod}.png`;

    // Fotograflar
    renderEditPhotos(m.fotograflar || []);
  } catch (e) {
    showToast("Detaylar alınamadı", true);
  }
}

function renderEditPhotos(photos) {
  const strip = document.getElementById("edit-photo-strip");
  strip.innerHTML = "";
  if (photos.length === 0) {
    strip.innerHTML = '<span style="font-size:0.8rem;color:#94a3b8;padding:8px 0;">Henüz fotoğraf yok. Aşağıdaki butondan çekebilirsiniz.</span>';
    return;
  }
  photos.forEach(f => {
    const wrapper = document.createElement("div");
    wrapper.style.position = "relative";
    wrapper.style.display = "inline-block";
    wrapper.innerHTML = `
      <img src="${f.kucuk_resim_yolu || f.dosya_yolu}" class="photo-item">
      <button onclick="deletePhoto(${f.id})" style="position:absolute;top:-4px;right:-4px;background:#dc2626;color:white;border:none;border-radius:50%;width:20px;height:20px;font-size:12px;cursor:pointer;">×</button>
    `;
    strip.appendChild(wrapper);
  });
}

function closeEditModal() {
  document.getElementById("edit-modal").style.display = "none";
}

// Duzenlemeyi Kaydet
async function saveMaterialEdit() {
  if (!editingMaterialId) return;

  const payload = {
    ad: document.getElementById("edit-material-name").value.trim(),
    marka: document.getElementById("edit-material-brand").value.trim() || null,
    tip_aciklama: document.getElementById("edit-material-desc").value.trim() || null,
    lokasyon_id: parseInt(document.getElementById("edit-material-location").value),
    raf_no: document.getElementById("edit-material-rack").value.trim() || null,
    birim: document.getElementById("edit-material-unit").value,
    raf_omru: document.getElementById("edit-material-shelf").value.trim() || null,
    yp_kodu: document.getElementById("edit-material-yp").value.trim() || null
  };

  if (!payload.ad || !payload.lokasyon_id) {
    showToast("Malzeme adı ve lokasyon zorunludur", true);
    return;
  }

  try {
    const res = await fetch(`/api/malzemeler/${editingMaterialId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Güncelleme başarısız");

    showToast("Malzeme güncellendi!");
    closeEditModal();
    loadMaterials();
    loadStats();
  } catch (e) {
    showToast(e.message, true);
  }
}

// Kameradan veya Dosyadan Fotograf Yukleme
async function uploadPhotoToMaterial(fileInput) {
  if (!editingMaterialId || !fileInput.files || fileInput.files.length === 0) return;

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("foto", file);

  showToast("Fotoğraf yükleniyor...");

  try {
    const res = await fetch(`/api/malzemeler/${editingMaterialId}/fotograf`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) throw new Error("Fotoğraf yüklenemedi");

    showToast("Fotoğraf eklendi!");
    fileInput.value = "";
    // Yeniden detay cek
    openEditModal(editingMaterialId);
    loadStats();
  } catch (e) {
    showToast(e.message, true);
  }
}

async function deletePhoto(photoId) {
  if (!confirm("Fotoğrafı silmek istediğinize emin misiniz?")) return;
  try {
    const res = await fetch(`/api/fotograflar/${photoId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Silinemedi");
    showToast("Fotoğraf silindi");
    openEditModal(editingMaterialId);
    loadStats();
  } catch (e) {
    showToast(e.message, true);
  }
}

// --- YENI MALZEME KAYDI ---
async function submitNewMaterial() {
  const form = document.getElementById("new-material-form");
  const formData = new FormData(form);

  const ad = formData.get("ad");
  const lokasyon = formData.get("lokasyon_id");

  if (!ad || !lokasyon) {
    showToast("Lütfen malzeme adı ve lokasyon seçiniz", true);
    return;
  }

  // Kamera ile cekilen fotografi ekle
  if (newMaterialPhotoBlob) {
    formData.append("foto", newMaterialPhotoBlob, "new_mat.jpg");
  }

  try {
    showToast("Kaydediliyor...");
    const res = await fetch("/api/malzemeler", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Kayıt başarısız");

    showToast(`Malzeme kaydedildi! QR: ${data.qr_kod}`);
    form.reset();

    // Fotograf kutusunu sifirla
    newMaterialPhotoBlob = null;
    const previewBox = document.getElementById("new-mat-photo-preview-box");
    const promptBox = document.getElementById("new-mat-photo-prompt");
    if (previewBox && promptBox) {
      previewBox.style.display = "none";
      promptBox.style.display = "block";
    }
    
    // Otomatik Ekle/Dus ekranini ac
    fetchMaterialAndOpenStock(data.qr_kod);
    loadStats();
  } catch (e) {
    showToast(e.message, true);
  }
}

// --- ETIKET YAZDIR ---
function downloadPdfLabels() {
  const locId = document.getElementById("print-location").value;
  let url = "/api/etiketler/pdf";
  if (locId) url += `?lokasyon_id=${locId}`;
  window.open(url, "_blank");
}

// Baslangic
window.addEventListener("DOMContentLoaded", () => {
  loadLocations();
  loadStats();

  // PWA Service Worker kaydi
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(err => {
      console.log("SW register failed:", err);
    });
  }

  // URL'de /m/{kod} ile gelinmisse direkt ac
  const path = window.location.pathname;
  if (path.startsWith("/m/")) {
    const code = path.replace("/m/", "").trim();
    if (code) fetchMaterialAndOpenStock(code);
  }
});
