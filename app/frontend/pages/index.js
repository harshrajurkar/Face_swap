import { useEffect, useMemo, useRef, useState } from 'react';

import ProgressComponent from '../components/ProgressComponent';
import styles from '../styles/Home.module.css';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN || '';
const SUPPORTED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp'];

function getBrowserOrigin() {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.location.origin;
}

function resolveOutputUrl(outputUrl) {
  if (!outputUrl) {
    return '';
  }
  if (outputUrl.startsWith('http://') || outputUrl.startsWith('https://')) {
    return outputUrl;
  }
  return `${BACKEND_ORIGIN || getBrowserOrigin()}${outputUrl}`;
}

function buildDownloadUrl(outputUrl) {
  if (!outputUrl) {
    return '';
  }
  try {
    const url = new URL(outputUrl, getBrowserOrigin());
    url.searchParams.set('download', '1');
    return url.toString();
  } catch {
    return outputUrl.includes('?') ? `${outputUrl}&download=1` : `${outputUrl}?download=1`;
  }
}

function inferBackendOrigin() {
  if (API_BASE_URL.startsWith('/')) {
    return getBrowserOrigin();
  }
  try {
    const parsed = new URL(API_BASE_URL);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return BACKEND_ORIGIN || getBrowserOrigin();
  }
}

