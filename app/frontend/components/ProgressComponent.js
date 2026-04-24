import styles from '../styles/Progress.module.css';

const STAGE_CONFIG = {
    model_loading: {
        label: 'Loading Models',
        icon: '⚙️',
        color: '#6366f1',
    },
    face_detection: {
        label: 'Detecting Faces',
        icon: '👁️',
        color: '#f59e0b',
    },
    face_extraction: {
        label: 'Extracting Faces',
        icon: '✂️',
        color: '#ec4899',
    },
    face_swapping: {
        label: 'Swapping Faces',
        icon: '🔄',
        color: '#8b5cf6',
    },
    blending: {
        label: 'Blending',
        icon: '🎨',
        color: '#10b981',
    },
    enhancement: {
        label: 'Enhancing Details',
        icon: '✨',
        color: '#f43f5e',
    },
    saving: {
        label: 'Saving Output',
        icon: '💾',
        color: '#3b82f6',
    },
    completed: {
        label: 'Complete',
        icon: '✓',
        color: '#10b981',
    },
    failed: {
        label: 'Failed',
        icon: '✗',
        color: '#ef4444',
    },
};

export default function ProgressComponent({
    progress,
    stage,
    statusMessage,
    status,
    error,
}) {
    const stageConfig = STAGE_CONFIG[stage] || STAGE_CONFIG.model_loading;
    const isCompleted = status === 'completed';
    const isFailed = status === 'failed';
    const isProcessing = status === 'processing';

    // Calculate smooth progress with small increments
    const displayProgress = progress ?? 0;

    return (
        <div className={styles.container}>
            {/* Progress Bar */}
            <div className={styles.progressSection}>
                <div className={styles.progressBar}>
                    <div
                        className={`${styles.progressFill} ${isFailed ? styles.failed : ''} ${isCompleted ? styles.completed : ''}`}
                        style={{
                            width: `${displayProgress}%`,
                            backgroundColor: stageConfig.color,
                        }}
                    />
                </div>
                <div className={styles.progressLabel}>
                    <span className={styles.percentage}>{displayProgress}%</span>
                </div>
            </div>

            {/* Stage and Status */}
            <div className={styles.stageSection}>
                {/* Stage Header */}
                <div className={styles.stageHeader}>
                    <div className={styles.stageIcon}>{stageConfig.icon}</div>
                    <div className={styles.stageInfo}>
                        <h3 className={styles.stageLabel}>{stageConfig.label}</h3>
                        {statusMessage && <p className={styles.statusMessage}>{statusMessage}</p>}
                    </div>
                    {isProcessing && <div className={styles.spinner} />}
                    {isCompleted && <div className={styles.checkmark}>✓</div>}
                    {isFailed && <div className={styles.cross}>✗</div>}
                </div>

                {/* Stage Steps */}
                <div className={styles.stageSteps}>
                    {renderStageSteps(progress, displayProgress)}
                </div>
            </div>

            {/* Status Footer */}
            <div className={styles.statusFooter}>
                <span className={styles.statusBadge} style={{ backgroundColor: stageConfig.color }}>
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                </span>
                {displayProgress > 0 && displayProgress < 100 && (
                    <span className={styles.eta}>Estimating time...</span>
                )}
                {isCompleted && <span className={styles.eta}>Done!</span>}
                {isFailed && <span className={styles.eta}>An error occurred</span>}
            </div>
        </div>
    );
}

function renderStageSteps(progress, displayProgress) {
    const stages = [
        { name: 'model_loading', range: [0, 10] },
        { name: 'face_detection', range: [10, 25] },
        { name: 'face_extraction', range: [25, 35] },
        { name: 'face_swapping', range: [35, 55] },
        { name: 'blending', range: [55, 75] },
        { name: 'enhancement', range: [75, 88] },
        { name: 'saving', range: [88, 100] },
    ];

    return (
        <>
            {stages.map((stage, idx) => {
                const [start, end] = stage.range;
                const isActive = displayProgress > start && displayProgress <= end;
                const isCompleted = displayProgress > end;
                const config = STAGE_CONFIG[stage.name];

                return (
                    <div key={stage.name} className={styles.step}>
                        <div
                            className={`${styles.stepDot} ${isCompleted ? styles.completed : ''} ${isActive ? styles.active : ''}`}
                            style={{
                                backgroundColor: isCompleted || isActive ? config.color : '#e5e7eb',
                            }}
                        >
                            {isCompleted ? '✓' : idx + 1}
                        </div>
                        <span
                            className={`${styles.stepLabel} ${isCompleted ? styles.completedLabel : ''} ${isActive ? styles.activeLabel : ''}`}
                        >
                            {config.label}
                        </span>
                    </div>
                );
            })}
        </>
    );
}
