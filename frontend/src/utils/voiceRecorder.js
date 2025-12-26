const waitForRecorderStop = (recorder) =>
  new Promise((resolve) => {
    if (!recorder || recorder.state === 'inactive') {
      resolve()
      return
    }
    recorder.addEventListener('stop', resolve, { once: true })
  })

export const recordUntilSilence = (options = {}) => {
  const {
    mimeType = 'audio/webm;codecs=opus',
    silenceThreshold = 0.02,
    silenceMs = 900,
    minRecordingMs = 800,
    maxRecordingMs = 15000,
  } = options

  let stream = null
  let audioContext = null
  let source = null
  let analyser = null
  let recorder = null
  let animationFrame = null
  let silenceStart = null
  let startTime = 0
  let dataArray = null
  let stopRequested = false
  let isFinalizing = false
  let ready = false
  const chunks = []
  let resolvePromise
  let rejectPromise

  const cleanup = async () => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
      animationFrame = null
    }
    if (source) source.disconnect()
    if (analyser) analyser.disconnect()
    if (stream) stream.getTracks().forEach((track) => track.stop())
    if (audioContext) await audioContext.close()
  }

  const finalize = async () => {
    if (isFinalizing) return
    isFinalizing = true
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
      await waitForRecorderStop(recorder)
    }
    await cleanup()
  }

  const calculateRms = () => {
    analyser.getByteTimeDomainData(dataArray)
    let sum = 0
    for (let i = 0; i < dataArray.length; i += 1) {
      const normalized = (dataArray[i] - 128) / 128
      sum += normalized * normalized
    }
    return Math.sqrt(sum / dataArray.length)
  }

  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve
    rejectPromise = reject
  })

  const monitor = () => {
    if (stopRequested) {
      finalize()
      return
    }
    const now = performance.now()
    const elapsed = now - startTime

    if (elapsed >= maxRecordingMs) {
      finalize()
      return
    }

    if (elapsed >= minRecordingMs) {
      const rms = calculateRms()
      if (rms < silenceThreshold) {
        if (!silenceStart) {
          silenceStart = now
        } else if (now - silenceStart >= silenceMs) {
          finalize()
          return
        }
      } else {
        silenceStart = null
      }
    }

    animationFrame = requestAnimationFrame(monitor)
  }

  const stop = () => {
    stopRequested = true
    if (ready) {
      finalize()
    }
  }

  const setup = async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioContext = new (window.AudioContext || window.webkitAudioContext)()
      source = audioContext.createMediaStreamSource(stream)
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
      recorder = new MediaRecorder(stream, { mimeType })
      dataArray = new Uint8Array(analyser.fftSize)
      startTime = performance.now()
      ready = true

      recorder.addEventListener('dataavailable', (event) => {
        if (event.data && event.data.size > 0) {
          chunks.push(event.data)
        }
      })

      recorder.addEventListener(
        'stop',
        () => {
          const blobType = recorder.mimeType || 'audio/webm'
          resolvePromise(new Blob(chunks, { type: blobType }))
        },
        { once: true }
      )

      recorder.addEventListener(
        'error',
        async (event) => {
          await cleanup()
          rejectPromise(event.error || new Error('Recorder error'))
        },
        { once: true }
      )

      recorder.start()
      audioContext.resume().catch(() => {})

      if (stopRequested) {
        finalize()
        return
      }
      monitor()
    } catch (error) {
      rejectPromise(error)
    }
  }

  setup()

  return { promise, stop }
}