function formatFileSize(file) {
  if (!file) {
    return 'No file selected';
  }
  const units = ['B', 'KB', 'MB'];
  let size = file.size;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function createPreviewUrl(file) {
  return file ? URL.createObjectURL(file) : '';
}

function hasSupportedImageExtension(file) {
  if (!file?.name) {
    return false;
  }
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  return SUPPORTED_IMAGE_EXTENSIONS.includes(extension);
}

function getStatusLabel(status) {
  if (status === 'queued') return 'Queued';
  if (status === 'processing') return 'Processing';
  if (status === 'completed') return 'Completed';
  if (status === 'failed') return 'Failed';
  if (status === 'uploading') return 'Uploading';
  return 'Ready';
}

function getStatusText(status) {
  if (status === 'queued') return 'Files are stored and waiting for the worker.';
  if (status === 'processing') return 'InsightFace is running the swap and optional enhancement.';
  if (status === 'completed') return 'Your final image is ready to compare and download.';
  if (status === 'failed') return 'The run stopped before completion. Review the error and try again.';
  if (status === 'uploading') return 'Uploading both images and creating a background job.';
  return 'Choose a source portrait and a target image to begin.';
}

function getProgress(status) {
  if (status === 'uploading') return 12;
  if (status === 'queued') return 28;
  if (status === 'processing') return 72;
  if (status === 'completed' || status === 'failed') return 100;
  return 0;
}

function Uploader({ title, hint, file, previewUrl, onFileChange }) {
  const inputRef = useRef(null);

  return (
    <div className={styles.uploadCard}>
      <div className={styles.uploadHeader}>
        <span>{title}</span>
        <span className={styles.meta}>{formatFileSize(file)}</span>
      </div>

      <div className={styles.uploadSurface}>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
          hidden
          onClick={(event) => {
            event.currentTarget.value = '';
          }}
          onChange={(event) => {
            onFileChange(event.target.files?.[0] || null);
            event.currentTarget.value = '';
          }}
        />

        <button type="button" className={styles.uploadButton} onClick={() => inputRef.current?.click()}>
          {previewUrl ? (
            <>
              <img src={previewUrl} alt={`${title} preview`} className={styles.preview} />
              <div className={styles.overlayBar}>
                <span>{file?.name || 'Selected image'}</span>
                <span className={styles.chip}>Replace</span>
              </div>
            </>
          ) : (
            <div className={styles.uploadEmpty}>
              <div className={styles.uploadEmptyTitle}>{title}</div>
              <div className={styles.uploadEmptyText}>{hint}</div>
              <span className={styles.badge}>Browse image</span>
            </div>
          )}
        </button>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [sourceImage, setSourceImage] = useState(null);
  const [targetImage, setTargetImage] = useState(null);
  const [sourcePreviewUrl, setSourcePreviewUrl] = useState('');
  const [targetPreviewUrl, setTargetPreviewUrl] = useState('');
  const [prompt, setPrompt] = useState('');
  const [enhanceFace, setEnhanceFace] = useState(false);
  const [jobId, setJobId] = useState('');
  const [status, setStatus] = useState('idle');
  const [outputUrl, setOutputUrl] = useState('');
  const [error, setError] = useState('');
  const [jobPrompt, setJobPrompt] = useState('');
  const [jobEnhanceFace, setJobEnhanceFace] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [comparePosition, setComparePosition] = useState(50);
  const [serverProgress, setServerProgress] = useState(null);
  const [serverStage, setServerStage] = useState('');
  const [serverStatusMessage, setServerStatusMessage] = useState('');

  useEffect(() => {
    return () => {
      if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
      if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    };
  }, [sourcePreviewUrl, targetPreviewUrl]);

  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') {
      return undefined;
    }

    let cancelled = false;

    async function pollJob() {
      try {
        const response = await fetch(`${API_BASE_URL}/job/${jobId}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Unable to fetch job status.');
        }

        if (cancelled) {
          return;
        }

        setStatus(data.status || 'unknown');
        const backendError = data.error || data.detail || '';
        const derivedFailureMessage =
          (data.status === 'failed' && !backendError)
            ? 'Face swap failed during processing. Please try again with clearer supported images.'
            : '';
        setError(backendError || derivedFailureMessage);
        setJobPrompt(data.prompt || '');
        setJobEnhanceFace(Boolean(data.enhance_face));
        setServerProgress(typeof data.progress === 'number' ? data.progress : null);
        setServerStage(data.stage || '');
        setServerStatusMessage(data.status_message || '');
        if (data.output_url) {
          setOutputUrl(resolveOutputUrl(data.output_url));
        }
      } catch (pollError) {
        if (cancelled) {
          return;
        }
        setStatus('failed');
        setError(pollError.message || 'Polling failed.');
      }
    }

    pollJob();
    const intervalId = window.setInterval(pollJob, 1200);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [jobId, status]);

  const statusLabel = getStatusLabel(status);
  const statusText = error || serverStatusMessage || getStatusText(status);
  const progress = serverProgress ?? getProgress(status);
  const resultName = useMemo(() => {
    if (!outputUrl) {
      return '';
    }
    return outputUrl.split('/').pop() || 'face-swap-result.png';
  }, [outputUrl]);

  function setSourceFile(file) {
    if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
    if (file && !hasSupportedImageExtension(file)) {
      setError('Unsupported source image format. Use .jpg, .jpeg, .png, or .webp.');
      setSourceImage(null);
      setSourcePreviewUrl('');
      return;
    }
    setError('');
    setSourceImage(file);
    setSourcePreviewUrl(createPreviewUrl(file));
  }

  function setTargetFile(file) {
    if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    if (file && !hasSupportedImageExtension(file)) {
      setError('Unsupported target image format. Use .jpg, .jpeg, .png, or .webp.');
      setTargetImage(null);
      setTargetPreviewUrl('');
      return;
    }
    setError('');
    setTargetImage(file);
    setTargetPreviewUrl(createPreviewUrl(file));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setOutputUrl('');
    setComparePosition(50);

    if (!sourceImage || !targetImage) {
      setError('Select both the source face image and the target image.');
      return;
    }

    const formData = new FormData();
    formData.append('source_image', sourceImage);
    formData.append('target_image', targetImage);
    formData.append('prompt', prompt);
    formData.append('enhance_face', String(enhanceFace));
    formData.append('response_base_url', inferBackendOrigin());

    setIsSubmitting(true);
    setStatus('uploading');

    try {
      const response = await fetch(`${API_BASE_URL}/create-job`, {
        method: 'POST',
        body: formData,
      });
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (!response.ok) {
        throw new Error(data.detail || data.error || `Job creation failed (HTTP ${response.status}).`);
      }

      setJobId(data.job_id);
      setJobPrompt(data.prompt || '');
      setJobEnhanceFace(Boolean(data.enhance_face));
      setStatus(data.status || 'queued');
    } catch (submitError) {
      setStatus('failed');
      setError(submitError.message || 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDownload() {
    if (!outputUrl || isDownloading) {
      return;
    }

    setIsDownloading(true);
    try {
      // Ask the same-origin backend to stream S3 output as an attachment.
      const link = document.createElement('a');
      link.href = buildDownloadUrl(outputUrl);
      link.download = resultName;
      link.rel = 'noreferrer';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (downloadError) {
      setError(downloadError.message || 'Unable to download output.');
    } finally {
      setIsDownloading(false);
    }
  }

  function handleReset() {
    if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
    if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    setSourceImage(null);
    setTargetImage(null);
    setSourcePreviewUrl('');
    setTargetPreviewUrl('');
    setPrompt('');
    setEnhanceFace(false);
    setJobId('');
    setStatus('idle');
    setOutputUrl('');
    setError('');
    setJobPrompt('');
    setJobEnhanceFace(false);
    setIsSubmitting(false);
    setIsDownloading(false);
    setComparePosition(50);
    setServerProgress(null);
    setServerStage('');
    setServerStatusMessage('');
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.hero}>
          <div>
            <p className={styles.eyebrow}>AI Face Swap Studio</p>
            <h1 className={styles.title}>Simple, professional face swap review from upload to final compare.</h1>
            <p className={styles.subtitle}>
              Upload one source portrait and one target image, let the worker process the swap in the background, then
              review the final result with a comparison slider before downloading it to your device.
            </p>
          </div>

          <div className={styles.badgeRow}>
            <span className={styles.badge}>Async processing</span>
            <span className={styles.badge}>InsightFace</span>
            <span className={styles.badge}>GFPGAN optional</span>
          </div>
        </header>

        <section className={styles.workspace}>
          <form className={`${styles.panel} ${styles.composer}`} onSubmit={handleSubmit}>
            <div className={styles.sectionHeader}>
              <div>
                <h2 className={styles.sectionTitle}>Input Workspace</h2>
                <p className={styles.sectionText}>
                  Keep it straightforward: a clear source portrait, a clean target image, one optional note, and one
                  enhancement toggle.
                </p>
              </div>
              <span className={styles.badge}>Image only</span>
            </div>

            <div className={styles.uploadGrid}>
              <Uploader
                title="Source Identity"
                hint="Use a sharp portrait with a clear, front-facing face."
                file={sourceImage}
                previewUrl={sourcePreviewUrl}
                onFileChange={setSourceFile}
              />
              <Uploader
                title="Target Image"
                hint="Choose the image that should receive the new face."
                file={targetImage}
                previewUrl={targetPreviewUrl}
                onFileChange={setTargetFile}
              />
            </div>

            <div className={styles.controlGrid}>
              <div className={`${styles.card} ${styles.fieldCard}`}>
                <label className={styles.label} htmlFor="session-note">
                  Session Note
                </label>
                <textarea
                  id="session-note"
                  className={styles.textarea}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="Optional note for this run, such as client preview, portrait test, or quality comparison."
                />
                <div className={styles.helper}>
                  This note is stored with the job for tracking only. It does not control the face swap model.
                </div>
              </div>

              <div className={`${styles.card} ${styles.optionCard}`}>
                <div className={styles.toggleRow}>
                  <div>
                    <div className={styles.toggleTitle}>Detail Enhancement</div>
                    <div className={styles.toggleText}>Apply GFPGAN after the swap for a cleaner, sharper result.</div>
                  </div>
                  <label className={styles.switch}>
                    <input
                      type="checkbox"
                      checked={enhanceFace}
                      onChange={(event) => setEnhanceFace(event.target.checked)}
                    />
                    <span className={styles.slider} />
                  </label>
                </div>
                <div className={styles.helper}>
                  Best results usually come from large, evenly lit faces. Turn enhancement off if you want to inspect the
                  raw swap output.
                </div>
              </div>
            </div>

            <div className={styles.actions}>
              <button className={styles.primaryButton} type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Launching job...' : 'Start Face Swap'}
              </button>
              <button className={styles.secondaryButton} type="button" onClick={handleReset}>
                Reset
              </button>
            </div>
          </form>

          <aside className={`${styles.panel} ${styles.sidebar}`}>
            {status !== 'idle' ? (
              <ProgressComponent
                progress={progress}
                stage={serverStage}
                statusMessage={serverStatusMessage}
                status={status}
                error={error}
              />
            ) : (
              <section className={`${styles.card} ${styles.statusCard}`}>
                <div className={styles.statusHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>Live Status</h2>
                    <p className={styles.sectionText}>Ready to begin. Upload your images and click "Start Face Swap".</p>
                  </div>
                  <span className={styles.livePill}>Ready</span>
                </div>
                <div className={styles.helper}>Select your source portrait and target image to get started.</div>
              </section>
            )}

            {status === 'idle' && (
              <section className={`${styles.card} ${styles.summaryCard}`}>
                <div className={styles.sectionHeader}>
                  <div>
                    <h3 className={styles.sectionTitle}>Run Summary</h3>
                    <p className={styles.sectionText}>Useful context for quick review and support.</p>
                  </div>
                </div>

                <div className={styles.summaryList}>
                  <div className={styles.summaryRow}>
                    <span>Job ID</span>
                    <span className={styles.summaryValue}>{jobId || 'Not created yet'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Enhancement</span>
                    <span className={styles.summaryValue}>{jobEnhanceFace ? 'GFPGAN on' : 'Off'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Session note</span>
                    <span className={styles.summaryValue}>{jobPrompt || 'None'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Best practice</span>
                    <span className={styles.summaryValue}>Front-facing, sharp, evenly lit portraits</span>
                  </div>
                </div>
              </section>
            )}

            {status !== 'idle' && status !== 'completed' && status !== 'failed' && (
              <section className={`${styles.card} ${styles.summaryCard}`}>
                <div className={styles.sectionHeader}>
                  <div>
                    <h3 className={styles.sectionTitle}>Run Summary</h3>
                    <p className={styles.sectionText}>Details about this job.</p>
                  </div>
                </div>

                <div className={styles.summaryList}>
                  <div className={styles.summaryRow}>
                    <span>Job ID</span>
                    <span className={styles.summaryValue}>{jobId ? jobId.slice(0, 16) + '...' : 'N/A'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Enhancement</span>
                    <span className={styles.summaryValue}>{jobEnhanceFace ? 'GFPGAN on' : 'Off'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Current stage</span>
                    <span className={styles.summaryValue}>{serverStage || 'Initializing'}</span>
                  </div>
                  <div className={styles.summaryRow}>
                    <span>Progress</span>
                    <span className={styles.summaryValue}>{progress}%</span>
                  </div>
                </div>
              </section>
            )}

            <section className={`${styles.card} ${styles.resultCard}`}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>Result Review</h3>
                  <p className={styles.sectionText}>
                    Compare the target against the final output, then download the image directly to your device.
                  </p>
                </div>
              </div>

              {outputUrl ? (
                <div className={styles.resultStage}>
                  {targetPreviewUrl ? (
                    <>
                      <div className={styles.compareFrame} style={{ '--compare-position': `${comparePosition}%` }}>
                        <img src={targetPreviewUrl} alt="Original target" className={styles.compareBase} />
                        <img src={outputUrl} alt="Processed result" className={styles.compareOverlay} />
                        <div className={styles.compareDivider} />
                        <div className={styles.compareLabels}>
                          <span className={styles.compareLabel}>Target</span>
                          <span className={styles.compareLabel}>Output</span>
                        </div>
                      </div>

                      <div className={styles.rangeWrap}>
                        <div className={styles.progressMeta}>
                          <span>Comparison slider</span>
                          <span>{comparePosition}% output</span>
                        </div>
                        <input
                          className={styles.range}
                          type="range"
                          min="0"
                          max="100"
                          value={comparePosition}
                          onChange={(event) => setComparePosition(Number(event.target.value))}
                        />
                      </div>
                    </>
                  ) : (
                    <img src={outputUrl} alt="Face swap result" className={styles.resultImage} />
                  )}

                  <div className={styles.downloadRow}>
                    <button className={styles.primaryButton} type="button" onClick={handleDownload} disabled={isDownloading}>
                      {isDownloading ? 'Downloading...' : 'Download Result'}
                    </button>
                    <a className={styles.secondaryButton} href={outputUrl} target="_blank" rel="noreferrer">
                      Open Full Image
                    </a>
                  </div>
                </div>
              ) : (
                <div className={styles.emptyState}>
                  The result review panel will appear here after the job completes. Keep the target preview selected to
                  use the final comparison slider.
                </div>
              )}
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}
