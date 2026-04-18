# 🎬 Progress UI Visual Reference

## Stage Progression & Colors

```
┌─────────────────────────────────────────────────────────────────┐
│  PROGRESS VISUALIZATION (0% → 100%)                            │
└─────────────────────────────────────────────────────────────────┘

████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  45%

        ⚙️                                                         
      Loading Models                                              
      "Models loaded successfully. Analyzing images..."           

───────────────────────────────────────────────────────────────────

  ✓  ⚙️         👁️         ✂️          🔄          🎨          ...
  10% Loading  Detection  Extraction  Swapping   Blending
```

---

## Stage Breakdown with Colors

```javascript
// Stage Configuration in ProgressComponent.js

┌─────────────────────────────────────────────────────────────┐
│ Stage Name          │ Progress │ Color    │ Icon │ Duration│
├─────────────────────────────────────────────────────────────┤
│ model_loading       │ 5-10%   │ #6366f1  │ ⚙️  │ 2-3s   │
│ face_detection      │ 15-25%  │ #f59e0b  │ 👁️  │ 3-5s   │
│ face_extraction     │ 25-35%  │ #ec4899  │ ✂️  │ 2s     │
│ face_swapping       │ 40-55%  │ #8b5cf6  │ 🔄  │ 5-10s  │
│ blending            │ 60-75%  │ #10b981  │ 🎨  │ 3-5s   │
│ enhancement         │ 78-88%  │ #f43f5e  │ ✨  │ 5s     │
│ saving              │ 95-99%  │ #3b82f6  │ 💾  │ 1s     │
│ completed           │ 100%    │ #10b981  │ ✓  │ —      │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Hierarchy

```
ProgressComponent (Main Container)
├── progressSection
│   ├── progressBar (animated fill)
│   └── progressLabel (percentage)
├── stageSection
│   ├── stageHeader
│   │   ├── stageIcon (emoji)
│   │   ├── stageInfo
│   │   │   ├── stageLabel
│   │   │   └── statusMessage
│   │   └── spinner/checkmark/cross
│   └── stageSteps (step indicator)
│       ├── step (×7)
│       │   ├── stepDot
│       │   └── stepLabel
└── statusFooter
    ├── statusBadge
    └── eta
```

---

## Animation Timeline

```
Time: 0s
  └─ Component mounts
     └─ slideIn animation starts (0.4s)
        └─ Container fades in
        └─ statusHeader fadeIn (0.3s)
           └─ stageIcon bounce (0.6s)
           └─ spinner spin (0.8s continuous)

When Progress Updates:
  └─ progressFill width animates (0.6s)
  └─ stepDot color changes smoothly
  └─ stageHeader updates with fadeIn

When Complete:
  └─ spinner stops
  └─ checkmark appears with scaleIn (0.4s)
  └─ progressFill turns green
  └─ statusBadge updates

When Error:
  └─ spinner stops
  └─ cross appears
  └─ shake animation (0.5s)
  └─ error message displayed
```

---

## Frontend Data Flow

```
Redux/Local State
├── status ("idle" | "processing" | "completed" | "failed")
├── progress (0-100)
├── serverStage (e.g., "face_swapping")
├── serverStatusMessage (e.g., "Detecting faces...")
└── error (error message if failed)
    │
    ↓
useEffect (jobId changes)
    │
    └─→ setInterval(pollJob, 1200ms)
        │
        └─→ fetch(`/api/job/${jobId}`)
            │
            └─→ Update all state variables
                │
                └─→ Re-render ProgressComponent
                    │
                    └─→ CSS animations run
                        │
                        └─→ User sees smooth progress
```

---

## Backend Update Cycle

```
Job Processing
    │
    ├─→ Update stage: "model_loading" (5%)
    │   └─→ Redis: job_store.update_job(progress=5)
    │       └─→ Frontend polls: fetch job status
    │           └─→ Component updates
    │               └─→ Bar animates to 5%
    │
    ├─→ Update stage: "face_detection" (15%)
    │   └─→ Redis: job_store.update_job(progress=15)
    │       └─→ Frontend polls: fetch job status
    │           └─→ Component updates
    │               └─→ Bar animates to 15%, icon changes
    │
    └─→ ... repeat for each stage ...
        
        └─→ Update stage: "completed" (100%)
            └─→ Redis: job_store.update_job(progress=100)
                └─→ Frontend polls: fetch job status
                    └─→ Component updates
                        └─→ Bar fills to 100%, checkmark appears
                            └─→ Polling stops (status === 'completed')
