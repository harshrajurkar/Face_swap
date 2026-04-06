
import { useEffect, useRef, useState } from 'react';

import styles from '../styles/Home.module.css';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';
const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN || 'http://localhost:8000';
const JOB_SESSION_KEY = 'ai-face-studio-session-v1';

const IMAGE_STATUS_STEPS = [
  { key: 'queued', label: 'Queued', text: 'Files are safely stored and waiting for the worker.' },
  { key: 'analyzing', label: 'Analyzing', text: 'Checking face detection, image quality, and compatibility.' },
  { key: 'swapping', label: 'Swapping', text: 'Running the face replacement model on the target image.' },
  { key: 'enhancing', label: 'Enhancing', text: 'Refining details with GFPGAN for a cleaner finish. This step can take longer on CPU.' },
  { key: 'completed', label: 'Completed', text: 'Result is ready to review, compare, and download.' },
];

const VIDEO_STATUS_STEPS = [
  { key: 'queued', label: 'Queued', text: 'Video job is stored and waiting for the worker.' },
  { key: 'extracting_frames', label: 'Extracting Frames', text: 'Breaking the target video into processable frames with ffmpeg.' },
  { key: 'processing_frames', label: 'Processing Frames', text: 'Running face swap and optional enhancement across each frame.' },
  { key: 'rebuilding_video', label: 'Rebuilding Video', text: 'Encoding the processed frames back into the final MP4 output.' },
  { key: 'completed', label: 'Completed', text: 'The swapped video is ready to preview and download.' },
];

function resolveOutputUrl(outputUrl) {
  if (!outputUrl) return '';
  if (outputUrl.startsWith('http://') || outputUrl.startsWith('https://')) return outputUrl;
  return `${BACKEND_ORIGIN}${outputUrl}`;
}

function getCompatibilityLabel(score) {
  if (score === null || score === undefined) return 'Pending';
  if (score >= 72) return 'Strong fit';
  if (score >= 58) return 'Usable fit';
  return 'Challenging fit';
}

function formatFileSize(file) {
  if (!file) return 'No file selected';
  const units = ['B', 'KB', 'MB'];
  let size = file.size;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function getStageIndex(stage, isVideoJob) {
  const steps = isVideoJob ? VIDEO_STATUS_STEPS : IMAGE_STATUS_STEPS;
  const index = steps.findIndex((item) => item.key === stage);
  return index === -1 ? 0 : index;
}

function createPreviewUrl(file) {
  return file ? URL.createObjectURL(file) : '';
}

function isTerminalStatus(status) {
  return status === 'completed' || status === 'failed';
}

function getSavedSession() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(JOB_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function persistSession(session) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(JOB_SESSION_KEY, JSON.stringify(session));
  } catch {
  }
}

function clearPersistedSession() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(JOB_SESSION_KEY);
}

