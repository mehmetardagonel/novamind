const waitForRecorderStop = (recorder) =>
  new Promise((resolve) => {
    if (!recorder || recorder.state === 'inactive') {
      resolve()
      return
    }
    recorder.addEventListener('stop', resolve, { once: true })
  })

export const recordUntilSilence = async (options = {}) => {
  const {
    mimeType = 'audio/webm;codecs=opus',
    silenceThreshold = 0.02,
    silenceMs = 900,
    minRecordingMs = 800,
    maxRecordingMs = 15000,
  } = options

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const audioContext = new (window.AudioContext || window.webkitAudioContext)()
  const source = audioContext.createMediaStreamSource(stream)
  const analyser = audioContext.createAnalyser()

  analyser.fftSize = 2048
  source.connect(analyser)

  const recorder = new MediaRecorder(stream, { mimeType })
  const chunks = []
  let animationFrame = null
  let silenceStart = null
  const startTime = performance.now()

  const dataArray = new Uint8Array(analyser.fftSize)

  const cleanup = async () => {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
      animationFrame = null
    }
    source.disconnect()
    analyser.disconnect()
    stream.getTracks().forEach((track) => track.stop())
    await audioContext.close()
  }

  const finalize = async () => {
    if (recorder.state !== 'inactive') {
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

  return new Promise((resolve, reject) => {
    recorder.addEventListener('dataavailable', (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data)
      }
    })

    recorder.addEventListener(
      'stop',
      () => {
        const blobType = recorder.mimeType || 'audio/webm'
        resolve(new Blob(chunks, { type: blobType }))
      },
      { once: true }
    )

    recorder.addEventListener('error', async (event) => {
      await cleanup()
      reject(event.error || new Error('Recorder error'))
    })

    const monitor = () => {
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

    recorder.start()
    audioContext.resume().catch(() => {})
    monitor()
  })
}