```

---

## CSS Animation Examples

```css
/* Progress Bar Shimmer */
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
/* Duration: 2s, infinite */

/* Icon Bounce */
@keyframes bounce {
  0% { transform: scale(0.8) translateY(4px); opacity: 0; }
  50% { transform: scale(1.1); }
  100% { transform: scale(1) translateY(0); opacity: 1; }
}
/* Duration: 0.6s, ease-out */

/* Completion Checkmark */
@keyframes scaleIn {
  from { transform: scale(0) rotate(-45deg); opacity: 0; }
  to { transform: scale(1) rotate(0); opacity: 1; }
}
/* Duration: 0.4s, cubic-bezier(0.34, 1.56, 0.64, 1) */
```

---

## Responsive Breakpoints

```
Desktop (1024px+)
├── Full-size components
├── Large icons (28px)
├── Wide progress bar
└── Side-by-side layouts

Tablet (768px - 1023px)
├── Slightly smaller components
├── Medium icons (24px)
├── Touch-optimized buttons
└── Adjusted padding

Mobile (480px - 767px)
├── Compact components
├── Small icons (20px)
├── Full-width layouts
├── Vertical stacking
└── Reduced padding/margins

Small Mobile (<480px)
├── Minimal spacing
├── Very small icons (18px)
├── Optimized for thumbs
└── Simple layouts
```

---

## Status Indicators

```
Processing:        [⚙️ ] Loading Models
                   [████░░░░░░░░░░░░░░] 20%
                   Processing... (spinner)

In Progress:       [👁️ ] Detecting Faces
                   [████████░░░░░░░░░░] 45%
                   Found 2 faces... (spinner)

Completing:        [🎨 ] Blending
                   [████████████░░░░░░] 70%
                   Blending for seamless result... (spinner)

Completed:         [✓ ] Complete
                   [████████████████████] 100%
                   Done! Your face swap is ready. (checkmark)

Failed:            [✗ ] Error
                   [████░░░░░░░░░░░░░░] 15%
                   Error: No face detected in source (cross + shake)
```

---

## Integration Points

```
1. Backend (processor.py)
   └─→ Calls: job_store.update_job(
       - progress: int (0-100)
       - stage: string
       - status_message: string
       - status: string
   )

2. Redis (job_store)
   └─→ Stores job state in Redis
       - Expires after job_status_ttl_seconds

3. Frontend API (pages/index.js)
   └─→ Polls: /api/job/{job_id}
       - Interval: 1200ms
       - Returns: { progress, stage, status_message, status, ... }

4. ProgressComponent
   └─→ Receives props and renders UI
       - Smooth animations
       - Color updates
       - Stage transitions

5. CSS (Progress.module.css)
   └─→ Handles all animations
       - Transitions
       - Keyframe animations
       - Responsive styles
```

---

## Key Numbers

```
Progress Update Frequency:    1200ms (1.2 seconds)
Progress Bar Animation:       600ms (smooth transition)
Icon Bounce Animation:        600ms
Shimmer Effect Duration:      2000ms (continuous)
Spinner Rotation Speed:       800ms per rotation
Checkmark Animation:          400ms
Error Shake Animation:        500ms
Component Entrance:           400ms

Total Job Duration (average):
  - model_loading:   2-3 seconds
  - face_detection:  3-5 seconds  
  - face_extraction: 2 seconds
  - face_swapping:   5-10 seconds
  - blending:        3-5 seconds
  - enhancement:     5 seconds (optional)
  - saving:          1 second
  ──────────────────────────
  Total:             21-31 seconds average
```

---

## Color Palette Reference

```
#6366f1  │ ⚙️  model_loading      │ Indigo - Professional
#f59e0b  │ 👁️  face_detection     │ Amber - Attention
#ec4899  │ ✂️  face_extraction    │ Pink - Creative
#8b5cf6  │ 🔄  face_swapping      │ Purple - Magical
#10b981  │ 🎨  blending & success │ Emerald - Growth
#f43f5e  │ ✨  enhancement        │ Rose - Enhancement
#3b82f6  │ 💾  saving            │ Blue - Information
```

---

## Testing Viewport Sizes

```
Desktop:
  - 1920×1080
  - 1366×768
  - 1024×768

Tablet:
  - iPad Pro: 1024×1366
  - iPad: 768×1024
  - Galaxy Tab: 800×600

Mobile:
  - iPhone 14: 390×844
  - iPhone SE: 375×667
  - Google Pixel: 412×915
  - Galaxy S21: 360×800
  - Small (old): 320×568
```

This visual reference helps understand the complete progress UI implementation! 🎨
