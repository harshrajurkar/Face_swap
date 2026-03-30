import { useEffect, useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api';
const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_BACKEND_ORIGIN || 'http://localhost:8000';

function resolveOutputUrl(outputUrl) {
  if (!outputUrl) {
    return '';
  }
  if (outputUrl.startsWith('http://') || outputUrl.startsWith('https://')) {
    return outputUrl;
  }
  return `${BACKEND_ORIGIN}${outputUrl}`;
}

function inferBackendOrigin() {
  try {
    const parsed = new URL(API_BASE_URL);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return BACKEND_ORIGIN;
  }
}

export default function HomePage() {
  const [sourceImage, setSourceImage] = useState(null);
  const [targetImage, setTargetImage] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [enhanceFace, setEnhanceFace] = useState(true);
  const [jobId, setJobId] = useState('');
  const [status, setStatus] = useState('idle');
  const [outputUrl, setOutputUrl] = useState('');
  const [error, setError] = useState('');
  const [jobPrompt, setJobPrompt] = useState('');
  const [jobEnhanceFace, setJobEnhanceFace] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') {
      return undefined;
    }

    const intervalId = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/job/${jobId}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Unable to fetch job status.');
        }

        setStatus(data.status || 'unknown');
        setError(data.error || '');
        setJobPrompt(data.prompt || '');
        setJobEnhanceFace(Boolean(data.enhance_face));
        if (data.output_url) {
          setOutputUrl(resolveOutputUrl(data.output_url));
        }
      } catch (pollError) {
        setStatus('failed');
        setError(pollError.message || 'Polling failed.');
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [jobId, status]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setOutputUrl('');

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

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Job creation failed.');
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

  return (
    <main style={styles.page}>
      <section style={styles.card}>
        <div style={styles.headingWrap}>
          <p style={styles.eyebrow}>Async Face Swap</p>
          <h1 style={styles.title}>Swap a face and optionally restore detail with GFPGAN.</h1>
          <p style={styles.subtitle}>
            InsightFace handles the identity swap. GFPGAN can then restore facial detail to reduce the soft, blurry look
            that classic swap models often leave behind.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Source face image
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setSourceImage(event.target.files?.[0] || null)}
              style={styles.input}
            />
          </label>

          <label style={styles.label}>
            Target image
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setTargetImage(event.target.files?.[0] || null)}
              style={styles.input}
            />
          </label>

          <label style={styles.label}>
            Comparison prompt
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Example: cinematic close-up, natural skin texture, clean face replacement, preserve background"
              rows={4}
              style={styles.textarea}
            />
          </label>

          <label style={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={enhanceFace}
              onChange={(event) => setEnhanceFace(event.target.checked)}
            />
            Enhance swapped face with GFPGAN
          </label>

          <div style={styles.tipBox}>
            Best results come from sharp, front-facing images where the face is large and clearly visible. Enable
            enhancement for cleaner detail, but it may slightly change texture compared with the raw swap.
          </div>

          <button type="submit" disabled={isSubmitting} style={styles.button}>
            {isSubmitting ? 'Submitting...' : 'Create Face Swap Job'}
          </button>
        </form>

        <div style={styles.statusPanel}>
          <p><strong>Status:</strong> {status}</p>
          {jobId ? <p><strong>Job ID:</strong> {jobId}</p> : null}
          {jobPrompt ? <p><strong>Prompt:</strong> {jobPrompt}</p> : null}
          <p><strong>Enhancement:</strong> {jobEnhanceFace ? 'GFPGAN enabled' : 'Off'}</p>
          {error ? <p style={styles.error}>{error}</p> : null}
        </div>

        {outputUrl ? (
          <div style={styles.resultWrap}>
            <h2 style={styles.resultTitle}>Result</h2>
            <img src={outputUrl} alt="Face swap result" style={styles.resultImage} />
            <a href={outputUrl} target="_blank" rel="noreferrer" style={styles.link}>
              Open output image
            </a>
          </div>
        ) : null}
      </section>
    </main>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    margin: 0,
    padding: '32px 20px',
    background: 'radial-gradient(circle at top, #f6f3ea 0%, #dfe9f2 45%, #b4c7d9 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "Georgia, 'Times New Roman', serif",
  },
  card: {
    width: '100%',
    maxWidth: '760px',
    background: 'rgba(255, 255, 255, 0.88)',
    border: '1px solid rgba(32, 53, 71, 0.12)',
    borderRadius: '24px',
    padding: '32px',
    boxShadow: '0 24px 60px rgba(34, 53, 74, 0.16)',
    backdropFilter: 'blur(10px)',
  },
  headingWrap: {
    marginBottom: '24px',
  },
  eyebrow: {
    margin: '0 0 10px',
    textTransform: 'uppercase',
    letterSpacing: '0.18em',
    fontSize: '12px',
    color: '#39576c',
  },
  title: {
    margin: '0 0 12px',
    fontSize: '38px',
    lineHeight: 1.1,
    color: '#1d2f3a',
  },
  subtitle: {
    margin: 0,
    fontSize: '17px',
    lineHeight: 1.6,
    color: '#445c6c',
  },
  form: {
    display: 'grid',
    gap: '18px',
    marginBottom: '24px',
  },
  label: {
    display: 'grid',
    gap: '8px',
    color: '#223946',
    fontWeight: 600,
  },
  input: {
    border: '1px solid #a7b9c8',
    borderRadius: '14px',
    padding: '12px',
    background: '#f8fbfd',
  },
  textarea: {
    border: '1px solid #a7b9c8',
    borderRadius: '14px',
    padding: '12px',
    background: '#f8fbfd',
    resize: 'vertical',
    font: 'inherit',
    minHeight: '110px',
  },
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    color: '#223946',
    fontWeight: 600,
  },
  tipBox: {
    borderRadius: '16px',
    padding: '14px 16px',
    background: '#eef4f8',
    color: '#294454',
    lineHeight: 1.5,
  },
  button: {
    border: 0,
    borderRadius: '999px',
    padding: '14px 20px',
    background: '#24445a',
    color: '#fffdf7',
    fontSize: '15px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  statusPanel: {
    borderTop: '1px solid rgba(34, 57, 70, 0.12)',
    paddingTop: '18px',
    color: '#223946',
  },
  error: {
    color: '#a32525',
  },
  resultWrap: {
    marginTop: '28px',
    display: 'grid',
    gap: '14px',
  },
  resultTitle: {
    margin: 0,
    fontSize: '26px',
    color: '#1d2f3a',
  },
  resultImage: {
    width: '100%',
    borderRadius: '18px',
    border: '1px solid rgba(34, 57, 70, 0.12)',
  },
  link: {
    color: '#24445a',
    fontWeight: 700,
  },
};