function Uploader({
  title,
  hint,
  file,
  previewUrl,
  accept,
  mediaKind,
  onFileChange,
}) {
  const inputRef = useRef(null);
  const [isDragActive, setIsDragActive] = useState(false);

  function handleDrop(event) {
    event.preventDefault();
    setIsDragActive(false);
    const droppedFile = event.dataTransfer.files?.[0];
    if (droppedFile) {
      onFileChange(droppedFile);
    }
  }

  return (
    <div className={`${styles.uploadCard} ${isDragActive ? styles.uploadCardActive : ''}`}>
      <div className={styles.uploadLabel}>
        <span>{title}</span>
        <span className={styles.uploadMeta}>{formatFileSize(file)}</span>
      </div>

      <div
        className={styles.dropzone}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          hidden
          onClick={(event) => {
            event.currentTarget.value = '';
          }}
          onChange={(event) => {
            onFileChange(event.target.files?.[0] || null);
            event.currentTarget.value = '';
          }}
        />

        <button
          type="button"
          className={styles.dropzoneButton}
          onClick={() => inputRef.current?.click()}
        >
          {previewUrl ? (
            <>
              {mediaKind === 'video' ? (
                <video src={previewUrl} className={styles.previewVideo} muted playsInline controls />
              ) : (
                <img src={previewUrl} alt={`${title} preview`} className={styles.previewImage} />
              )}
              <div className={styles.overlayBar}>
                <span>{file?.name || `Selected ${mediaKind}`}</span>
                <span className={styles.smallButton}>Replace</span>
              </div>
            </>
          ) : (
            <div className={styles.dropzoneEmpty}>
              <div className={styles.dropzoneTitle}>{title}</div>
              <div className={styles.dropzoneText}>{hint}</div>
              <span className={styles.badge}>Drag and drop or browse</span>
            </div>
          )}
        </button>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [targetMode, setTargetMode] = useState('image');
  const [sourceImage, setSourceImage] = useState(null);
  const [targetFile, setTargetFile] = useState(null);
  const [sourcePreviewUrl, setSourcePreviewUrl] = useState('');
  const [targetPreviewUrl, setTargetPreviewUrl] = useState('');
  const [prompt, setPrompt] = useState('');
  const [enhanceFace, setEnhanceFace] = useState(true);
  const [jobId, setJobId] = useState('');
  const [jobType, setJobType] = useState('swap');
  const [status, setStatus] = useState('idle');
  const [stage, setStage] = useState('queued');
  const [progress, setProgress] = useState(0);
  const [outputUrl, setOutputUrl] = useState('');
  const [error, setError] = useState('');
  const [jobPrompt, setJobPrompt] = useState('');
  const [jobEnhanceFace, setJobEnhanceFace] = useState(true);
  const [matchPercent, setMatchPercent] = useState(null);
  const [sourceFaceSize, setSourceFaceSize] = useState(null);
  const [targetFaceSize, setTargetFaceSize] = useState(null);
  const [frameCount, setFrameCount] = useState(null);
  const [processedFrameCount, setProcessedFrameCount] = useState(null);
  const [skippedFrameCount, setSkippedFrameCount] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [comparePosition, setComparePosition] = useState(50);
  const [restoredSession, setRestoredSession] = useState(false);

  const isVideoMode = targetMode === 'video';
  const isVideoJob = jobType === 'video_swap';
  const statusSteps = isVideoJob ? VIDEO_STATUS_STEPS : IMAGE_STATUS_STEPS;

  useEffect(() => {
    const saved = getSavedSession();
    if (!saved || !saved.jobId) {
      return;
    }

    setJobId(saved.jobId || '');
    setJobType(saved.jobType || 'swap');
    setTargetMode(saved.jobType === 'video_swap' ? 'video' : 'image');
    setStatus(saved.status || 'queued');
    setStage(saved.stage || 'queued');
    setProgress(saved.progress ?? 0);
    setOutputUrl(saved.outputUrl || '');
    setError(saved.error || '');
    setJobPrompt(saved.jobPrompt || '');
    setPrompt(saved.jobPrompt || '');
    setJobEnhanceFace(Boolean(saved.jobEnhanceFace));
    setEnhanceFace(Boolean(saved.jobEnhanceFace));
    setMatchPercent(saved.matchPercent ?? null);
    setSourceFaceSize(saved.sourceFaceSize ?? null);
    setTargetFaceSize(saved.targetFaceSize ?? null);
    setFrameCount(saved.frameCount ?? null);
    setProcessedFrameCount(saved.processedFrameCount ?? null);
    setSkippedFrameCount(saved.skippedFrameCount ?? null);
    setRecommendations(saved.recommendations || []);
    setRestoredSession(true);
  }, []);

  useEffect(() => {
    return () => {
      if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
      if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    };
  }, [sourcePreviewUrl, targetPreviewUrl]);

  useEffect(() => {
    if (!jobId) {
      clearPersistedSession();
      return;
    }

    persistSession({
      jobId,
      jobType,
      status,
      stage,
      progress,
      outputUrl,
      error,
      jobPrompt,
      jobEnhanceFace,
      matchPercent,
      sourceFaceSize,
      targetFaceSize,
      frameCount,
      processedFrameCount,
      skippedFrameCount,
      recommendations,
    });
  }, [jobId, jobType, status, stage, progress, outputUrl, error, jobPrompt, jobEnhanceFace, matchPercent, sourceFaceSize, targetFaceSize, frameCount, processedFrameCount, skippedFrameCount, recommendations]);

  useEffect(() => {
    if (!jobId || isTerminalStatus(status)) {
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

        setJobType(data.job_type || 'swap');
        setStatus(data.status || 'unknown');
        setStage(data.stage || 'queued');
        setProgress(data.progress ?? 0);
        setError(data.error || '');
        setJobPrompt(data.prompt || '');
        setJobEnhanceFace(Boolean(data.enhance_face));
        setMatchPercent(data.similarity_percent ?? null);
        setSourceFaceSize(data.source_face_size ?? null);
        setTargetFaceSize(data.target_face_size ?? null);
        setFrameCount(data.frame_count ?? null);
        setProcessedFrameCount(data.processed_frame_count ?? null);
        setSkippedFrameCount(data.skipped_frame_count ?? null);
        setRecommendations(data.recommendations || []);
        if (data.output_url) {
          setOutputUrl(resolveOutputUrl(data.output_url));
        }
      } catch (pollError) {
        if (cancelled) {
          return;
        }
        setStatus('failed');
        setStage('failed');
        setProgress(100);
        setError(pollError.message || 'Polling failed.');
      }
    }

    pollJob();
    const intervalId = window.setInterval(pollJob, 2200);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [jobId, status]);

  function setSourceFile(file) {
    if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
    setSourceImage(file);
    setSourcePreviewUrl(createPreviewUrl(file));
  }

  function setTargetUpload(file) {
    if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    setTargetFile(file);
    setTargetPreviewUrl(createPreviewUrl(file));
  }

  function handleModeChange(mode) {
    setTargetMode(mode);
    if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    setTargetFile(null);
    setTargetPreviewUrl('');
    setOutputUrl('');
    setError('');
    setFrameCount(null);
    setProcessedFrameCount(null);
    setSkippedFrameCount(null);
    setComparePosition(50);
  }

  async function handleDownload() {
    if (!outputUrl || isDownloading) {
      return;
    }

    setIsDownloading(true);
    try {
      const response = await fetch(outputUrl);
      if (!response.ok) {
        throw new Error('Download failed.');
      }

      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      const extension = isVideoJob ? 'mp4' : 'png';
      const fallbackName = jobId ? `face-swap-${jobId}.${extension}` : `face-swap-output.${extension}`;
      const fileName = outputUrl.split('/').pop() || fallbackName;

      link.href = blobUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (downloadError) {
      setError(downloadError.message || 'Unable to download output.');
    } finally {
      setIsDownloading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setOutputUrl('');
    setRecommendations([]);
    setMatchPercent(null);
    setSourceFaceSize(null);
    setTargetFaceSize(null);
    setFrameCount(null);
    setProcessedFrameCount(null);
    setSkippedFrameCount(null);
    setComparePosition(50);
    setRestoredSession(false);

    if (!sourceImage || !targetFile) {
      setError(`Select both the source face image and the ${isVideoMode ? 'target video' : 'target image'} before starting the job.`);
      return;
    }

    const formData = new FormData();
    formData.append('source_image', sourceImage);
    formData.append('target_image', targetFile);
    formData.append('prompt', prompt);
    formData.append('enhance_face', String(enhanceFace));
    formData.append('is_video', String(isVideoMode));

    setIsSubmitting(true);
    setStatus('uploading');
    setStage('queued');
    setProgress(3);

    try {
      const response = await fetch(`${API_BASE_URL}/create-job`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Job creation failed.');
      }

      setJobId(data.job_id);
      setJobType(data.job_type || (isVideoMode ? 'video_swap' : 'swap'));
      setJobPrompt(data.prompt || '');
      setJobEnhanceFace(Boolean(data.enhance_face));
      setStatus(data.status || 'queued');
      setStage(data.stage || 'queued');
      setProgress(data.progress ?? 5);
    } catch (submitError) {
      setStatus('failed');
      setStage('failed');
      setProgress(100);
      setError(submitError.message || 'Upload failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleReset() {
    if (sourcePreviewUrl) URL.revokeObjectURL(sourcePreviewUrl);
    if (targetPreviewUrl) URL.revokeObjectURL(targetPreviewUrl);
    setTargetMode('image');
    setSourceImage(null);
    setTargetFile(null);
    setSourcePreviewUrl('');
    setTargetPreviewUrl('');
    setPrompt('');
    setEnhanceFace(true);
    setJobId('');
    setJobType('swap');
    setStatus('idle');
    setStage('queued');
    setProgress(0);
    setOutputUrl('');
    setError('');
    setJobPrompt('');
    setJobEnhanceFace(true);
    setMatchPercent(null);
    setSourceFaceSize(null);
    setTargetFaceSize(null);
    setFrameCount(null);
    setProcessedFrameCount(null);
    setSkippedFrameCount(null);
    setRecommendations([]);
    setComparePosition(50);
    setRestoredSession(false);
    clearPersistedSession();
  }

  const compatibilityLabel = getCompatibilityLabel(matchPercent);
  const activeStageIndex = getStageIndex(stage, isVideoJob);
  const stageLabel = statusSteps.find((item) => item.key === stage)?.label || 'Preparing';
  const stageText = statusSteps.find((item) => item.key === stage)?.text || 'Preparing your current job.';
  const resultTitle = isVideoJob ? 'Video Result Review' : 'Result Review';
  const targetTitle = isVideoMode ? 'Target Video' : 'Target Frame';
  const targetHint = isVideoMode
    ? 'Upload a target video. The worker will automatically reduce frame rate and resolution for faster CPU processing, then rebuild an MP4.'
    : 'Choose the frame that will receive the swap. Closer faces give cleaner blends.';

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.topbar}>
          <div className={styles.brandBlock}>
            <p className={styles.kicker}>AI Face Studio</p>
            <h1 className={styles.title}>Professional face-swap workbench for image and video production.</h1>
            <p className={styles.subtitle}>
              Run single-frame swaps or short video face swaps through the same async worker pipeline, with live progress,
              result review, and direct downloads built in.
            </p>
          </div>

          <div className={styles.badgeRow}>
            <span className={`${styles.badge} ${styles.accentBadge}`}>Local processing</span>
            <span className={styles.badge}>Image + video jobs</span>
            <span className={styles.badge}>InsightFace + GFPGAN + ffmpeg</span>
            {restoredSession ? <span className={styles.badge}>Session restored</span> : null}
          </div>
        </header>

        <section className={styles.workspace}>
          <form className={`${styles.panel} ${styles.leftPanel}`} onSubmit={handleSubmit}>
            <div className={styles.sectionHeader}>
              <div>
                <h2 className={styles.sectionTitle}>Input Workspace</h2>
                <p className={styles.sectionText}>
                  Start with a strong source portrait, then choose whether you want to process a single target image or a short target video.
                </p>
              </div>
              <span className={styles.badge}>{isVideoMode ? 'Video mode: long clips supported' : 'Image mode: JPG, PNG, WEBP'}</span>
            </div>

            <div className={styles.modeToggle}>
              <button
                type="button"
                className={`${styles.modeButton} ${!isVideoMode ? styles.modeButtonActive : ''}`}
                onClick={() => handleModeChange('image')}
              >
                Image Target
              </button>
              <button
                type="button"
                className={`${styles.modeButton} ${isVideoMode ? styles.modeButtonActive : ''}`}
                onClick={() => handleModeChange('video')}
              >
                Video Target
              </button>
            </div>

            <div className={styles.uploadGrid}>
              <Uploader
                title="Source Identity"
                hint="Use a tighter portrait with clear facial detail so the identity embedding is stronger."
                file={sourceImage}
                previewUrl={sourcePreviewUrl}
                accept="image/*"
                mediaKind="image"
                onFileChange={setSourceFile}
              />
              <Uploader
                title={targetTitle}
                hint={targetHint}
                file={targetFile}
                previewUrl={targetPreviewUrl}
                accept={isVideoMode ? 'video/*' : 'image/*'}
                mediaKind={isVideoMode ? 'video' : 'image'}
                onFileChange={setTargetUpload}
              />
            </div>

            <div className={styles.controlsGrid}>
              <div className={styles.fieldCard}>
                <label className={styles.fieldLabel} htmlFor="session-note">
                  Session Note
                </label>
                <textarea
                  id="session-note"
                  className={styles.textarea}
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder={isVideoMode ? 'Optional note, for example: use for short reel test or client preview pass.' : 'Optional note for this run, for example: compare two portrait variants or save this for client review.'}
                />
                <div className={styles.helperText}>
                  This note is stored with the job for tracking. It does not steer the face-swap model.
                </div>
                {!sourceImage && !targetFile && restoredSession ? (
                  <div className={styles.helperText}>
                    Active job details were restored after refresh. For browser security, file inputs themselves cannot be auto-filled again.
                  </div>
                ) : null}
              </div>

              <div className={styles.optionCard}>
                <div className={styles.toggleRow}>
                  <div className={styles.toggleMeta}>
                    <div className={styles.toggleTitle}>Detail Enhancement</div>
                    <div className={styles.toggleText}>Apply GFPGAN after each image or video frame swap to restore facial sharpness.</div>
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

                <div className={styles.helperText}>
                  {isVideoMode
                    ? 'Video processing is CPU-heavy. The app now auto-reduces FPS and resolution for speed, but long clips can still take time.'
                    : 'Keep this enabled for portrait-grade exports. Turn it off if you want the raw model output for debugging.'}
                </div>
              </div>
            </div>

            <div className={styles.actions}>
              <button className={styles.primaryButton} type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Launching job...' : isVideoMode ? 'Start Video Face Swap Job' : 'Start Face Swap Job'}
              </button>
              <button className={styles.secondaryButton} type="button" onClick={handleReset}>
                Reset Workspace
              </button>
            </div>
          </form>

          <aside className={`${styles.panel} ${styles.rightPanel}`}>
            <section className={styles.statusCard}>
              <div className={styles.statusHeader}>
                <div>
                  <h2 className={styles.statusTitle}>Live Job Monitor</h2>
                  <p className={styles.sectionText}>Track queue progress, quality signals, and processing readiness.</p>
                </div>
                <span className={`${styles.liveChip} ${jobId && status !== 'failed' ? styles.liveChipActive : ''}`}>
                  {jobId ? stageLabel : 'Waiting'}
                </span>
              </div>

              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{ width: `${progress}%` }} />
              </div>

              <div className={styles.progressMeta}>
                <span>{jobId ? `Job ${jobId.slice(0, 8)}` : 'No job started yet'}</span>
                <span>{progress}%</span>
              </div>

              <div className={styles.helperText}>{stageText}</div>
              {error ? <div className={styles.errorBox}>{error}</div> : null}
            </section>

            <section className={styles.timelineCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>Processing Timeline</h3>
                  <p className={styles.sectionText}>A clearer step-by-step view than a raw status string.</p>
                </div>
              </div>

              <div className={styles.timeline}>
                {statusSteps.map((item, index) => {
                  const isDone = activeStageIndex > index || status === 'completed';
                  const isActive = stage === item.key || (!jobId && item.key === 'queued');
                  const dotClass = isDone
                    ? `${styles.timelineDot} ${styles.timelineDotDone}`
                    : isActive
                      ? `${styles.timelineDot} ${styles.timelineDotActive}`
                      : styles.timelineDot;

                  return (
                    <div className={styles.timelineItem} key={item.key}>
                      <span className={dotClass} />
                      <div>
                        <p className={styles.timelineTitle}>{item.label}</p>
                        <p className={styles.timelineText}>{item.text}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className={styles.metricsCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>Quality Signals</h3>
                  <p className={styles.sectionText}>Use these as guidance, not guarantees. Better source and target choices still matter most.</p>
                </div>
              </div>

              <div className={styles.metricsGrid}>
                <div className={styles.metricBox}>
                  <p className={styles.metricLabel}>Compatibility</p>
                  <p className={styles.metricValue}>{matchPercent !== null ? `${matchPercent}%` : '--'}</p>
                  <p className={styles.metricSubtext}>{compatibilityLabel}</p>
                </div>
                <div className={styles.metricBox}>
                  <p className={styles.metricLabel}>Enhancement</p>
                  <p className={styles.metricValue}>{jobEnhanceFace ? 'On' : 'Off'}</p>
                  <p className={styles.metricSubtext}>Post-process detail recovery</p>
                </div>
                <div className={styles.metricBox}>
                  <p className={styles.metricLabel}>{isVideoJob ? 'Frame Count' : 'Source Face Size'}</p>
                  <p className={styles.metricValue}>{isVideoJob ? (frameCount ?? '--') : (sourceFaceSize !== null ? `${sourceFaceSize}px` : '--')}</p>
                  <p className={styles.metricSubtext}>{isVideoJob ? 'Frames extracted for processing' : 'Larger, sharper faces encode better identity'}</p>
                </div>
                <div className={styles.metricBox}>
                  <p className={styles.metricLabel}>{isVideoJob ? 'Frames Done' : 'Target Face Size'}</p>
                  <p className={styles.metricValue}>{isVideoJob ? (processedFrameCount ?? '--') : (targetFaceSize !== null ? `${targetFaceSize}px` : '--')}</p>
                  <p className={styles.metricSubtext}>{isVideoJob ? 'Successfully swapped frames' : 'Closer crops usually yield cleaner blends'}</p>
                </div>
              </div>

              {isVideoJob ? (
                <div className={styles.videoStatsRow}>
                  <span className={styles.badge}>Skipped frames: {skippedFrameCount ?? 0}</span>
                </div>
              ) : null}
            </section>

            <section className={styles.recommendCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>Recommendations</h3>
                  <p className={styles.sectionText}>Actionable advice generated from the analysis stage.</p>
                </div>
              </div>

              {recommendations.length ? (
                <ul className={styles.recommendList}>
                  {recommendations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <div className={styles.emptyResult}>Upload media and start a job to receive live quality recommendations.</div>
              )}
            </section>

            <section className={styles.resultCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>{resultTitle}</h3>
                  <p className={styles.sectionText}>{isVideoJob ? 'Preview the final MP4 and export it directly.' : 'Compare the target frame against the generated output and export the result.'}</p>
                </div>
              </div>

              {outputUrl ? (
                isVideoJob ? (
                  <div className={styles.videoResultWrap}>
                    <video src={outputUrl} className={styles.resultVideo} controls playsInline />
                    <div className={styles.resultActions}>
                      <button
                        className={`${styles.primaryButton} ${styles.downloadButton}`}
                        type="button"
                        onClick={handleDownload}
                        disabled={isDownloading}
                      >
                        {isDownloading ? 'Downloading...' : 'Download Video'}
                      </button>
                      <a className={styles.secondaryButton} href={outputUrl} target="_blank" rel="noreferrer">
                        Open MP4
                      </a>
                    </div>
                  </div>
                ) : (
                  <div className={styles.compareWrap}>
                    <div className={styles.compareStage} style={{ '--compare-position': `${comparePosition}%` }}>
                      {targetPreviewUrl ? <img src={targetPreviewUrl} alt="Original target" className={styles.compareBase} /> : null}
                      <img src={outputUrl} alt="Processed result" className={styles.compareOverlay} />
                      <div className={styles.compareDivider} />
                      <div className={styles.compareLabels}>
                        <span className={styles.compareLabel}>{targetPreviewUrl ? 'Target' : 'Result'}</span>
                        <span className={styles.compareLabel}>Output</span>
                      </div>
                    </div>

                    <div className={styles.sliderWrap}>
                      <div className={styles.progressMeta}>
                        <span>{targetPreviewUrl ? 'Compare target vs result' : 'Output review'}</span>
                        <span>{comparePosition}% result</span>
                      </div>
                      <input
                        className={styles.range}
                        type="range"
                        min="0"
                        max="100"
                        value={comparePosition}
                        onChange={(event) => setComparePosition(Number(event.target.value))}
                        disabled={!targetPreviewUrl}
                      />
                      {!targetPreviewUrl ? (
                        <div className={styles.helperText}>Target preview is not available after refresh, but your saved job result is still here.</div>
                      ) : null}
                    </div>

                    <div className={styles.resultActions}>
                      <button
                        className={`${styles.primaryButton} ${styles.downloadButton}`}
                        type="button"
                        onClick={handleDownload}
                        disabled={isDownloading}
                      >
                        {isDownloading ? 'Downloading...' : 'Download Output'}
                      </button>
                      <a className={styles.secondaryButton} href={outputUrl} target="_blank" rel="noreferrer">
                        Open Full Resolution
                      </a>
                    </div>
                  </div>
                )
              ) : (
                <div className={styles.emptyResult}>
                  {isVideoJob
                    ? 'The output video panel will appear here once the worker finishes extracting, processing, and rebuilding the clip.'
                    : 'The output panel will appear here once the worker completes the job. Keep the target preview selected to use the compare slider.'}
                </div>
              )}
            </section>

            <section className={styles.recommendCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>Run Details</h3>
                  <p className={styles.sectionText}>Useful context for auditability when you are testing multiple image pairs or short clips.</p>
                </div>
              </div>
              <div className={styles.noteList}>
                <div className={styles.noteRow}>
                  <span>Session note</span>
                  <span className={styles.noteValue}>{jobPrompt || 'None'}</span>
                </div>
                <div className={styles.noteRow}>
                  <span>Job type</span>
                  <span className={styles.noteValue}>{isVideoJob ? 'video_swap' : 'swap'}</span>
                </div>
                <div className={styles.noteRow}>
                  <span>Current status</span>
                  <span className={styles.noteValue}>{status}</span>
                </div>
                <div className={styles.noteRow}>
                  <span>Recommended practice</span>
                  <span className={styles.noteValue}>{isVideoJob ? 'Short clips, front-facing shots, steady lighting' : 'Front-facing, sharp, evenly lit portraits'}</span>
                </div>
              </div>
            </section>
          </aside>
        </section>
      </div>
    </main>
  );
}
