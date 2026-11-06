/* MediTrust scanner. The decoder is served locally, without a CDN dependency. */
(function () {
  'use strict';

  var widget = document.querySelector('.scanner');
  if (!widget) return;

  var startButton     = document.getElementById('start');
  var stopButton      = document.getElementById('stop');
  var status          = document.getElementById('scan-status');
  var fileInput       = document.getElementById('qr-file');
  var scanImageButton = document.getElementById('scan-image');
  var imagePreview    = document.getElementById('qr-preview');
  var previewBox      = document.getElementById('qr-preview-box');
  var fileName        = document.getElementById('qr-file-name');
  var cameraSelect    = document.getElementById('camera');
  var cameraChoice    = document.getElementById('camera-choice');

  var previewUrl = null;
  var scanner    = null;
  var running    = false;
  var busy       = false;
  var navigating = false;
  var disposed   = false;
  var lastInvalid = 0;

  var mode = widget.dataset.mode || 'verify';

  function say(message) {
    if (status) status.textContent = message;
  }

  function controls() {
    if (startButton)     startButton.disabled     = busy || running || navigating;
    if (stopButton)      stopButton.disabled      = busy || !running;
    if (fileInput)       fileInput.disabled       = busy || navigating;
    if (scanImageButton) scanImageButton.disabled = busy || navigating || !(fileInput && fileInput.files && fileInput.files.length);
    if (cameraSelect)    cameraSelect.disabled    = busy;
  }

  function decoder() {
    if (!window.Html5Qrcode) {
      throw new Error('The scanner could not load. Reload this page or use the printed serial.');
    }
    if (!scanner) {
      scanner = new Html5Qrcode('reader', {
        formatsToSupport: [Html5QrcodeSupportedFormats.QR_CODE],
        verbose: false
      });
    }
    return scanner;
  }

  function destination(text) {
    text = text.trim();

    if (mode !== 'receive' && /^MT-[A-Z0-9]{10}$/i.test(text)) {
      return '/scan/?serial=' + encodeURIComponent(text.toUpperCase());
    }

    if (/^[a-f0-9]{32}$/i.test(text)) {
      if (mode === 'receive') {
        throw new Error('This carton QR has no signature. Use the batch-code form to check your assigned delivery.');
      }
      return '/verify/' + encodeURIComponent(text) + '/';
    }

    var url;
    try {
      url = new URL(text, location.origin);
    } catch (_) {
      throw new Error('This is not a recognised MediTrust QR.');
    }

    if (!/^https?:$/.test(url.protocol)) {
      throw new Error('Only MediTrust web links can be scanned here.');
    }

    var match = url.pathname.match(/^\/(verify|receive|pharmacy\/receive)\/([a-f0-9]{32})\/?$/i);
    if (!match) {
      throw new Error('This QR is not a medicine or carton code. Use the printed serial instead.');
    }

    var isBatch = match[1] !== 'verify';
    if (mode === 'receive' && !isBatch) {
      throw new Error('That is a medicine-strip QR. Scan the carton QR to receive a batch.');
    }

    var signature = url.searchParams.get('sig');
    if (signature && !/^[A-Za-z0-9_-]{43}$/.test(signature)) {
      throw new Error('The QR signature is malformed. Scan the original label.');
    }

    // Resolve known links on this trusted site, retaining the signature.
    // Never open an arbitrary scanned host.
    return (isBatch ? '/receive/' : '/verify/')
      + encodeURIComponent(match[2]) + '/'
      + (signature ? '?sig=' + encodeURIComponent(signature) : '');
  }

  async function stopCamera() {
    if (scanner && running) {
      try {
        await scanner.stop();
      } finally {
        running = false;
      }
    }
  }

  async function decoded(text) {
    if (navigating || disposed) return;

    var target;
    try {
      target = destination(text);
    } catch (error) {
      if (Date.now() - lastInvalid > 1500) {
        say(error.message);
        lastInvalid = Date.now();
      }
      return;
    }

    navigating = true;
    controls();
    say('QR recognised. Opening its record...');

    try {
      await stopCamera();
    } catch (_) {
      /* Navigation releases any remaining camera track. */
    }

    if (!disposed) location.assign(target);
  }

  function cameraError(error) {
    var text = String((error && (error.name || error.message)) || error);
    if (/NotAllowed|Permission|denied/i.test(text)) {
      return 'Camera permission was denied. Allow access in your browser settings, or choose a QR image below.';
    }
    if (/NotFound|DevicesNotFound|Overconstrained/i.test(text)) {
      return 'No usable camera was found. Connect a webcam or choose a QR image below.';
    }
    if (/NotReadable|TrackStart|in use/i.test(text)) {
      return 'The camera may be in use by another app. Close that app and try again, or choose a QR image.';
    }
    return 'The camera could not start. Check its permissions or choose a QR image below.';
  }

  async function startCamera(cameraId) {
    if (busy || running || navigating || disposed) return;

    if (!window.isSecureContext || !navigator.mediaDevices) {
      say('Your browser requires HTTPS or localhost for live camera access. You can still choose a QR image or type the printed serial.');
      return;
    }

    busy = true;
    controls();
    say('Starting camera. Allow access if your browser asks.');

    try {
      var qr = decoder();
      var config = {
        fps: 10,
        qrbox: function (width, height) {
          var size = Math.floor(Math.min(width, height) * 0.7);
          return { width: size, height: size };
        }
      };

      try {
        await qr.start(cameraId || { facingMode: 'environment' }, config, decoded);
      } catch (error) {
        if (cameraId || /NotAllowed|Permission|denied/i.test(String(error))) throw error;
        await qr.start({ facingMode: 'user' }, config, decoded);
      }

      running = true;

      if (disposed) {
        await stopCamera();
        return;
      }

      say('Camera is on. Hold the QR code inside the frame.');

      try {
        var cameras = await Html5Qrcode.getCameras();
        if (cameraSelect && cameraChoice) {
          cameraSelect.replaceChildren();
          cameras.forEach(function (camera, i) {
            var option = new Option(camera.label || ('Camera ' + (i + 1)), camera.id);
            cameraSelect.add(option);
          });
          if (cameraId) cameraSelect.value = cameraId;
          cameraChoice.hidden = cameras.length < 2;
        }
      } catch (_) {
        /* Scanning continues if device labels are unavailable. */
      }
    } catch (error) {
      say(error.message && /scanner could not load/i.test(error.message)
        ? error.message
        : cameraError(error));
    } finally {
      busy = false;
      controls();
    }
  }

  if (startButton) {
    startButton.addEventListener('click', function () {
      startCamera();
    });
  }

  if (stopButton) {
    stopButton.addEventListener('click', async function () {
      if (busy) return;
      busy = true;
      controls();
      try {
        await stopCamera();
        say('Camera stopped. You can start it again or choose an image.');
      } catch (_) {
        say('Camera stopped. Reload the page if its indicator remains on.');
      } finally {
        busy = false;
        controls();
      }
    });
  }

  if (cameraSelect) {
    cameraSelect.addEventListener('change', async function () {
      var id = cameraSelect.value;
      if (busy) return;
      busy = true;
      controls();
      try {
        await stopCamera();
      } finally {
        busy = false;
      }
      startCamera(id);
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];

      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
      }

      if (previewBox) previewBox.hidden = !file;

      if (file) {
        if (imagePreview) {
          previewUrl = URL.createObjectURL(file);
          imagePreview.src = previewUrl;
        }
        if (fileName) fileName.textContent = file.name;
        say('Image selected: ' + file.name + '. Click Scan image to read the QR code.');
      } else {
        if (imagePreview) imagePreview.removeAttribute('src');
        if (fileName) fileName.textContent = '';
        say('Choose a QR image or start the camera.');
      }

      controls();
    });
  }

  if (scanImageButton) {
    scanImageButton.addEventListener('click', async function () {
      var file = fileInput && fileInput.files && fileInput.files[0];
      if (!file) {
        say('Choose a QR image first, then click Scan image.');
        return;
      }
      if (busy || navigating) return;

      busy = true;
      controls();
      say('Reading QR image...');

      var label = scanImageButton.querySelector('span');
      if (label) label.textContent = 'Scanning...';

      try {
        await stopCamera();

        var text = await decoder().scanFile(file, true);
        var target = destination(text);

        navigating = true;
        say('QR recognised. Opening its record...');
        location.assign(target);
      } catch (error) {
        say(error.message && /QR|signature|serial|scanner/i.test(error.message)
          ? error.message
          : 'No readable QR was found. Try a sharper photo showing the whole code.');
      } finally {
        busy = false;
        if (label) label.textContent = 'Scan image';
        controls();
      }
    });
  }

  window.addEventListener('pagehide', function () {
    disposed = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    stopCamera().catch(function () {});
  });

  widget.dataset.ready = 'true';
  say(window.Html5Qrcode
    ? 'Ready. Start the camera, or choose a QR image and click Scan image.'
    : 'The QR decoder could not load. Refresh the page or use the printed serial.');

  controls();
})();