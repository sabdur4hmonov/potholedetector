// Show startup/runtime script errors on screen. Without this a script failure leaves a blank
// page and nothing to report; this is the first script the page loads.
(() => {
  const note = (label, detail) => {
    try {
      let box = document.getElementById("bootErrorBox");
      if (!box) {
        box = document.createElement("pre");
        box.id = "bootErrorBox";
        box.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;max-height:40vh;overflow:auto;"
          + "background:#3a1010;color:#ffd7d7;font:11px/1.4 monospace;padding:8px;border-radius:8px;"
          + "z-index:99999;white-space:pre-wrap;margin:0";
        (document.body || document.documentElement).appendChild(box);
      }
      if (box.textContent.length < 3000) box.textContent += label + ": " + detail + "\n";
    } catch (_) {}
  };
  window.addEventListener("error", (e) => note("error", String(e.message) + " @ "
    + String(e.filename || "").split("/").pop() + ":" + e.lineno + ":" + e.colno));
  window.addEventListener("unhandledrejection", (e) => {
    const r = e.reason;
    note("promise", String(r && (r.stack || r.message) || r).slice(0, 500));
  });
})();

// The app engine: the entire pipeline on-device, no server anywhere.
// The page's api() delegates every call here.
(() => {
  const NATIVE = !!(window.Capacitor && Capacitor.isNativePlatform && Capacitor.isNativePlatform());

  // Hold a native writer lease through the final camera import/composer callback.
  // Browser handoffs create no plugin-owned files and need no native lease.
  window.withManagedMediaOperation = async (kind, action) => {
    if (!NATIVE) return action();
    const wipeActive = () => !!(window.isManagedMediaWipeInProgress && window.isManagedMediaWipeInProgress());
    if (wipeActive()) throw new Error("App data deletion is in progress; retry afterwards.");
    const plugin = Capacitor.registerPlugin ? Capacitor.registerPlugin("ManagedMedia")
      : Capacitor.Plugins && Capacitor.Plugins.ManagedMedia;
    if (!plugin || !plugin.beginOperation || !plugin.endOperation) {
      throw new Error("Native media cleanup is unavailable; reopen the updated app.");
    }
    const lease = await plugin.beginOperation({ kind });
    if (!lease || typeof lease.token !== "string") throw new Error("Native media operation was not admitted.");
    try {
      if (wipeActive()) throw new Error("App data deletion is in progress; retry afterwards.");
      return await action();
    }
    finally {
      const result = await plugin.endOperation({ token: lease.token });
      if (!result || result.cleaned !== true) throw new Error("Temporary media cleanup incomplete; use Delete All Data to retry.");
    }
  };

  // Native credentials live behind Android Keystore-backed authenticated encryption.
  // The bridge exposes status, replacement, deletion, and one fixed OpenAI operation;
  // it never returns plaintext. Browser credentials are deliberately memory-only.
  const CredentialBroker = (() => {
    let browserOpenAiKey = "";
    let openAiConfigured = false;
    let dashcamRtspConfigured = false;
    let initializationError = null;
    const nativePlugin = (() => {
      if (!NATIVE) return null;
      try {
        return Capacitor.registerPlugin ? Capacitor.registerPlugin("SecureCredentials")
          : (Capacitor.Plugins && Capacitor.Plugins.SecureCredentials);
      } catch (_) { return null; }
    })();
    const takeLegacy = (name) => {
      const value = String(localStorage.getItem(name) || "").trim();
      // Remove the persistent plaintext before any asynchronous bridge work. If Android
      // rejects migration, the user must enter it again instead of leaving it exposed.
      localStorage.removeItem(name);
      return value;
    };
    let legacyOpenAiKey = takeLegacy("openai_key");
    let legacyDashcamRtspUrl = takeLegacy("dashcam_rtsp_url");
    const hadLegacyCredential = !!(legacyOpenAiKey || legacyDashcamRtspUrl);

    // SEC-016: credentials are accepted only through explicit Settings entry, never from a
    // link. A legacy `#key=` fragment is discarded unread and removed from the address bar.
    if (!NATIVE && new URLSearchParams(location.hash.replace(/^#/, "")).has("key")) {
      history.replaceState(null, "", location.pathname + location.search);
    }

    const applyStatus = (status) => {
      openAiConfigured = !!(status && status.openAiConfigured);
      dashcamRtspConfigured = !!(status && status.dashcamRtspConfigured);
      return { openAiConfigured, dashcamRtspConfigured };
    };
    const readyPromise = (async () => {
      if (NATIVE) {
        if (!nativePlugin) throw new Error("Secure credential storage is unavailable.");
        const migration = {};
        if (legacyOpenAiKey) migration.openAiKey = legacyOpenAiKey;
        if (legacyDashcamRtspUrl) migration.dashcamRtspUrl = legacyDashcamRtspUrl;
        let status;
        if (Object.keys(migration).length) {
          try {
            status = await nativePlugin.migrateLegacyCredentials(migration);
          } catch (_) {
            // Invalid legacy values stay deleted. A working native store must still
            // allow Settings to save a replacement rather than locking out recovery.
            status = await nativePlugin.getStatus();
          }
        } else {
          status = await nativePlugin.getStatus();
        }
        applyStatus(status);
      } else {
        browserOpenAiKey = legacyOpenAiKey;
        openAiConfigured = !!browserOpenAiKey;
        dashcamRtspConfigured = false;
      }
      legacyOpenAiKey = "";
      legacyDashcamRtspUrl = "";
    })().catch(() => {
      legacyOpenAiKey = "";
      legacyDashcamRtspUrl = "";
      initializationError = new Error("Secure credential storage is unavailable. Open Settings and save the credential again.");
    });

    const ready = async () => {
      await readyPromise;
      if (initializationError) throw initializationError;
    };
    const responseLike = (result) => {
      const text = String(result && result.body || "");
      return {
        status: Number(result && result.status || 0),
        ok: !!(result && result.ok),
        body: null,
        text: async () => text,
        json: async () => JSON.parse(text),
      };
    };
    const request = async (body, stream) => {
      await ready();
      if (!openAiConfigured) {
        throw new Error("OpenAI API key missing. Tap the gear icon and paste it.");
      }
      const bounded = boundedAiRequest(body, stream);
      if (NATIVE) {
        try {
          return responseLike(await nativePlugin.openAiRequest({
            body: JSON.stringify(bounded), stream: !!stream,
          }));
        } catch (error) {
          if (error && error.code === "AI_USAGE_LIMIT") throw aiUsageLimitError();
          throw error;
        }
      }
      // A browser-owned ledger can be reset by the same JS that owns the credential.
      // Fail closed instead of offering a paid path without authoritative accounting.
      const error = new Error("AI inference is available only in the Android app.");
      error.fatal = true; error.aiUsageLimit = true;
      throw error;
    };
    const storeCredentials = async ({ openAiKey, dashcamRtspUrl } = {}) => {
      await ready();
      if (NATIVE) {
        const update = {};
        if (openAiKey) update.openAiKey = openAiKey;
        if (dashcamRtspUrl) update.dashcamRtspUrl = dashcamRtspUrl;
        if (!Object.keys(update).length) return { openAiConfigured, dashcamRtspConfigured };
        return applyStatus(await nativePlugin.storeCredentials(update));
      }
      if (openAiKey) browserOpenAiKey = String(openAiKey).trim();
      openAiConfigured = !!browserOpenAiKey;
      dashcamRtspConfigured = false;
      return { openAiConfigured, dashcamRtspConfigured };
    };
    const refresh = async () => {
      await ready();
      if (NATIVE) return applyStatus(await nativePlugin.getStatus());
      return { openAiConfigured, dashcamRtspConfigured };
    };
    const clear = async () => {
      await ready();
      browserOpenAiKey = "";
      if (NATIVE) return applyStatus(await nativePlugin.clearCredentials());
      openAiConfigured = false;
      dashcamRtspConfigured = false;
      return { openAiConfigured, dashcamRtspConfigured };
    };
    const prewarm = async () => {
      await ready();
      if (NATIVE || !browserOpenAiKey) return;
      try {
        await fetch("https://api.openai.com/v1/models?limit=1", {
          headers: { "Authorization": `Bearer ${browserOpenAiKey}` },
        });
      } catch (_) {}
    };
    return Object.freeze({
      ready, request, storeCredentials, refresh, clear, prewarm,
      hasOpenAi: () => openAiConfigured,
      hasDashcamRtsp: () => dashcamRtspConfigured,
      hadLegacyCredential: () => hadLegacyCredential,
      isNative: () => NATIVE,
    });
  })();
  window.CredentialBroker = CredentialBroker;

  const S = {
    get name() { return (localStorage.getItem("sender_name") || "").trim() || "A concerned citizen"; },
    get debug() { return localStorage.getItem("debug_mode") === "1"; },
    get model() { return normaliseModel(localStorage.getItem("detection_model")); },
    get detail() { return normaliseDetail(localStorage.getItem("image_detail"), this.model); },
  };

  const LANG = () => {
    const value = localStorage.getItem("app_lang");
    return value === "uz" ? "uz" : "en";
  };
  const PROGRESS = {
    en: { compress: "Preparing photo...", capture: "Preparing road views...",
          detect: "AI checking: pothole YES or NO...", finalize: "Checking location...",
          repair: "Comparing this revisit with the saved pothole...",
          write: "Saving the report..." },
    uz: { compress: "Rasm tayyorlanmoqda...", capture: "Yo'l kadrlari tayyorlanmoqda...",
          detect: "AI tekshirmoqda: chuqur HA yoki YO'Q...", finalize: "Joylashuv tekshirilmoqda...",
          repair: "Qayta o'tish saqlangan chuqur bilan solishtirilmoqda...",
          write: "Hisobot saqlanmoqda..." },
  };
  const pmsg = (k) => (PROGRESS[LANG()] && PROGRESS[LANG()][k]) || PROGRESS.en[k];

  const DEFAULT_MODEL = "gpt-5-mini";
  // Live private-media regression on the exact Drive contract found materially better
  // recall from gpt-5.6 while preserving every supplied hard negative. Manual Photo kept
  // better edge-cavity recall on gpt-5-mini. Keep the modes explicit and auditable.
  const DRIVE_DETECTION_MODEL = "gpt-5.6";
  const DRIVE_DETECTION_DETAIL = "original";
  const ALLOWED_MODELS = new Set([DEFAULT_MODEL, "gpt-5.6"]);
  const ALLOWED_DETAILS = new Set(["high", "original"]);
  const PROMPT_VERSION = "pothole-binary-v19";
  const PHOTO_PROMPT_VERSION = "pothole-photo-only-v5";
  const SCHEMA_VERSION = 9;
  const REPAIR_PROMPT_VERSION = "road-repair-v2";
  const REPAIR_SCHEMA_VERSION = 1;
  const MAX_DETECTION_IMAGES = 4;
  const MAX_REPAIR_IMAGES = 5;
  // Detection still examines every burst. Only after a burst is accepted do we group it
  // with a road-damage event already saved at the same place. This preserves capture
  // recall while stopping adjacent bursts and later drives from creating repeat drafts.
  const DEDUPE_ADJACENT_RADIUS_M = 12;
  const DEDUPE_HISTORY_RADIUS_M = 8;
  const DEDUPE_MISSING_HEADING_RADIUS_M = 5;
  const DEDUPE_SAME_DRIVE_S = 4;
  const DEDUPE_POOR_GPS_S = 2;
  const DEDUPE_HISTORY_S = 30 * 24 * 60 * 60;
  const ACCEPTED_REPORT_STATUSES = new Set(["draft", "queued", "sent"]);
  const REPAIR_MAX_ACCURACY_M = 12;
  const REPAIR_RADIUS_M = 5;
  const REPAIR_MISSING_HEADING_RADIUS_M = 3;
  const REPAIR_MAX_HEADING_DIFFERENCE_DEG = 35;
  const REPAIR_EVIDENCE_MIN_BYTES = 256;
  const REPAIR_EVIDENCE_MAX_BYTES = 8 * 1024 * 1024;
  const REPAIR_EVIDENCE_MIN_DIMENSION = 32;
  const REPAIR_EVIDENCE_MAX_DIMENSION = 8192;
  const REPAIR_EVIDENCE_MAX_PIXELS = 40 * 1024 * 1024;
  const REPAIR_EVIDENCE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

  const normaliseManualCaptureSource = (value) => value === "manual_camera"
    ? "manual_camera" : value === "manual_import" ? "manual_import" : "manual";
  const isManualCaptureSource = (value) => /^manual(?:_|$)/.test(String(value || ""));

  function normaliseModel(value) {
    return ALLOWED_MODELS.has(value) ? value : DEFAULT_MODEL;
  }
  function normaliseDetail(value, model) {
    const picked = ALLOWED_DETAILS.has(value) ? value : "high";
    // `original` is intentionally an experiment arm for the newest model. Older
    // vision models do not support it, so fail safely to their highest valid setting.
    return picked === "original" && model !== "gpt-5.6" ? "high" : picked;
  }

  /** Pure accounting for saved-video analysis; no skipped work can look successful. */
  function summarizeFootageAnalysis({
    planned, extracted, checked, failed, unreadableClips, aborted
  }) {
    const count = (value) => Math.max(0, Number(value) | 0);
    const totals = {
      planned: count(planned),
      extracted: count(extracted),
      checked: count(checked),
      failed: count(failed),
      unreadableClips: count(unreadableClips),
      aborted: !!aborted,
    };
    totals.skipped = Math.max(0, totals.planned - totals.checked - totals.failed);
    totals.complete = !totals.aborted && totals.failed === 0 &&
      totals.unreadableClips === 0 && totals.checked === totals.planned &&
      totals.extracted >= totals.checked;
    totals.incompleteItems = totals.failed + totals.skipped + totals.unreadableClips;
    return totals;
  }

  function vodSampleTimes(durationSeconds, stepSeconds) {
    const duration = Number(durationSeconds);
    const step = Number(stepSeconds);
    if (!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(step) || step <= 0) {
      return [];
    }
    const times = [];
    for (let at = Math.min(0.4, duration / 2); at < duration; at += step) times.push(at);
    return times;
  }

  function vodBurstTimes(atSeconds, durationSeconds, halfSpanSeconds = 0.4) {
    const at = Number(atSeconds);
    const duration = Number(durationSeconds);
    const halfSpan = Number(halfSpanSeconds);
    if (![at, duration, halfSpan].every(Number.isFinite) || duration <= 0 || halfSpan < 0) {
      return [];
    }
    const last = Math.max(0.001, duration - 0.001);
    return [Math.max(0.001, at - halfSpan), Math.min(last, Math.max(0.001, at)),
      Math.min(last, at + halfSpan)].filter((value, index, all) =>
      all.findIndex((other) => Math.abs(other - value) < 0.04) === index);
  }

  const DETECT_PROMPT = `You are a strict binary pothole detector for a civic complaint app. Inspect the supplied road views in chronological order and return only the structured fields in the schema. False positives are more harmful than false negatives: ambiguous geometry is NO.

A pothole is a localized wheel-dropping depression caused by missing, displaced, or disintegrated road-surface material. It does not need to be round, deep, dark, fully enclosed, or surrounded by intact pavement.

Return is_pothole true only when all are visible:
1. The damaged footprint lies on the surface the recording vehicle is actually traversing.
2. The footprint is lower than the adjacent wheel path and has localized material loss.
3. At least one side has an irregular broken lip, eroded edge, or abrupt material-height drop.
4. With multiple views, the same lower footprint moves or grows predictably as the vehicle approaches.
5. It is not an intentional raised speed breaker, hump, or rumble strip.

"Localized" means a stable, limited footprint within the traffic path; it does not mean a closed circular rim. Apply a stricter rule on an unfinished, gravel-covered, failed, or construction-stage lane. YES only when a compact depression or connected cavity cluster occupies part of a wheel path, has an abrupt irregular boundary against the adjacent traffic surface, and the same lower opening grows coherently in at least two chronological views. The floor may contain rubble or loose aggregate. It need not be fully exposed when a persistent broken lip or occlusion boundary together with visibly higher adjacent traffic surface proves the opening is lower. Set has_unambiguous_lower_interior true for that repeated geometric proof, never for colour, texture, stones, shadow, or coherent growth alone.

Temporary-surface decision clarification: A connected eroded cavity cluster occupying only part of a wheel path is localized. When a persistent broken or occluding near edge, a rubble-filled lower footprint, and visibly higher adjacent running surfaces move and enlarge together, return YES even if loose aggregate visually bridges or partly hides the floor. Do not relabel that bounded wheel-dropping cluster as distributed roughness merely because the lane is unfinished. This does not relax the NO rule for road-wide gravel, uniform grading, corrugation, scattered stones, or a construction scar with no bounded lower footprint.

Wet connected-cluster rule: Do not require a connected cavity cluster to be compact across the lane. A finite transverse band on the traversed temporary lane is localized when the same dark, wet, or rubble-filled concave footprint is bounded along the direction of travel by persistent irregular eroded height breaks and enlarges coherently. In that case mark all four physical evidence fields true even when water hides the floor and the cluster spans much of the lane; transverse concavity is not a raised speed breaker. Keep all four false for a flat wet band, stain, reflection, or puddle whose boundaries are only colour and have no higher approach/exit surface or eroded occluding lip.

Return NO for distributed gravel texture, scattered stones, gradual grading, exposed soil, a rolling wave or smooth rut across most of the lane, or a construction scar with no compact repeatable downward opening. Roughness, rubble, and a boundary line are never sufficient without both a localized footprint and a persistent abrupt drop from higher adjacent surface.

A compact water-filled opening may be YES only when a stable irregular eroded shoreline or broken lip encloses a bounded wet interior, the immediately adjacent traffic surface is visibly higher, and the same opening grows coherently through the approach. A flat puddle, reflection, wet stain, or broad water-covered low area without that stable broken boundary is NO. Water by itself never proves depth or material loss.

A shallow pothole is still YES when an irregular, compact area has a visibly lower interior relative to the immediate surrounding traffic surface and that geometry persists through the approach. A worn or rounded eroded lip or exposed aggregate may support that visible depression, but neither can replace it. Do not demand a steep wall, deep dark interior, fully visible floor, or sharp closed rim. A flat patch remains NO: colour, texture, a repair outline, or a height transition without an unambiguous lower interior is not a pothole.

General gravel texture, road-wide grading, corrugation, broad roughness with no local lower footprint, a wheel rut with smooth sides, loose debris resting on a level surface, a stain, shadow, puddle with no visible depressed boundary, intact patch, crack, seam, manhole, drain, shoulder erosion, construction obstacle, or damage outside the wheel-traversed surface is NO. A darker or rougher strip at a paved-to-loose-material transition is also NO when no interior is visibly lower than both adjacent surfaces; persistence of that flat transition across views is not depth evidence.

Speed-breaker hard veto: set looks_like_speed_breaker true and is_pothole false whenever the feature is or could reasonably be a raised transverse ridge. Painted bands or rectangles, reflectors, parallel leading/trailing edges, a vehicle jolt, and camera pitch support a breaker. A separate cavity beside a breaker is YES only when clearly distinct from the raised ridge; raised-versus-concave ambiguity is NO.

Utility-reinstatement veto: a circular manhole or utility-cover ring, collar, rectangular trench patch, or linear reinstatement around an intact cover is NO even when its repair material is rough, cracked, or slightly sunken. Return YES only for a separate irregular wheel-dropping cavity that clearly extends beyond the utility repair footprint and independently satisfies every pothole condition.

Surface type:
- bituminous_asphalt, cement_concrete, mastic_asphalt, or paver_blocks when identifiable;
- temporary_drivable_surface for an unsealed or construction-stage path that the recording vehicle traverses. In a forward-facing Drive burst, coherent forward motion along a continuous wheel path proves this use even when no second vehicle is visible;
- unpaved_or_nonroad for a shoulder, construction bed, work area, service path, or roadside ground not being traversed; otherwise unknown.
unpaved_or_nonroad and unknown are always NO.

A cavity at a road edge may be YES when its opening removes part of the flat traffic surface or creates a wheel-reachable drop, even if rubble extends beneath a raised roadside slab. It is NO when an intact kerb or gutter separates the entire opening from traffic.

Set has_localized_cavity, has_unambiguous_lower_interior, has_broken_edge_or_rim, and has_depth_or_surface_loss true only when the corresponding physical evidence above is present. has_unambiguous_lower_interior means the opening is demonstrably below its immediate surroundings, either by a visible lower interior or by a persistent broken lip or occlusion boundary beside visibly higher traffic surface. Texture, loose stones, shadow, a boundary line alone, or a raised ridge cannot satisfy it. Set image_quality unusable only when blur, darkness, glare, obstruction, or distance prevents a defensible judgment. For multiple views set temporal_consistency consistent when at least two show the same footprint; a feature leaving the final full frame is not disagreement. Use single_view for one user-framed photo.

After YES, set size to small below 30 cm, medium from 30 to 60 cm, or large above 60 cm or for a connected cavity cluster. For NO, size is null. These are visual app estimates, not official measurements. Keep description factual and never output confidence or probability.`;

  const PHOTO_ONLY_PROMPT_SUFFIX = `

Photo feature scope: detect potholes only. Garbage, litter, dumped waste, open or damaged manholes, drains, footpaths, and every other civic issue are not reportable in this feature and must return is_pothole false (NO). Never reinterpret them as another complaint category.`;

  // Key order is the streaming order. Eligibility fields precede the binary decision so
  // ordinary NOs still stop early while a temporary-surface near miss can finish and vote.
  const ASSESS_SCHEMA = {
    type: "object", additionalProperties: false,
    required: ["image_quality", "surface_type", "on_drivable_surface", "temporal_consistency",
      "looks_like_speed_breaker", "is_pothole", "has_localized_cavity",
      "has_unambiguous_lower_interior", "has_broken_edge_or_rim",
      "has_depth_or_surface_loss", "size", "description"],
    properties: {
      image_quality: { type: "string", enum: ["usable", "unusable"] },
      surface_type: { type: "string", enum: ["bituminous_asphalt", "cement_concrete",
        "mastic_asphalt", "paver_blocks", "temporary_drivable_surface",
        "unpaved_or_nonroad", "unknown"] },
      on_drivable_surface: { type: "boolean" },
      temporal_consistency: { type: "string", enum: ["consistent", "single_view", "inconsistent", "not_applicable"] },
      looks_like_speed_breaker: { type: "boolean" },
      is_pothole: { type: "boolean" },
      has_localized_cavity: { type: "boolean" },
      has_unambiguous_lower_interior: { type: "boolean" },
      has_broken_edge_or_rim: { type: "boolean" },
      has_depth_or_surface_loss: { type: "boolean" },
      size: { type: ["string", "null"], enum: ["small", "medium", "large", null] },
      description: { type: "string" },
    },
  };
  const REPAIR_PROMPT = `Compare a saved pothole photograph with new road views from a later live drive.

Image 1 is the older saved road-damage evidence. Image 2 is the current full-frame context. Every remaining image is a complete current camera frame in chronological order. No current image is cropped, tiled, masked, or limited to a region of interest.

This is a strict before/after verification, not ordinary pothole detection:
- Set same_location_visible true only when stable road geometry and surrounding features show that the old damaged footprint itself is visible in the current views. Nearby clean asphalt, a different lane, or a similar-looking road is not the same footprint.
- Set completed_repair_visible true only when that exact old footprint is now covered by completed, intact asphalt, concrete, or a sealed level patch on the drivable surface.
- The absence of a visible cavity is never repair evidence by itself. Blur, distance, glare, traffic, water, occlusion, a changed viewpoint, or failure to locate the old footprint must produce current_condition uncertain or not_visible.
- Use still_damaged if the old defect or a failed repair remains visible.
- Use repaired only when the same footprint and the completed intact repair are both clear. Do not infer repairs from time, GPS, or a generally smooth road.
- description must state the stable same-place cues and the visible repair material, or state why verification is inconclusive.`;
  const REPAIR_SCHEMA = {
    type: "object", additionalProperties: false,
    required: ["same_location_visible", "completed_repair_visible", "current_condition",
      "assessment", "image_quality", "description"],
    properties: {
      same_location_visible: { type: "boolean" },
      completed_repair_visible: { type: "boolean" },
      current_condition: { type: "string",
        enum: ["repaired", "still_damaged", "not_visible", "uncertain"] },
      assessment: { type: "string", enum: ["clear", "probable", "uncertain"] },
      image_quality: { type: "string", enum: ["usable", "degraded", "unusable"] },
      description: { type: "string" },
    },
  };
  // ---------- OpenAI ----------
  // SEC-006: finite request ceilings; native code independently validates/clamps them.
  function aiUsageLimitError() {
    const error = new Error("AI usage limit reached.");
    error.fatal = true; error.aiUsageLimit = true;
    return error;
  }

  function boundedAiRequest(body, stream) {
    if (!body || !ALLOWED_MODELS.has(body.model)) throw aiUsageLimitError();
    const name = body.text && body.text.format && body.text.format.name || "general";
    const ceiling = name === "pothole_binary_assessment" ? 1536
      : (name === "road_repair_assessment" || name === "road_repair_verification") ? 768
      : (name === "tender_match" || name === "general") ? 512 : 0;
    const requested = body.max_output_tokens === undefined ? ceiling : body.max_output_tokens;
    if (!ceiling || !Number.isSafeInteger(requested) || requested <= 0 || requested > 2147483647) throw aiUsageLimitError();
    return { ...body, stream: !!stream, max_output_tokens: Math.min(requested, ceiling) };
  }

  // Detection is a classification job, not an essay: left at its default the model
  // spends 200+ hidden reasoning tokens per photo before answering, which measured
  // as roughly 3.5 of the 6.5 seconds a verdict used to take.
  const withSpeedDefaults = (body) => ({
    ...boundedAiRequest(body, body && body.stream),
    // Detection inputs can contain precise road imagery and addresses. Do not retain
    // response application state beyond the request; provider abuse-monitoring rules
    // remain governed by OpenAI's published policy and are disclosed in our policy.
    store: false,
    reasoning: (body && body.reasoning)
      || { effort: body && body.model === "gpt-5.6" ? "none" : "minimal" },
  });

  // Fatal means "fails the same way without streaming", so retrying plain is pointless.
  const fatal = (e) => { e.fatal = true; return e; };
  // A stalled request is worse than a failed one: without this a lost connection
  // leaves the UI on a spinner with no end, and a drive quietly stops forever.
  const REQUEST_TIMEOUT_MS = 30000;

  // The timeout used to be cleared the moment the headers arrived, so it only ever covered
  // the handshake. A response that sent headers and then stalled was never aborted, and a
  // drive wedged with every slot occupied while the HUD went on reporting it healthy.
  //
  // The timer now stays armed until the body is finished. A streaming caller re-arms it on
  // every chunk that carries data, so a slow but live response is fine and a silent one is
  // not, and disarms it when the body is done.
  async function fetchWithTimeout(url, init, ms = REQUEST_TIMEOUT_MS) {
    const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    let timer = setTimeout(() => ctl && ctl.abort(), ms);
    const disarm = () => { clearTimeout(timer); timer = null; };
    const rearm = (delay) => {
      if (timer === null) return;             // already finished
      clearTimeout(timer);
      timer = setTimeout(() => ctl && ctl.abort(), delay === undefined ? ms : delay);
    };
    let res;
    try {
      res = await fetch(url, ctl ? { ...init, signal: ctl.signal } : init);
    } catch (e) {
      disarm();
      if (e && (e.name === "AbortError" || /abort/i.test(e.message || ""))) {
        const to = new Error("The network did not respond. Check the connection and try again.");
        to.timeout = true;
        throw to;
      }
      // Platform network errors read like `Unable to resolve host "api.openai.com"`.
      // Nobody watching a demo should be shown that.
      throw new Error("Could not reach OpenAI. Check the connection and try again.");
    }
    res.__cancel = () => ctl && ctl.abort();
    res.__disarm = disarm;
    res.__rearm = rearm;
    return res;
  }

  // Reading a body must always disarm the watchdog, including when it throws.
  async function readJson(res) {
    try { return await res.json(); }
    finally { if (res.__disarm) res.__disarm(); }
  }

  // Never surface a provider's response body: it is JSON, it is long, and on a
  // projected screen it reads as a crash.
  async function statusError(res) {
    const bad = mapStatus(res);
    if (bad) return bad;
    if (res.status === 400) return new Error("OpenAI rejected the request. If this persists, the app needs an update.");
    if (res.status === 408 || res.status === 504) return new Error("OpenAI timed out. Try again.");
    if (res.status >= 500) return new Error("OpenAI is having trouble right now. Try again in a moment.");
    return new Error("OpenAI could not process that image. Try again.");
  }

  function mapStatus(res) {
    if (res.status === 401) return fatal(new Error("OpenAI rejected the API key. Check it in settings."));
    if (res.status === 403) return fatal(new Error("This API key is not allowed to use the model. Check the key in settings."));
    // 429 covers both throttling and an exhausted balance, and telling someone to
    // wait a minute for a spent quota sends them in circles.
    if (res.status === 429) return fatal(new Error("OpenAI refused: rate limit or the key's credit is exhausted. Check the account."));
    return null;
  }

  async function oai(body) {
    return withInferenceResponse(body, false, async (res, context) => {
      const buffer = new Uint8Array(context.limits.responseBytes);
      let size = 0;
      await readInferenceChunks(res, context, bytes => { buffer.set(bytes, size); size += bytes.byteLength; return false; });
      context.checkActive();
      let data;
      try { data = parseInferenceJson(new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, size))); }
      catch (_) { throw inferenceSafetyError(); }
      if (!data || !Array.isArray(data.output)) throw inferenceSafetyError();
      const msg = data.output.find(o => o && o.type === "message");
      const text = msg && Array.isArray(msg.content) && msg.content.find(c => c && c.type === "output_text");
      if (!text || typeof text.text !== "string" || !text.text) throw inferenceSafetyError();
      inferenceUtf8Size(text.text, INFERENCE_SSE_LIMITS.responseBytes);
      return parseInferenceJson(text.text);
    });
  }

  // Structured outputs stream in schema order. The same hard binary gate is used for
  // streamed and final paths, so the UI cannot announce YES and later reverse it.
  const IS_POTHOLE_RE = /"is_pothole"\s*:\s*(true|false)/;
  const SPEED_BREAKER_RE = /"looks_like_speed_breaker"\s*:\s*(true|false)/;
  const QUALITY_RE = /"image_quality"\s*:\s*"(usable|unusable)"/;
  const SURFACE_RE = /"surface_type"\s*:\s*"(bituminous_asphalt|cement_concrete|mastic_asphalt|paver_blocks|temporary_drivable_surface|unpaved_or_nonroad|unknown)"/;
  const ROAD_RE = /"on_drivable_surface"\s*:\s*(true|false)/;
  const CAVITY_RE = /"has_localized_cavity"\s*:\s*(true|false)/;
  const LOWER_INTERIOR_RE = /"has_unambiguous_lower_interior"\s*:\s*(true|false)/;
  const EDGE_RE = /"has_broken_edge_or_rim"\s*:\s*(true|false)/;
  const DEPTH_RE = /"has_depth_or_surface_loss"\s*:\s*(true|false)/;
  const TEMPORAL_RE = /"temporal_consistency"\s*:\s*"(consistent|single_view|inconsistent|not_applicable)"/;
  const SIZE_RE = /"size"\s*:\s*(?:"(small|medium|large)"|null)/;
  const POTHOLE_SIZES = new Set(["small", "medium", "large"]);
  const PAVED_SURFACES = new Set(["bituminous_asphalt", "cement_concrete",
    "mastic_asphalt", "paver_blocks"]);
  const TEMPORARY_DRIVABLE_SURFACE = "temporary_drivable_surface";
  const REPORTABLE_SURFACES = new Set([...PAVED_SURFACES, TEMPORARY_DRIVABLE_SURFACE]);
  const KNOWN_SURFACES = new Set([...REPORTABLE_SURFACES, "unpaved_or_nonroad", "unknown"]);
  const LEGACY_NATIVE_V16_PROMPT_VERSION = "pothole-binary-v16";
  const LEGACY_NATIVE_V16_SCHEMA_VERSION = 8;
  const LEGACY_NATIVE_V15_PROMPT_VERSION = "pothole-binary-v15";
  const LEGACY_NATIVE_V15_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V13_PROMPT_VERSION = "pothole-binary-v13";
  const LEGACY_NATIVE_V13_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V12_PROMPT_VERSION = "pothole-binary-v12";
  const LEGACY_NATIVE_V12_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V10_PROMPT_VERSION = "pothole-binary-v10";
  const LEGACY_NATIVE_V10_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V9_PROMPT_VERSION = "pothole-binary-v9";
  const LEGACY_NATIVE_V9_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V8_PROMPT_VERSION = "pothole-binary-v8";
  const LEGACY_NATIVE_V8_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V7_PROMPT_VERSION = "pothole-binary-v7";
  const LEGACY_NATIVE_V7_SCHEMA_VERSION = 7;
  const LEGACY_NATIVE_V6_PROMPT_VERSION = "pothole-binary-v6";
  const LEGACY_NATIVE_V6_SCHEMA_VERSION = 6;

  function nativeDetectorContract(native) {
    if (!native || typeof native !== "object") return null;
    if (native.prompt_version === PROMPT_VERSION
        && Number(native.schema_version) === SCHEMA_VERSION) {
      return { kind: "current_v19", surfaceTypes: REPORTABLE_SURFACES };
    }
    if (native.prompt_version === LEGACY_NATIVE_V16_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V16_SCHEMA_VERSION) {
      return { kind: "legacy_v16", surfaceTypes: REPORTABLE_SURFACES };
    }
    if (native.prompt_version === LEGACY_NATIVE_V15_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V15_SCHEMA_VERSION) {
      return { kind: "legacy_v15", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v13 was the first complete-frame Drive contract. Preserve accepted and pending
    // rows from the preceding release, including their complete evidence image.
    if (native.prompt_version === LEGACY_NATIVE_V13_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V13_SCHEMA_VERSION) {
      return { kind: "legacy_v13", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v12 used the same strict schema with cropped temporal views. Existing accepted and
    // pending rows remain importable, but all new inference uses complete camera frames.
    if (native.prompt_version === LEGACY_NATIVE_V12_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V12_SCHEMA_VERSION) {
      return { kind: "legacy_v12", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v10 used the same strict fields and remains valid for unsynced rows captured by
    // the previous GitHub release. Its prompt differed, so retain provenance.
    if (native.prompt_version === LEGACY_NATIVE_V10_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V10_SCHEMA_VERSION) {
      return { kind: "legacy_v10", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v9 used the same strict fields and remains valid for unsynced rows captured by
    // the previous GitHub release. Its prompt and crop differed, so retain provenance.
    if (native.prompt_version === LEGACY_NATIVE_V9_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V9_SCHEMA_VERSION) {
      return { kind: "legacy_v9", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v8 used the same strict fields and remains valid for unsynced rows captured by
    // the previous GitHub release. Its prompt differed, so keep the provenance explicit.
    if (native.prompt_version === LEGACY_NATIVE_V8_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V8_SCHEMA_VERSION) {
      return { kind: "legacy_v8", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v7 used the same strict schema and temporary-surface vocabulary. Preserve pending
    // and accepted rows captured immediately before the prompt/crop upgrade.
    if (native.prompt_version === LEGACY_NATIVE_V7_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V7_SCHEMA_VERSION) {
      return { kind: "legacy_v7", surfaceTypes: REPORTABLE_SURFACES };
    }
    // v6 knew only sealed paved surfaces and cannot authorize the temporary class.
    if (native.prompt_version === LEGACY_NATIVE_V6_PROMPT_VERSION
        && Number(native.schema_version) === LEGACY_NATIVE_V6_SCHEMA_VERSION) {
      return { kind: "legacy_v6", surfaceTypes: PAVED_SURFACES };
    }
    return null;
  }

  function decisionFor(a, driveMode = false, sourceViewCount = null) {
    // The model supplies YES/NO, but YES still has to satisfy every physical invariant.
    // Anything missing, ambiguous, off-road, raised, or poorly visible becomes NO.
    if (!a || a.is_pothole !== true || a.looks_like_speed_breaker !== false) return "reject";
    if (a.image_quality !== "usable" || !REPORTABLE_SURFACES.has(a.surface_type)
        || a.on_drivable_surface !== true ||
        a.has_localized_cavity !== true) return "reject";
    if (typeof a.has_unambiguous_lower_interior !== "boolean") return "reject";
    if (a.surface_type === TEMPORARY_DRIVABLE_SURFACE &&
        a.has_unambiguous_lower_interior !== true) return "reject";
    if (a.has_broken_edge_or_rim !== true || a.has_depth_or_surface_loss !== true) return "reject";
    // An unfinished surface can be distinguished from ordinary gravel/ruts only from a
    // chronological Drive burst. A single user-framed Photo must fail closed here even
    // if the model contradicts the prompt and calls it reportable.
    if (a.surface_type === TEMPORARY_DRIVABLE_SURFACE && !driveMode) return "reject";
    if (driveMode) {
      // Repeated encodings of one frame are not temporal corroboration.
      if (a.temporal_consistency !== "consistent" || sourceViewCount < 2) return "reject";
    } else if (a.temporal_consistency !== "consistent" && a.temporal_consistency !== "single_view") {
      return "reject";
    }
    if (!POTHOLE_SIZES.has(a.size)) return "reject";
    return "accept";
  }

  function binaryAssessment(a, driveMode = false, sourceViewCount = null) {
    const accepted = decisionFor(a, driveMode, sourceViewCount) === "accept";
    return {
      ...(a || {}),
      is_pothole: accepted,
      // Compatibility fields keep existing reports, complaint rendering and Room sync
      // readable. They are derived locally; the model no longer predicts them.
      reportable: accepted,
      assessment: accepted ? "clear" : "absent",
      damage_type: accepted ? "pothole_cavity" : "none",
      defect_type: accepted ? "pothole" : "not_pothole",
      surface_type: KNOWN_SURFACES.has(a && a.surface_type) ? a.surface_type : "unknown",
      // No pixel-to-centimetre conversion is defensible without a scale reference.
      // Keep the useful visual class, but make the absent physical measurements explicit.
      measurement_provenance: accepted ? "visual_estimate_no_scale" : "not_applicable",
      measurement_confidence: accepted ? "low" : "not_applicable",
      measurement_length_cm: null,
      measurement_width_cm: null,
      measurement_depth_cm: null,
      size: accepted ? a.size : null,
    };
  }

  const temporarySurfaceVoteEligible = (a, driveMode = false) =>
    !!driveMode && !!a && a.looks_like_speed_breaker === false
      && a.image_quality === "usable"
      && a.surface_type === TEMPORARY_DRIVABLE_SURFACE
      && a.on_drivable_surface === true
      && a.temporal_consistency === "consistent";

  const temporarySurfaceNeedsConfirmation = (a, driveMode = false) =>
    temporarySurfaceVoteEligible(a, driveMode);

  function temporarySurfaceVoteNeedsAnother(attempts, driveMode = false,
                                             sourceViewCount = null) {
    if (!Array.isArray(attempts) || !attempts.length || attempts.length >= 3
        || attempts.some((item) => !temporarySurfaceVoteEligible(item, driveMode))) return false;
    const accepts = attempts.filter((item) =>
      decisionFor(item, true, sourceViewCount) === "accept").length;
    const rejects = attempts.length - accepts;
    return accepts < 2 && rejects < 2;
  }

  function confirmedTemporaryAssessment(first, second, driveMode = false,
                                        sourceViewCount = null, third = null) {
    if (!temporarySurfaceVoteEligible(first, driveMode)) {
      return binaryAssessment(first, driveMode, sourceViewCount);
    }
    const attempts = [first, second, third].filter(Boolean);
    const accepts = attempts.filter((item) => temporarySurfaceVoteEligible(item, driveMode)
      && decisionFor(item, true, sourceViewCount) === "accept");
    if (attempts.length >= 2 && attempts.every((item) =>
        temporarySurfaceVoteEligible(item, driveMode)) && accepts.length >= 2) {
      return binaryAssessment(accepts[accepts.length - 1], true, sourceViewCount);
    }
    const basis = attempts[attempts.length - 1] || first || {};
    return binaryAssessment({
      ...basis,
      is_pothole: false,
      size: null,
      description: "Temporary-surface pothole was not independently confirmed.",
    }, true, sourceViewCount);
  }

  const clearAbsenceForRepair = (a) => !!a
    && a.is_pothole === false
    && a.looks_like_speed_breaker === false
    && a.image_quality === "usable"
    && a.has_localized_cavity === false
    && a.has_unambiguous_lower_interior === false
    && a.has_broken_edge_or_rim === false
    && a.has_depth_or_surface_loss === false
    && a.size == null;

  function repairConditionFor(observation) {
    if (!observation || observation.current_condition !== "repaired"
        || observation.same_location_visible !== true
        || observation.completed_repair_visible !== true
        || observation.image_quality !== "usable") return null;
    if (observation.assessment === "clear") return "fixed";
    if (observation.assessment === "probable") return "repair_review";
    return null;
  }

  function partialAssessment(text) {
    const verdict = IS_POTHOLE_RE.exec(text);
    if (!verdict) return null;
    const breaker = SPEED_BREAKER_RE.exec(text), quality = QUALITY_RE.exec(text);
    const surface = SURFACE_RE.exec(text);
    const road = ROAD_RE.exec(text), temporal = TEMPORAL_RE.exec(text);
    if (verdict[1] === "false") {
      if (breaker && quality && surface && road && temporal
          && breaker[1] === "false" && quality[1] === "usable"
          && surface[1] === TEMPORARY_DRIVABLE_SURFACE && road[1] === "true"
          && temporal[1] === "consistent") return null;
      return binaryAssessment({
        is_pothole: false,
        looks_like_speed_breaker: breaker ? breaker[1] === "true" : false,
        image_quality: quality ? quality[1] : "usable",
        surface_type: surface ? surface[1] : "unknown",
        on_drivable_surface: !!road && road[1] === "true",
        has_localized_cavity: false, has_unambiguous_lower_interior: false,
        has_broken_edge_or_rim: false, has_depth_or_surface_loss: false,
        temporal_consistency: temporal ? temporal[1] : "not_applicable", size: null,
      });
    }
    const cavity = CAVITY_RE.exec(text);
    const lowerInterior = LOWER_INTERIOR_RE.exec(text);
    const edge = EDGE_RE.exec(text), depth = DEPTH_RE.exec(text);
    const size = SIZE_RE.exec(text);
    if (!breaker || !quality || !surface || !road || !cavity || !lowerInterior ||
        !edge || !depth || !temporal || !size) return null;
    return {
      is_pothole: true,
      looks_like_speed_breaker: breaker[1] === "true",
      image_quality: quality[1],
      surface_type: surface[1],
      on_drivable_surface: road[1] === "true",
      has_localized_cavity: cavity[1] === "true",
      has_unambiguous_lower_interior: lowerInterior[1] === "true",
      has_broken_edge_or_rim: edge[1] === "true",
      has_depth_or_surface_loss: depth[1] === "true",
      temporal_consistency: temporal[1],
      size: size[1] || null,
    };
  }

  const peekVerdict = (partial) => {
    const a = partialAssessment(partial);
    if (!a) return null;
    const decision = decisionFor(a);
    return { accepted: decision === "accept", review: false,
             damage_type: decision === "accept" ? "pothole_cavity" : "none",
             assessment: decision === "accept" ? "clear" : "absent" };
  };

  // True once the response has proved that Drive Mode will not create a complaint.
  // Debug/evaluation calls do not enable cancellation because they need the exact full
  // verdict, including the reason for a miss.
  const peekReject = (partial, driveMode = false) => {
    const breaker = SPEED_BREAKER_RE.exec(partial);
    if (breaker && breaker[1] === "true") return true;
    const verdict = IS_POTHOLE_RE.exec(partial);
    if (!verdict) return false;
    if (verdict[1] === "false") {
      const quality = QUALITY_RE.exec(partial), surface = SURFACE_RE.exec(partial);
      const road = ROAD_RE.exec(partial), temporal = TEMPORAL_RE.exec(partial);
      const eligibleTemporaryNo = driveMode && quality && surface && road && temporal && breaker
        && quality[1] === "usable" && surface[1] === TEMPORARY_DRIVABLE_SURFACE
        && road[1] === "true" && temporal[1] === "consistent" && breaker[1] === "false";
      return !eligibleTemporaryNo;
    }
    const a = partialAssessment(partial);
    return !!a && decisionFor(a, driveMode, driveMode ? 2 : null) !== "accept";
  };

  // SEC-005: byte-first inference framing; limits are native/browser equivalents.
  const INFERENCE_SSE_LIMITS = Object.freeze({ responseBytes: 64 * 1024,
    lineBytes: 32 * 1024, eventBytes: 48 * 1024, events: 512, deadlineMs: 35000 });

  function inferenceSafetyError() {
    const error = new Error("Inference response violated its safety budget or protocol.");
    error.inferenceSafety = true;
    error.fatal = true; // Do not retry hostile framing through the unstreamed fallback.
    return error;
  }

  function inferenceUtf8Size(text, limit, rejectReplacement = false) {
    if (typeof text !== "string" || text.length > limit) throw inferenceSafetyError();
    let size = 0;
    for (let i = 0; i < text.length; i++) {
      const c = text.charCodeAt(i);
      if (rejectReplacement && c === 0xfffd) throw inferenceSafetyError();
      let bytes = c < 0x80 ? 1 : c < 0x800 ? 2 : 3;
      if (c >= 0xd800 && c <= 0xdbff) {
        const next = text.charCodeAt(++i);
        if (!(next >= 0xdc00 && next <= 0xdfff)) throw inferenceSafetyError();
        bytes = 4;
      } else if (c >= 0xdc00 && c <= 0xdfff) throw inferenceSafetyError();
      if (bytes > limit - size) throw inferenceSafetyError();
      size += bytes;
    }
    return size;
  }

  function validateInferenceLimits(limits) {
    for (const key of Object.keys(INFERENCE_SSE_LIMITS)) {
      if (!Number.isSafeInteger(limits[key]) || limits[key] <= 0 ||
          limits[key] > INFERENCE_SSE_LIMITS[key]) throw inferenceSafetyError();
    }
  }

  function createInferenceSseState(limits = INFERENCE_SSE_LIMITS) {
    validateInferenceLimits(limits);
    return { limits, line: new Uint8Array(limits.lineBytes), event: new Uint8Array(limits.eventBytes),
      lineSize: 0, eventSize: 0, hasData: false, events: 0, bytes: 0, skipLf: false,
      text: "", textBytes: 0, early: false, stop: false, transportCompleted: false };
  }

  function parseInferenceJson(text) {
    let depth = 0, quoted = false, escaped = false;
    for (const char of text) {
      if (quoted) {
        if (escaped) escaped = false;
        else if (char === "\\") escaped = true;
        else if (char === '"') quoted = false;
      } else if (char === '"') quoted = true;
      else if (char === "{" || char === "[") { if (++depth > 32) throw inferenceSafetyError(); }
      else if (char === "}" || char === "]") depth--;
    }
    try { return JSON.parse(text); } catch (_) { throw inferenceSafetyError(); }
  }

  function dispatchInferenceEvent(state, onEarly, stopWhenRejected) {
    if (!state.hasData) return;
    if (state.events >= state.limits.events) throw inferenceSafetyError();
    state.events++;
    let payload;
    try { payload = new TextDecoder("utf-8", { fatal: true }).decode(state.event.subarray(0, state.eventSize)); }
    catch (_) { throw inferenceSafetyError(); }
    state.hasData = false; state.eventSize = 0;
    if (payload.trim() === "[DONE]") { state.transportCompleted = true; return; }
    let ev;
    ev = parseInferenceJson(payload);
    if (!ev || Array.isArray(ev) || typeof ev.type !== "string" ||
        !ev.type.startsWith("response.") || ev.type.length > 128 ||
        ev.type === "response.failed" || ev.type === "response.incomplete") throw inferenceSafetyError();
    if (ev.type === "response.completed") { state.transportCompleted = true; return; }
    if (ev.type !== "response.output_text.delta") return;
    if (typeof ev.delta !== "string") throw inferenceSafetyError();
    const deltaBytes = inferenceUtf8Size(ev.delta, INFERENCE_SSE_LIMITS.responseBytes - state.textBytes);
    state.textBytes += deltaBytes;
    state.text += ev.delta;
    if (!state.early && onEarly) {
      const value = peekVerdict(state.text);
      if (value) { state.early = true; try { onEarly(value); } catch (_) {} }
    }
    if (stopWhenRejected && peekReject(state.text, true)) state.stop = true;
  }

  function finishInferenceLine(state, onEarly, stopWhenRejected) {
    if (!state.lineSize) { dispatchInferenceEvent(state, onEarly, stopWhenRejected); return; }
    let line;
    try { line = new TextDecoder("utf-8", { fatal: true }).decode(state.line.subarray(0, state.lineSize)); }
    catch (_) { throw inferenceSafetyError(); }
    state.lineSize = 0;
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    if (colon < 0) throw inferenceSafetyError();
    const field = line.slice(0, colon);
    const value = line.slice(colon + 1 + (line[colon + 1] === " " ? 1 : 0));
    if (field === "data") {
      const data = new TextEncoder().encode(value); // The raw line is already bounded.
      const separator = state.hasData ? 1 : 0;
      if (separator > state.limits.eventBytes - state.eventSize ||
          data.byteLength > state.limits.eventBytes - state.eventSize - separator) throw inferenceSafetyError();
      if (state.hasData) state.event[state.eventSize++] = 10;
      state.event.set(data, state.eventSize); state.eventSize += data.byteLength; state.hasData = true;
    } else if (field === "event") { if (!value) throw inferenceSafetyError(); }
    else if (field === "id") { if (value.includes("\u0000")) throw inferenceSafetyError(); }
    else if (field === "retry") { if (!/^[0-9]+$/.test(value)) throw inferenceSafetyError(); }
    else throw inferenceSafetyError();
  }

  function drainSSE(chunk, state, onEarly, stopWhenRejected, checkActive = () => {}) {
    if (!(chunk instanceof Uint8Array) || chunk.byteLength > state.limits.responseBytes - state.bytes) throw inferenceSafetyError();
    state.bytes += chunk.byteLength;
    for (const byte of chunk) {
      checkActive();
      if (state.transportCompleted || state.stop) return;
      if (byte === 13) { finishInferenceLine(state, onEarly, stopWhenRejected); state.skipLf = true; }
      else if (byte === 10) { if (!state.skipLf) finishInferenceLine(state, onEarly, stopWhenRejected); state.skipLf = false; }
      else {
        state.skipLf = false;
        if (state.lineSize >= state.limits.lineBytes) throw inferenceSafetyError();
        state.line[state.lineSize++] = byte;
      }
    }
  }

  async function readInferenceChunks(res, context, consume) {
    const rawLength = res.headers && res.headers.get("content-length");
    let declared = null;
    if (rawLength !== null && rawLength !== undefined) {
      if (!/^[0-9]+$/.test(rawLength)) throw inferenceSafetyError();
      declared = Number(rawLength);
      if (!Number.isSafeInteger(declared) || declared < 0 || declared > context.limits.responseBytes) throw inferenceSafetyError();
    }
    const encoding = res.headers && res.headers.get("content-encoding");
    const identity = !encoding || encoding.toLowerCase() === "identity";
    let total = 0;
    const accept = chunk => {
      context.checkActive();
      if (!(chunk instanceof Uint8Array) || chunk.byteLength > context.limits.responseBytes - total ||
          (identity && declared !== null && chunk.byteLength > declared - total)) throw inferenceSafetyError();
      total += chunk.byteLength;
      return consume(chunk);
    };
    if (res.body && typeof res.body.getReader === "function") {
      context.reader = res.body.getReader();
      while (true) {
        context.checkActive();
        const { done, value } = await Promise.race([context.reader.read(), context.cancelled]);
        context.checkActive();
        if (done) break;
        if (accept(value)) return;
      }
      if (identity && declared !== null && total !== declared) throw inferenceSafetyError();
    } else {
      // SEC-001's native gateway has already bounded this string to 1 MiB/35 s.
      // Browser bodies without streaming support fail closed; no unbounded .text().
      if (!NATIVE) throw inferenceSafetyError();
      const text = await Promise.race([res.text(), context.cancelled]);
      context.checkActive();
      inferenceUtf8Size(text, context.limits.responseBytes, true);
      const bytes = new TextEncoder().encode(text); // At most 64 KiB, checked before encoding.
      for (let i = 0; i < bytes.length; i += 4096) {
        if (accept(bytes.subarray(i, Math.min(i + 4096, bytes.length)))) return;
      }
    }
  }

  async function withInferenceResponse(body, stream, consume, signal = null, limits = INFERENCE_SSE_LIMITS) {
    validateInferenceLimits(limits);
    const controller = new AbortController();
    let response = null, timedOut = false, timer = null;
    const cancel = () => controller.abort();
    let rejectCancelled;
    const cancelled = new Promise((_, reject) => { rejectCancelled = reject; });
    cancelled.catch(() => {});
    const started = performance.now();
    const context = { limits, reader: null, cancelled,
      checkActive: () => {
        if (!controller.signal.aborted && performance.now() - started >= limits.deadlineMs) {
          timedOut = true; controller.abort();
        }
        if (controller.signal.aborted) {
          const error = new Error(timedOut ? "Inference response deadline exceeded." : "Inference response cancelled.");
          if (timedOut) error.timeout = true; else error.name = "AbortError";
          throw error;
        }
      } };
    const abort = () => {
      try { context.checkActive(); } catch (error) { rejectCancelled(error); }
      if (response && response.__cancel) response.__cancel();
      if (context.reader) { try { Promise.resolve(context.reader.cancel()).catch(() => {}); } catch (_) {} }
    };
    controller.signal.addEventListener("abort", abort, { once: true });
    if (signal) { signal.addEventListener("abort", cancel, { once: true }); if (signal.aborted) controller.abort(); }
    try {
      context.checkActive();
      timer = setTimeout(() => { timedOut = true; controller.abort(); }, limits.deadlineMs);
      const pending = CredentialBroker.request(withSpeedDefaults({ ...body, stream }), stream);
      pending.then(res => {
        if (controller.signal.aborted) {
          if (res.__cancel) res.__cancel();
          if (res.__disarm) res.__disarm();
          try { Promise.resolve(res.body && res.body.cancel()).catch(() => {}); } catch (_) {}
        }
      }, () => {});
      response = await Promise.race([pending, cancelled]);
      context.checkActive();
      if (!response.ok) throw await statusError(response);
      const result = await Promise.race([consume(response, context), cancelled]);
      context.checkActive();
      return result;
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener("abort", cancel);
      if (response && response.__disarm) response.__disarm();
      controller.abort();
      if (context.reader) { try { context.reader.releaseLock(); } catch (_) {} context.reader = null; }
      else if (response && response.body) { try { Promise.resolve(response.body.cancel()).catch(() => {}); } catch (_) {} }
    }
  }

  async function oaiStream(body, onEarly, stopWhenRejected, signal = null, limits = INFERENCE_SSE_LIMITS) {
    return withInferenceResponse(body, true, async (res, context) => {
      const state = createInferenceSseState(limits);
      try {
        await readInferenceChunks(res, context, bytes => {
          drainSSE(bytes, state, onEarly, stopWhenRejected, context.checkActive);
          return state.stop || state.transportCompleted;
        });
        context.checkActive();
        if (state.stop) return rejectedVerdict(state.text);
        if (!state.transportCompleted) {
          const error = new Error("Detection stream ended before OpenAI confirmed completion.");
          error.incompleteStream = true; throw error;
        }
        if (!state.text) throw inferenceSafetyError();
        return parseInferenceJson(state.text);
      } finally { state.line = null; state.event = null; state.text = ""; }
    }, signal, limits);
  }

  // Reconstructed from the closed fields that arrived before Drive Mode cancelled the
  // remaining description. It deliberately has the complete new schema shape.
  function rejectedVerdict(text) {
    const verdict = IS_POTHOLE_RE.exec(text), breaker = SPEED_BREAKER_RE.exec(text);
    const quality = QUALITY_RE.exec(text), surface = SURFACE_RE.exec(text);
    const road = ROAD_RE.exec(text), cavity = CAVITY_RE.exec(text);
    const lowerInterior = LOWER_INTERIOR_RE.exec(text);
    const edge = EDGE_RE.exec(text);
    const depth = DEPTH_RE.exec(text), temporal = TEMPORAL_RE.exec(text), size = SIZE_RE.exec(text);
    return binaryAssessment({
      is_pothole: !!verdict && verdict[1] === "true",
      looks_like_speed_breaker: breaker ? breaker[1] === "true" : true,
      image_quality: quality ? quality[1] : "unusable",
      surface_type: surface ? surface[1] : "unknown",
      on_drivable_surface: !!road && road[1] === "true",
      has_localized_cavity: !!cavity && cavity[1] === "true",
      has_unambiguous_lower_interior:
        !!lowerInterior && lowerInterior[1] === "true",
      has_broken_edge_or_rim: !!edge && edge[1] === "true",
      has_depth_or_surface_loss: !!depth && depth[1] === "true",
      temporal_consistency: temporal ? temporal[1] : "not_applicable",
      size: size ? (size[1] || null) : null,
      description: "",
    });
  }

  const fmt = (name, schema) => ({
    format: { type: "json_schema", name, schema, strict: true },
    verbosity: "low",
  });
  const progress = (m) => { try { window.dispatchEvent(new CustomEvent("pipeline-progress", { detail: m })); } catch (e) {} };
  const emitVerdict = (v) => { try { window.dispatchEvent(new CustomEvent("pipeline-verdict", { detail: v })); } catch (e) {} };

  function buildDetectionRequest(imageInputs, prompt, model = S.model, detail = S.detail,
                                 formatName = "pothole_binary_assessment", schema = ASSESS_SCHEMA) {
    const selectedModel = normaliseModel(model);
    const selectedDetail = normaliseDetail(detail, selectedModel);
    const imageLimit = schema === REPAIR_SCHEMA ? MAX_REPAIR_IMAGES : MAX_DETECTION_IMAGES;
    const images = (Array.isArray(imageInputs) ? imageInputs : [imageInputs])
      .filter((x) => x && (typeof x === "string" ? x : x.url))
      .slice(0, imageLimit);
    if (!images.length) throw new Error("No usable image supplied for detection.");
    const content = [];
    for (let i = 0; i < images.length; i++) {
      const item = typeof images[i] === "string" ? { url: images[i] } : images[i];
      content.push({ type: "input_image", image_url: item.url,
                     detail: normaliseDetail(item.detail || selectedDetail, selectedModel) });
    }
    // The prompt appears exactly once and follows the ordered evidence views.
    content.push({ type: "input_text", text: `${prompt}\n\nThe ${images.length} supplied image(s) are ordered exactly as labelled by the capture pipeline.` });
    return {
      model: selectedModel,
      max_output_tokens: schema === REPAIR_SCHEMA ? 768 : 1536,
      input: [{ role: "user", content }],
      text: fmt(formatName, schema),
    };
  }

  let streamBroken = false;
  async function analyzeImage(imageInputs, prompt, name, schema, model, onEarly,
                              stopWhenRejected, detail, reasoningEffort = null) {
    const body = (schema === ASSESS_SCHEMA || schema === REPAIR_SCHEMA)
      ? buildDetectionRequest(imageInputs, prompt, model, detail, name, schema)
      : {
          model,
          max_output_tokens: 512,
          input: [{ role: "user", content: [
            { type: "input_image", image_url: Array.isArray(imageInputs) ? imageInputs[0] : imageInputs },
            { type: "input_text", text: prompt },
          ] }],
          text: fmt(name, schema),
        };
    if (reasoningEffort) body.reasoning = { effort: reasoningEffort };
    if ((!onEarly && !stopWhenRejected) || streamBroken) return oai(body);
    try {
      return await oaiStream(body, onEarly, stopWhenRejected);
    } catch (e) {
      // A bad key or a rate limit fails identically unstreamed, so surface those.
      if (e && e.fatal) throw e;
      // A timeout says nothing about whether the server can stream, it says the network
      // stalled. Retrying it unstreamed stalls again, so a single stalled frame cost two
      // full timeouts, and latching streamBroken made every later frame pay for streaming
      // it would no longer use. Surface it and leave streaming alone.
      if (e && e.incompleteStream) throw e;
      if (e && (e.timeout || e.name === "AbortError")) {
        // The abort can surface from the body reader rather than from fetch, where it
        // arrives as a bare "Aborted". Nobody watching a demo should be shown that.
        if (e.timeout) throw e;
        const to = new Error("The network did not respond. Check the connection and try again.");
        to.timeout = true;
        throw to;
      }
      // Anything else (a server that refuses stream:true, a transport that cannot
      // stream, a parse failure) must not cost us the verdict. Remember it, so the
      // wasted round trip is paid once per launch and not on every photo.
      streamBroken = true;
      return oai(body);
    }
  }

  // One warm TLS connection ahead of the first real call. Costs no tokens.
  let warmedAt = 0;
  async function prewarm() {
    await CredentialBroker.ready();
    if (!CredentialBroker.hasOpenAi() || Date.now() - warmedAt < 60000) return;
    warmedAt = Date.now();
    await CredentialBroker.prewarm();
  }

  // ---------- location ----------
  // The address is built from the parts that actually locate the pothole (street,
  // locality, city, postcode). The full display_name is kept separately because it reads
  // like machine output but is useful for debugging.
  const NOMINATIM_REVERSE_ENDPOINT = "https://nominatim.openstreetmap.org/reverse";
  const reverseGeocodeCache = new Map();
  let nominatimSlot = Promise.resolve(), lastNominatimRequestAt = 0;

  async function waitForNominatimSlot() {
    const turn = nominatimSlot.then(async () => {
      const remaining = 1100 - (Date.now() - lastNominatimRequestAt);
      if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, remaining));
      lastNominatimRequestAt = Date.now();
    });
    nominatimSlot = turn.catch(() => {});
    await turn;
  }

  async function reverseGeocodeUncached(lat, lng) {
    try {
      // Public Nominatim is deliberately serialized to below one request per second.
      // Production-scale deployments should change the endpoint to a compliant managed
      // or self-hosted instance; nothing else in the app depends on this response.
      await waitForNominatimSlot();
      const res = await fetchWithTimeout(
        `${NOMINATIM_REVERSE_ENDPOINT}?lat=${lat}&lon=${lng}&format=jsonv2&zoom=17&addressdetails=1&accept-language=${LANG() === "uz" ? "uz,ru,en" : "en"}`,
        {}, 12000);
      if (!res.ok) return null;
      const d = await readJson(res);
      const a = d.address || {};
      const parts = [
        a.road || a.pedestrian || a.residential || a.footway,
        a.neighbourhood || a.hamlet,
        a.suburb || a.village,
        a.city || a.town || a.municipality,
        a.postcode,
      ].filter((x, i, all) => x && all.indexOf(x) === i);
      return {
        short: parts.join(", ") || d.display_name || null,
        full: d.display_name || null,
        // Keep jurisdiction-bearing fields separate. Collapsing these used to make it
        // impossible to tell whether "Pune" came from a city, a municipality or merely
        // the nearest town, which is unsafe when adjacent civic bodies share a district.
        city: a.city || null,
        town: a.town || null,
        municipality: a.municipality || null,
        city_district: a.city_district || null,
        county: a.county || null,
        village: a.village || null,
        suburb: a.suburb || null,
        neighbourhood: a.neighbourhood || null,
        postcode: a.postcode || null,
        state_district: a.state_district || null,
        state: a.state || null,
        country_code: a.country_code || null,
      };
    } catch (e) { return null; }
  }

  function reverseGeocode(lat, lng) {
    // About an 11 m grid at this latitude: adjacent captures reuse the same address and
    // a burst of manual reports cannot hammer the shared public endpoint.
    const key = `${Number(lat).toFixed(4)},${Number(lng).toFixed(4)}`;
    if (reverseGeocodeCache.has(key)) return reverseGeocodeCache.get(key);
    const request = reverseGeocodeUncached(lat, lng);
    reverseGeocodeCache.set(key, request);
    request.then((result) => { if (!result) reverseGeocodeCache.delete(key); },
      () => reverseGeocodeCache.delete(key));
    if (reverseGeocodeCache.size > 250) {
      reverseGeocodeCache.delete(reverseGeocodeCache.keys().next().value);
    }
    return request;
  }

  function distMeters(lat1, lng1, lat2, lng2) {
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad, dLng = (lng2 - lng1) * rad;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2;
    return 2 * 6371000 * Math.asin(Math.sqrt(a));
  }

  const finiteCoord = (v) => typeof v === "number" && Number.isFinite(v);
  const conditionStatus = (r) => r && (r.condition_status === "fixed"
    || r.condition_status === "repair_review") ? r.condition_status : "open";
  const acceptedReport = (r) => !!r && conditionStatus(r) !== "fixed"
    && (r.decision === "accept" || ACCEPTED_REPORT_STATUSES.has(r.status));
  // The app reports one thing: potholes. Older rows without a type are the same thing.
  const isRoadDamageType = (value) => !value || value === "road_damage";
  const storedDamageType = (r) => r && (r.damage_type || (r.is_pothole ? "pothole_cavity" : null));
  const localDamageFamily = new Set(["pothole_cavity", "failed_patch"]);
  const compatibleDamage = (a, b) => {
    const left = storedDamageType(a), right = storedDamageType(b);
    return !!left && (left === right || (localDamageFamily.has(left) && localDamageFamily.has(right)));
  };
  const sizeConflict = (a, b) => !!a.size && !!b.size
    && ((a.size === "small" && b.size === "large") || (a.size === "large" && b.size === "small"));
  const eventTime = (r) => Number.isFinite(r.last_seen_at) ? r.last_seen_at
    : Number.isFinite(r.captured_at) ? r.captured_at : r.created_at;
  const headingDifference = (a, b) => {
    const d = Math.abs(a - b) % 360;
    return Math.min(d, 360 - d);
  };
  const eventSighting = (r) => ({
    drive_id: r.drive_id == null ? null : String(r.drive_id),
    lat: finiteCoord(r.lat) ? r.lat : null,
    lng: finiteCoord(r.lng) ? r.lng : null,
    source_offset_s: Number.isFinite(r.source_offset_s) ? r.source_offset_s : null,
    captured_at: Number.isFinite(r.captured_at) ? r.captured_at : null,
    gps_accuracy: Number.isFinite(r.gps_accuracy) ? r.gps_accuracy : null,
    speed_mps: Number.isFinite(r.speed_mps) ? r.speed_mps : null,
    heading: Number.isFinite(r.heading) ? r.heading : null,
    source_event_key: r.source_event_key || null,
  });
  const storedSightings = (r) => Array.isArray(r.event_sightings) && r.event_sightings.length
    ? r.event_sightings.map((seen) => ({ ...seen,
        drive_id: seen.drive_id == null && r.drive_id != null ? String(r.drive_id) : seen.drive_id }))
    : [eventSighting(r)];

  function matchesEverySameDriveSighting(candidate, sightings) {
    // A normal 4-second cluster contains only a handful of samples. If corrupted or
    // imported data exceeds this bound, save a separate event instead of dropping one.
    if (sightings.length > 64) return false;
    return sightings.every((seen) => {
      const delta = (a, b) => Number.isFinite(a) && Number.isFinite(b) ? Math.abs(a - b) : Infinity;
      const seconds = Math.min(delta(candidate.source_offset_s, seen.source_offset_s),
                               delta(candidate.captured_at, seen.captured_at));
      if (!Number.isFinite(seconds)) return false;
      const positioned = finiteCoord(candidate.lat) && finiteCoord(candidate.lng)
        && finiteCoord(seen.lat) && finiteCoord(seen.lng);
      const accuracyPoor = !Number.isFinite(candidate.gps_accuracy) || !Number.isFinite(seen.gps_accuracy)
        || candidate.gps_accuracy > 30 || seen.gps_accuracy > 30;
      if (!positioned || accuracyPoor) return seconds <= DEDUPE_POOR_GPS_S;
      const distance = distMeters(candidate.lat, candidate.lng, seen.lat, seen.lng);
      const stationary = Number.isFinite(candidate.speed_mps) && Number.isFinite(seen.speed_mps)
        && candidate.speed_mps <= 1 && seen.speed_mps <= 1;
      return stationary
        ? seconds <= 30 && distance <= 5
        : seconds <= DEDUPE_SAME_DRIVE_S && distance <= DEDUPE_ADJACENT_RADIUS_M;
    });
  }

  // A GPS match works across drives and app restarts. The time match is deliberately
  // limited to one drive: it recovers recorded footage with no GPS, but cannot merge two
  // unrelated manual reports merely because they were processed at the same time.
  function roadEventMatch(candidate, prior) {
    if (!candidate.dedupe_eligible || !acceptedReport(prior)
        || prior.debug_capture || prior.dedupe_eligible === false) return null;
    // A fresh routable complaint is more useful than an old accepted observation that
    // could not name an authority. Never hide the sendable one behind the unrouted one.
    if (candidate.status === "draft" && prior.status === "unrouted") return null;
    const keys = Array.isArray(prior.source_event_keys) ? prior.source_event_keys : [];
    if (candidate.source_event_key
        && (prior.source_event_key === candidate.source_event_key || keys.includes(candidate.source_event_key))) {
      return { kind: "same_source" };
    }
    // A manual photo is an explicit user action. Do not silently swallow it based on
    // approximate phone GPS; automatic Drive/VOD observations are the duplicate source.
    if (isManualCaptureSource(candidate.capture_source)) return null;
    if (!compatibleDamage(candidate, prior) || sizeConflict(candidate, prior)) return null;
    const positioned = finiteCoord(candidate.lat) && finiteCoord(candidate.lng)
      && finiteCoord(prior.lat) && finiteCoord(prior.lng);
    const distance = positioned
      ? distMeters(candidate.lat, candidate.lng, prior.lat, prior.lng) : Infinity;
    const candidateDrive = candidate.drive_id == null ? null : String(candidate.drive_id);
    const sameDriveSightings = candidateDrive == null ? []
      : storedSightings(prior).filter((seen) => seen.drive_id != null
          && String(seen.drive_id) === candidateDrive);
    if (sameDriveSightings.length) return matchesEverySameDriveSighting(candidate, sameDriveSightings)
      ? { kind: "same_drive" } : null;

    // A repeat on another drive is less certain: require recent, precise GPS, compatible
    // scale and subtype, and travel direction when the phone supplied it. Missing heading
    // is allowed only at a tighter radius so existing v1.12 reports still protect users.
    if (!positioned || !Number.isFinite(candidate.gps_accuracy) || !Number.isFinite(prior.gps_accuracy)
        || candidate.gps_accuracy > 15 || prior.gps_accuracy > 15) return null;
    const age = Math.abs((eventTime(candidate) || 0) - (eventTime(prior) || 0));
    if (!Number.isFinite(age) || age > DEDUPE_HISTORY_S) return null;
    const left = storedDamageType(candidate), right = storedDamageType(prior);
    if (left === "other_road_damage" || right === "other_road_damage") return null;
    let radius = left === right ? DEDUPE_HISTORY_RADIUS_M : 5;
    const moving = Number.isFinite(candidate.speed_mps) && Number.isFinite(prior.speed_mps)
      && candidate.speed_mps >= 2 && prior.speed_mps >= 2;
    const headingsKnown = Number.isFinite(candidate.heading) && Number.isFinite(prior.heading);
    if (moving && headingsKnown) {
      if (headingDifference(candidate.heading, prior.heading) > 45) return null;
    } else {
      radius = Math.min(radius, DEDUPE_MISSING_HEADING_RADIUS_M);
    }
    return distance <= radius ? { kind: "prior_drive" } : null;
  }

  const sameRoadEvent = (candidate, prior) => !!roadEventMatch(candidate, prior);

  function repairTargetMatch(observation, prior) {
    if (!observation || observation.capture_source !== "drive_live" || observation.debug_capture
        || !prior || !isRoadDamageType(prior.issue_type)
        || !acceptedReport(prior) || prior.debug_capture || prior.dedupe_eligible === false
        || !prior.photo || !finiteCoord(observation.lat) || !finiteCoord(observation.lng)
        || !finiteCoord(prior.lat) || !finiteCoord(prior.lng)
        || !Number.isFinite(observation.gps_accuracy) || observation.gps_accuracy < 0
        || observation.gps_accuracy > REPAIR_MAX_ACCURACY_M
        || !Number.isFinite(prior.gps_accuracy) || prior.gps_accuracy < 0
        || prior.gps_accuracy > REPAIR_MAX_ACCURACY_M) return null;
    // A repair is a later physical observation, never a reinterpretation of the
    // original frame. Missing clocks and equal/older timestamps therefore fail closed.
    const observedAt = observation.observed_at;
    const damageObservedAt = eventTime(prior);
    if (!Number.isFinite(observedAt) || !Number.isFinite(damageObservedAt)
        || observedAt <= damageObservedAt) return null;
    const driveId = observation.drive_id == null ? null : String(observation.drive_id);
    if (!driveId) return null;
    const priorDrives = new Set(Array.isArray(prior.sighting_drive_ids)
      ? prior.sighting_drive_ids.map(String) : []);
    if ((prior.drive_id != null && String(prior.drive_id) === driveId) || priorDrives.has(driveId)) {
      return null;
    }
    const distance = distMeters(observation.lat, observation.lng, prior.lat, prior.lng);
    let radius = REPAIR_RADIUS_M;
    const headingsKnown = Number.isFinite(observation.heading) && Number.isFinite(prior.heading);
    if (headingsKnown) {
      if (headingDifference(observation.heading, prior.heading)
          > REPAIR_MAX_HEADING_DIFFERENCE_DEG) return null;
    } else {
      radius = REPAIR_MISSING_HEADING_RADIUS_M;
    }
    return distance <= radius ? { distance } : null;
  }

  function findRepairCandidateFromReports(observation, reports) {
    const matches = [];
    for (const prior of reports || []) {
      const match = repairTargetMatch(observation, prior);
      if (match) matches.push({ prior, distance: match.distance });
      if (matches.length > 1) return null;
    }
    return matches.length === 1 ? matches[0].prior : null;
  }

  function findDuplicateReport(candidate, reports) {
    for (let i = reports.length - 1; i >= 0; i--) {
      if (sameRoadEvent(candidate, reports[i])) return reports[i];
    }
    return null;
  }

  function damageTypeOf(value) {
    if (value && value.damage_type) return value.damage_type;
    return value && value.is_pothole ? "pothole_cavity" : "none";
  }

  function assessmentOf(value) {
    if (value && value.assessment) return value.assessment;
    if (value && value.is_pothole) return "clear";
    return "absent";
  }

  let _db = null;
  function idb() {
    return new Promise((resolve, reject) => {
      if (_db) return resolve(_db);
      const req = indexedDB.open("potholes", 7);
      req.onupgradeneeded = () => {
        const d = req.result;
        const reports = d.objectStoreNames.contains("reports")
          ? req.transaction.objectStore("reports")
          : d.createObjectStore("reports", { keyPath: "id", autoIncrement: true });
        // Cursor over lightweight candidate ranges instead of getAll(): report records
        // contain photos, so cloning every old image for every accepted frame would make
        // long footage analysis slower and more memory-hungry as history grows.
        if (!reports.indexNames.contains("by_lat")) reports.createIndex("by_lat", "lat");
        if (!reports.indexNames.contains("by_drive")) reports.createIndex("by_drive", "drive_id");
        // A canonical event can be observed on later drives without changing its original
        // drive_id. Index every drive that has seen it so the next adjacent observation is
        // found even when it lies outside the stricter cross-drive radius or has no GPS.
        if (!reports.indexNames.contains("by_sighting_drive")) {
          reports.createIndex("by_sighting_drive", "sighting_drive_ids", { multiEntry: true });
        }
        // How many frames a drive actually checked is only known while it runs:
        // rejected frames are not kept unless debug mode is on, so the count has to
        // be recorded at the end or it is lost.
        if (!d.objectStoreNames.contains("drives")) d.createObjectStore("drives", { keyPath: "id" });
        // Continuous footage: capture stops guessing an interval, and a drive can be
        // re-analysed later, more densely or by a better model. Discarded frames are gone.
        if (!d.objectStoreNames.contains("footage")) {
          const f = d.createObjectStore("footage", { keyPath: "key" });
          f.createIndex("by_drive", "drive_id");
        }
        // Region-routing downloads no longer exist; drop their old cache if present.
        if (d.objectStoreNames.contains("state_packs")) d.deleteObjectStore("state_packs");
      };
      req.onsuccess = () => {
        _db = req.result;
        _db.onversionchange = () => { _db.close(); _db = null; };
        resolve(_db);
      };
      req.onerror = () => reject(req.error);
    });
  }
  // A write is not done when the request succeeds, it is done when the transaction
  // commits. Chrome reports a full disk by aborting the transaction, and the request
  // itself still succeeds, so resolving on req.onsuccess reported success for writes that
  // rolled back: measured, 672 MB of footage reported stored and absent afterwards. A
  // read has nothing to commit, so it still resolves on the request.
  function op(mode, fn, storeName = "reports") {
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction(storeName, mode);
      const req = fn(tx.objectStore(storeName));
      if (mode === "readonly") {
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
        return;
      }
      let value, failure = null;
      req.onsuccess = () => { value = req.result; };
      req.onerror = (e) => { failure = req.error; e.preventDefault(); };
      tx.oncomplete = () => resolve(value);
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = died;
    }));
  }

  const STORED_DATA_STORES = ["reports", "drives", "footage"];

  // Delete-all is one IndexedDB transaction. Sequential clears can leave a misleading
  // half-wiped history when a later store aborts (especially under storage pressure).
  function clearAllStoredRecords() {
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction(STORED_DATA_STORES, "readwrite");
      let failure = null;
      for (const name of STORED_DATA_STORES) {
        const req = tx.objectStore(name).clear();
        req.onerror = () => { failure = req.error; };
      }
      tx.oncomplete = () => resolve();
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = () => {};
    }));
  }

  function allStoredRecordsAreEmpty() {
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction(STORED_DATA_STORES, "readonly");
      let remaining = 0, failure = null;
      for (const name of STORED_DATA_STORES) {
        const req = tx.objectStore(name).count();
        req.onsuccess = () => { remaining += Number(req.result) || 0; };
        req.onerror = () => { failure = req.error; };
      }
      tx.oncomplete = () => failure ? reject(storageError(failure)) : resolve(remaining === 0);
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = () => {};
    }));
  }

  // A full device is the common cause and the only one the user can act on, so it says so
  // rather than surfacing a DOMException name.
  function storageError(err) {
    const name = err && err.name;
    if (name === "QuotaExceededError") {
      return new Error("This phone is out of storage, so nothing more can be saved. Free some space, or delete old drives and their video from the app.");
    }
    return new Error((err && err.message) || "Could not save to this device's storage.");
  }
  const allReports = () => op("readonly", (s) => s.getAll());
  const getReport = (id) => op("readonly", (s) => s.get(Number(id)));
  const putReport = (r) => op("readwrite", (s) => s.put(r));
  const addReport = (r) => op("readwrite", (s) => s.add(r));
  const delReport = (id) => op("readwrite", (s) => s.delete(Number(id)));
  // Raw GPS tracks are personal movement data: keep them 30 days, drop them earlier when the
  // user opts out, and let any single drive's track be deleted on request. Pothole reports
  // keep their own coordinates; only the per-drive track and its trip statistics go.
  // FRESH-001: a saved pothole is fresh for 7 days after it was last seen, aging through
  // day 30 and stale after that. Freshness only describes how recently we saw it; stale
  // potholes are never deleted, and "fixed" still needs separate before/after evidence.
  const FRESH_THROUGH_S = 7 * 86400;
  const STALE_AFTER_S = 30 * 86400;
  function freshnessFor(observedAtS, nowS) {
    if (!Number.isFinite(observedAtS) || observedAtS <= 0 || !Number.isFinite(nowS)
        || observedAtS > nowS + 300) return "unknown";
    const age = nowS - observedAtS;
    return age <= FRESH_THROUGH_S ? "fresh" : age <= STALE_AFTER_S ? "aging" : "stale";
  }
  const TRACK_RETENTION_S = 30 * 86400;
  const keepTracks = () => localStorage.getItem("keep_tracks") !== "0";
  function trackExpired(drive, nowS, keep = true) {
    if (!drive || !Array.isArray(drive.gps_track) || !drive.gps_track.length) return false;
    if (!keep) return true;
    const ended = Number(drive.ended_at || drive.started_at || 0);
    return Number.isFinite(ended) && ended > 0 && nowS - ended > TRACK_RETENTION_S;
  }
  async function pruneExpiredTracks(nowS = Date.now() / 1000) {
    const keep = keepTracks();
    const drives = await op("readonly", (s) => s.getAll(), "drives");
    for (const d of drives) {
      if (trackExpired(d, nowS, keep)) await putDrive({ ...d, gps_track: [], track_deleted_at: nowS });
    }
  }
  const allDrives = async () => {
    await pruneExpiredTracks();
    return op("readonly", (s) => s.getAll(), "drives");
  };
  const getDrive = (id) => op("readonly", (s) => s.get(String(id)), "drives");
  const putFootage = (seg) => op("readwrite", (s) => s.put(seg), "footage");
  const footageFor = (driveId) => op("readonly", (s) => s.index("by_drive").getAll(String(driveId)), "footage");
  const allFootage = () => op("readonly", (s) => s.getAll(), "footage");
  const putDrive = (d) => op("readwrite", (s) => s.put(d), "drives");

  function mutateReportAtomically(id, mutate) {
    const reportId = Number(id);
    if (!Number.isFinite(reportId) || reportId <= 0) {
      return Promise.reject(new Error("Report not found."));
    }
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction("reports", "readwrite");
      const store = tx.objectStore("reports");
      let result = null, failure = null;
      const abortWith = (error) => {
        failure = error instanceof Error ? error : new Error(String(error || "Could not update this report."));
        try { tx.abort(); } catch (_) {}
      };
      const read = store.get(reportId);
      read.onsuccess = () => {
        const current = read.result;
        if (!current) { abortWith(new Error("Report not found.")); return; }
        try { mutate(current); } catch (error) { abortWith(error); return; }
        const write = store.put(current);
        write.onsuccess = () => { result = toDict(current); };
        write.onerror = () => { failure = write.error; };
      };
      read.onerror = () => { failure = read.error; };
      tx.oncomplete = () => resolve(result);
      tx.onabort = () => reject(failure || storageError(tx.error));
      tx.onerror = () => {};
    }));
  }

  // Accepted Drive jobs finish concurrently. A separate getAll() followed by add()
  // lets two nearby jobs both observe "none" and both write. Keep the final check and
  // insert in one read-write transaction; IndexedDB serialises these transactions on the
  // reports store, so exactly one concurrent detection becomes the saved event.
  function addReportUnlessDuplicate(rec, dedupe) {
    if (!dedupe) return addReport(rec).then((id) => ({ id, duplicate: null }));
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction("reports", "readwrite");
      const store = tx.objectStore("reports");
      let result = null, failure = null;
      const addNew = () => {
        const add = store.add(rec);
        add.onsuccess = () => { result = { id: add.result, duplicate: null }; };
        add.onerror = () => { failure = add.error; };
      };
      const scan = (request, next) => {
        request.onsuccess = () => {
          const cursor = request.result;
          if (!cursor) { next(); return; }
          const match = roadEventMatch(rec, cursor.value);
          if (match) {
            const prior = cursor.value;
            const keys = Array.isArray(prior.source_event_keys)
              ? prior.source_event_keys.slice() : (prior.source_event_key ? [prior.source_event_key] : []);
            if (rec.source_event_key && !keys.includes(rec.source_event_key)) keys.push(rec.source_event_key);
            const exactReplay = match.kind === "same_source";
            const observedAt = eventTime(rec);
            // Keep a bounded envelope per drive, not a global 64-item cap: popular
            // locations can be revisited many times, and a full old global array would
            // otherwise stop recording the first sighting of a new drive. Sightings older
            // than the cross-drive horizon are no longer useful for approximate matching;
            // exact retained-footage replays remain covered by source_event_keys.
            const currentDrive = rec.drive_id == null ? null : String(rec.drive_id);
            const cutoff = Number.isFinite(observedAt) ? observedAt - DEDUPE_HISTORY_S : -Infinity;
            const sightings = storedSightings(prior).filter((seen) => {
              const seenAt = Number.isFinite(seen.captured_at) ? seen.captured_at : null;
              return (seen.drive_id != null && String(seen.drive_id) === currentDrive)
                || seenAt == null || seenAt >= cutoff;
            });
            const sameDriveCount = currentDrive == null ? 0 : sightings.filter((seen) =>
              seen.drive_id != null && String(seen.drive_id) === currentDrive).length;
            if ((match.kind === "same_drive" || match.kind === "prior_drive")
                && !exactReplay && (currentDrive == null || sameDriveCount < 64)) {
              sightings.push(eventSighting(rec));
            }
            const sightingDriveIds = [...new Set(sightings
              .map((seen) => seen.drive_id == null ? null : String(seen.drive_id)).filter(Boolean))];
            const updated = {
              ...prior,
              source_event_keys: keys.slice(-64),
              event_sightings: sightings,
              sighting_drive_ids: sightingDriveIds,
              seen_count: exactReplay ? (prior.seen_count || 1) : (prior.seen_count || 1) + 1,
              last_seen_at: Math.max(eventTime(prior) || 0, eventTime(rec) || 0),
              // A fresh accepted detection is direct evidence that the defect remains.
              // It can clear an AI-suggested repair review, but a previously fixed
              // canonical is excluded by acceptedReport and therefore becomes a new
              // recurrence rather than silently rewriting history.
              condition_status: conditionStatus(prior) === "repair_review" ? "open"
                : conditionStatus(prior),
              condition_updated_at: conditionStatus(prior) === "repair_review"
                ? (eventTime(rec) || Date.now() / 1000) : (prior.condition_updated_at || null),
              condition_source: conditionStatus(prior) === "repair_review"
                ? "damage_seen_on_revisit" : (prior.condition_source || null),
            };
            const write = cursor.update(updated);
            write.onsuccess = () => { result = { id: null, duplicate: updated, match: match.kind }; };
            write.onerror = () => { failure = write.error; };
            return;
          }
          cursor.continue();
        };
        request.onerror = () => { failure = request.error; };
      };
      const scanLocation = () => {
        if (!finiteCoord(rec.lat) || !finiteCoord(rec.lng)) { addNew(); return; }
        const latitudeBand = DEDUPE_HISTORY_RADIUS_M / 110900;
        scan(store.index("by_lat").openCursor(
          IDBKeyRange.bound(rec.lat - latitudeBand, rec.lat + latitudeBand)), addNew);
      };
      try {
        if (rec.drive_id != null) {
          const driveKey = String(rec.drive_id);
          const scanOriginalDrive = () => scan(
            store.index("by_drive").openCursor(IDBKeyRange.only(driveKey)), scanLocation);
          scan(store.index("by_sighting_drive").openCursor(IDBKeyRange.only(driveKey)), scanOriginalDrive);
        } else scanLocation();
      } catch (e) {
        failure = e;
        try { tx.abort(); } catch (_) {}
      }
      tx.oncomplete = () => result ? resolve(result)
        : reject(storageError(failure || new Error("Could not save this report.")));
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = () => {};
    }));
  }

  // SEC-010: bound encoded bytes and inspect raster headers before any pixel decode.
  const IMAGE_DECODE_POLICY = Object.freeze({
    maxEncodedBytes: 32 * 1024 * 1024,
    maxDimension: 12000,
    maxPixels: 64_000_000,
    maxPreparedDimension: 4000,
    maxHeaderBytes: 1024 * 1024,
    maxExifBytes: 64 * 1024,
    maxChunks: 4096,
  });
  function imageDecodeError() {
    return new Error("Photo is malformed or exceeds the supported image limits (32 MiB, 12000 pixels per side, 64 megapixels). Use JPEG, PNG, WebP, GIF or BMP.");
  }
  function checkPhotoEncodedSize(value) {
    if (value instanceof Blob && value.size > IMAGE_DECODE_POLICY.maxEncodedBytes) throw imageDecodeError();
    if (typeof value !== "string" || !/^data:image\//i.test(value)) return;
    const comma = value.indexOf(",");
    if (comma < 0 || comma > 64) throw imageDecodeError();
    const encodedLength = value.length - comma - 1;
    const base64 = /;base64$/i.test(value.slice(0, comma));
    const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
    const byteLimit = base64 ? Math.floor(encodedLength / 4) * 3 - padding : encodedLength;
    if (byteLimit > IMAGE_DECODE_POLICY.maxEncodedBytes) throw imageDecodeError();
  }
  function checkedImageDimensions(width, height, maxDimension = IMAGE_DECODE_POLICY.maxDimension,
      maxPixels = IMAGE_DECODE_POLICY.maxPixels) {
    if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height)
        || width < 1 || height < 1 || width > maxDimension || height > maxDimension
        || width > Math.floor(maxPixels / height)) throw imageDecodeError();
    return { width, height };
  }
  function imageExifOrientation(bytes) {
    let start = 0;
    if (bytes[0] === 0x45 && bytes[1] === 0x78 && bytes[2] === 0x69 && bytes[3] === 0x66) {
      if (bytes[4] !== 0 || bytes[5] !== 0) throw imageDecodeError();
      start = 6;
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const little = bytes[start] === 0x49 && bytes[start + 1] === 0x49;
    if (!little && !(bytes[start] === 0x4d && bytes[start + 1] === 0x4d)) throw imageDecodeError();
    const u16 = offset => { if (offset < start || offset + 2 > bytes.length) throw imageDecodeError(); return view.getUint16(offset, little); };
    const u32 = offset => { if (offset < start || offset + 4 > bytes.length) throw imageDecodeError(); return view.getUint32(offset, little); };
    if (u16(start + 2) !== 42) throw imageDecodeError();
    const ifd = start + u32(start + 4);
    const count = u16(ifd);
    if (count > IMAGE_DECODE_POLICY.maxChunks || ifd + 2 + count * 12 + 4 > bytes.length) throw imageDecodeError();
    for (let i = 0; i < count; i++) {
      const entry = ifd + 2 + i * 12;
      if (u16(entry) !== 0x112) continue;
      if (u16(entry + 2) !== 3 || u32(entry + 4) !== 1) throw imageDecodeError();
      const orientation = u16(entry + 8);
      if (orientation < 1 || orientation > 8) throw imageDecodeError();
      return orientation;
    }
    return 1;
  }
  function inspectImageHeader(bytes, totalBytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const text = (start, length) => String.fromCharCode(...bytes.subarray(start, start + length));
    let width, height, type, orientation = 1;
    if (bytes.length >= 33 && text(0, 8) === "\x89PNG\r\n\x1a\n") {
      if (view.getUint32(8) !== 13 || text(12, 4) !== "IHDR") throw imageDecodeError();
      width = view.getUint32(16); height = view.getUint32(20); type = "image/png";
    } else if (bytes.length >= 30 && text(0, 4) === "RIFF" && text(8, 4) === "WEBP") {
      if (view.getUint32(4, true) + 8 !== totalBytes) throw imageDecodeError();
      const tag = text(12, 4);
      const u24 = p => bytes[p] + bytes[p + 1] * 256 + bytes[p + 2] * 65536;
      if (tag === "VP8X" && view.getUint32(16, true) === 10) {
        width = u24(24) + 1; height = u24(27) + 1;
      } else if (tag === "VP8 " && bytes[23] === 0x9d && bytes[24] === 1 && bytes[25] === 0x2a) {
        width = view.getUint16(26, true) & 0x3fff; height = view.getUint16(28, true) & 0x3fff;
      } else if (tag === "VP8L" && bytes[20] === 0x2f) {
        const bits = view.getUint32(21, true);
        width = (bits & 0x3fff) + 1; height = ((bits >>> 14) & 0x3fff) + 1;
      } else throw imageDecodeError();
      type = "image/webp";
    } else if (bytes.length >= 13 && ["GIF87a", "GIF89a"].includes(text(0, 6))) {
      width = view.getUint16(6, true); height = view.getUint16(8, true); type = "image/gif";
      let p = 13 + (bytes[10] & 0x80 ? 3 * 2 ** ((bytes[10] & 7) + 1) : 0);
      let found = false;
      for (let count = 0; count < IMAGE_DECODE_POLICY.maxChunks && p < bytes.length; count++) {
        if (bytes[p] === 0x2c) {
          if (p + 10 > bytes.length) throw imageDecodeError();
          const left = view.getUint16(p + 1, true), top = view.getUint16(p + 3, true);
          const frameW = view.getUint16(p + 5, true), frameH = view.getUint16(p + 7, true);
          checkedImageDimensions(frameW, frameH);
          if (left + frameW > width || top + frameH > height) throw imageDecodeError();
          found = true; break;
        }
        if (bytes[p] !== 0x21 || p + 2 >= bytes.length) throw imageDecodeError();
        p += 2;
        let blocks = 0;
        while (p < bytes.length && bytes[p]) {
          if (++blocks > IMAGE_DECODE_POLICY.maxChunks) throw imageDecodeError();
          p += 1 + bytes[p];
        }
        if (p >= bytes.length) throw imageDecodeError();
        p++;
      }
      if (!found) throw imageDecodeError();
    } else if (bytes.length >= 54 && text(0, 2) === "BM") {
      if (view.getUint32(2, true) !== totalBytes || view.getUint32(14, true) < 40
          || view.getUint32(10, true) >= totalBytes) throw imageDecodeError();
      width = view.getInt32(18, true); height = Math.abs(view.getInt32(22, true)); type = "image/bmp";
    } else if (bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
      let p = 2, scanned = 0, foundScan = false;
      while (p < bytes.length && ++scanned <= IMAGE_DECODE_POLICY.maxChunks) {
        if (bytes[p++] !== 0xff) throw imageDecodeError();
        while (p < bytes.length && bytes[p] === 0xff) p++;
        const marker = bytes[p++];
        if (marker === 0xda) { foundScan = true; break; }
        if (marker === 0xd9 || marker === undefined) throw imageDecodeError();
        if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
        if (p + 2 > bytes.length) throw imageDecodeError();
        const length = view.getUint16(p);
        if (length < 2 || p + length > bytes.length) throw imageDecodeError();
        if (marker === 0xe1 && text(p + 2, 6) === "Exif\0\0") {
          orientation = imageExifOrientation(bytes.subarray(p + 2, p + length));
        }
        if ([0xc0, 0xc1, 0xc2].includes(marker)) {
          if (length < 8 || width !== undefined) throw imageDecodeError();
          height = view.getUint16(p + 3); width = view.getUint16(p + 5);
        }
        p += length;
      }
      if (!foundScan || width === undefined) throw imageDecodeError();
      type = "image/jpeg";
    } else throw imageDecodeError();
    checkedImageDimensions(width, height);
    return { width, height, type, orientation };
  }
  async function readImageBounds(blob) {
    if (!(blob instanceof Blob) || !Number.isSafeInteger(blob.size) || blob.size < 12
        || blob.size > IMAGE_DECODE_POLICY.maxEncodedBytes) throw imageDecodeError();
    const header = new Uint8Array(await blob.slice(0, IMAGE_DECODE_POLICY.maxHeaderBytes).arrayBuffer());
    const bounds = inspectImageHeader(header, blob.size);
    const tail = new Uint8Array(await blob.slice(-12).arrayBuffer());
    if ((bounds.type === "image/jpeg" && !(tail[tail.length - 2] === 0xff && tail[tail.length - 1] === 0xd9))
        || (bounds.type === "image/gif" && tail[tail.length - 1] !== 0x3b)) throw imageDecodeError();
    if (bounds.type === "image/png" || bounds.type === "image/webp") {
      const png = bounds.type === "image/png";
      let p = png ? 8 : 12, chunks = 0, foundExif = false, ended = false;
      while (p < blob.size) {
        if (++chunks > IMAGE_DECODE_POLICY.maxChunks || p + 8 > blob.size) throw imageDecodeError();
        const bytes = p + 8 <= header.length ? header.subarray(p, p + 8)
          : new Uint8Array(await blob.slice(p, p + 8).arrayBuffer());
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        const length = view.getUint32(png ? 0 : 4, !png);
        const tag = String.fromCharCode(...bytes.subarray(png ? 4 : 0, png ? 8 : 4));
        const next = p + 8 + length + (png ? 4 : length % 2);
        if (next > blob.size || next <= p) throw imageDecodeError();
        if (tag === (png ? "eXIf" : "EXIF")) {
          if (foundExif || length > IMAGE_DECODE_POLICY.maxExifBytes) throw imageDecodeError();
          const exif = p + 8 + length <= header.length ? header.subarray(p + 8, p + 8 + length)
            : new Uint8Array(await blob.slice(p + 8, p + 8 + length).arrayBuffer());
          bounds.orientation = imageExifOrientation(exif); foundExif = true;
        }
        if (png && tag === "IEND") {
          if (length !== 0 || next !== blob.size) throw imageDecodeError();
          ended = true;
        }
        p = next;
      }
      if (png && !ended) throw imageDecodeError();
    }
    if (bounds.orientation >= 5) [bounds.width, bounds.height] = [bounds.height, bounds.width];
    return bounds;
  }
  async function decodeBoundedImage(blob, maxDim) {
    if (!Number.isSafeInteger(maxDim) || maxDim < 1
        || maxDim > IMAGE_DECODE_POLICY.maxPreparedDimension) throw imageDecodeError();
    const bounds = await readImageBounds(blob);
    const scale = Math.min(1, maxDim / Math.max(bounds.width, bounds.height));
    const width = Math.max(1, Math.round(bounds.width * scale));
    const height = Math.max(1, Math.round(bounds.height * scale));
    let bitmap = null;
    try {
      bitmap = await createImageBitmap(blob, { imageOrientation: "from-image",
        resizeWidth: width, resizeHeight: height, resizeQuality: "high" });
      checkedImageDimensions(bitmap.width, bitmap.height, maxDim, maxDim * maxDim);
      if (bitmap.width !== width || bitmap.height !== height) throw imageDecodeError();
      return bitmap;
    } catch (error) {
      if (bitmap && bitmap.close) bitmap.close();
      throw imageDecodeError();
    }
  }
  let imagePreparationTail = Promise.resolve();
  function reserveImagePreparation() {
    const ready = imagePreparationTail;
    let done;
    imagePreparationTail = new Promise(resolve => { done = resolve; });
    return { ready, done };
  }
  let manualPhotoPreparing = false;
  function installManualPhotoBudget() {
    // Keep the SEC-009 hash-approved inline UI unchanged: guard its global entry
    // after it has been declared, before user capture/import events can run.
    const original = window.handleFile;
    if (typeof original !== "function") return;
    window.handleFile = async function boundedManualPhoto(file, captureMeta = {}) {
      if (!file) return;
      if (manualPhotoPreparing) { alert("A photo is already being prepared. Please wait."); return; }
      manualPhotoPreparing = true;
      let preview = null;
      try {
        const normalized = await toDataUrl(file, IMAGE_DECODE_POLICY.maxPreparedDimension, 0.92, false, true);
        const prepared = new File([normalized], file.name || "photo.jpg", {
          type: "image/jpeg", lastModified: file.lastModified,
        });
        return await original(prepared, captureMeta);
      } catch (error) {
        alert(error.message || imageDecodeError().message);
      } finally {
        // The original sets the preview only after its consent and confirmation prompts,
        // so look for it now rather than right after starting it.
        const shown = document.getElementById("progressPhoto");
        if (shown && shown.src.startsWith("blob:")) preview = shown.src;
        if (preview) {
          const photo = document.getElementById("progressPhoto");
          if (photo && photo.src === preview) photo.removeAttribute("src");
          URL.revokeObjectURL(preview);
        }
        manualPhotoPreparing = false;
      }
    };
  }
  document.addEventListener("DOMContentLoaded", installManualPhotoBudget, { once: true });
  // Photos are stored as blobs, not base64. Measured on a device with a hundred 1024px
  // thumbnails: reading them back took 177 ms as base64 strings and 3 ms as blobs, writing
  // took 253 ms against 90 ms, and each one is 88 KB as text against 66 KB binary. Every
  // screen that lists reports paid that difference, which is why the app felt slow
  // everywhere rather than in one place.
  //
  // Records written before this change hold a data URL string. Everything that reads a
  // photo accepts either, so nothing has to be migrated or rewritten.
  const dataUrlToBlob = async (u) => {
    if (!u || typeof u !== "string") return u || null;
    checkPhotoEncodedSize(u);
    try { return await (await fetch(u)).blob(); } catch (e) { return u; }
  };
  const blobToDataUrl = async (v) => {
    if (!v) return null;
    checkPhotoEncodedSize(v);
    if (typeof v === "string") return v;
    return await new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result));
      fr.onerror = () => reject(fr.error || new Error("Could not read saved repair evidence."));
      fr.readAsDataURL(v);
    });
  };

  const repairProvenanceIsExact = (observation) => {
    if (!observation || typeof observation !== "object") return false;
    const model = observation.detection_model;
    const detail = observation.image_detail;
    return typeof model === "string" && model.length > 0 && ALLOWED_MODELS.has(model)
      && typeof detail === "string" && detail.length > 0 && ALLOWED_DETAILS.has(detail)
      && normaliseDetail(detail, model) === detail
      && typeof observation.description === "string"
      && observation.description.trim().length > 0
      && observation.prompt_version === REPAIR_PROMPT_VERSION
      && Number.isInteger(observation.schema_version)
      && observation.schema_version === REPAIR_SCHEMA_VERSION;
  };

  // Repair evidence changes a saved physical fact, so it has a stricter contract than
  // legacy report photos: it must be a real, decodable, bounded image Blob. Never retain
  // an arbitrary string merely because fetch() could not decode it.
  async function decodeRepairEvidence(value) {
    let blob = null;
    if (typeof Blob !== "undefined" && value instanceof Blob) {
      blob = value;
    } else if (typeof value === "string"
        && /^data:image\/(?:jpeg|png|webp);base64,/i.test(value)) {
      if (value.length > Math.ceil(REPAIR_EVIDENCE_MAX_BYTES / 3) * 4 + 64) return null;
      try {
        const response = await fetch(value);
        if (!response.ok) return null;
        blob = await response.blob();
      } catch (_) { return null; }
    }
    const type = String(blob && blob.type || "").toLowerCase();
    if (!blob || blob.size < REPAIR_EVIDENCE_MIN_BYTES || blob.size > REPAIR_EVIDENCE_MAX_BYTES
        || !REPAIR_EVIDENCE_TYPES.has(type)) return null;
    let header;
    try { header = new Uint8Array(await blob.slice(0, 12).arrayBuffer()); }
    catch (_) { return null; }
    const jpeg = header[0] === 0xff && header[1] === 0xd8 && header[2] === 0xff;
    const png = header[0] === 0x89 && header[1] === 0x50 && header[2] === 0x4e
      && header[3] === 0x47 && header[4] === 0x0d && header[5] === 0x0a
      && header[6] === 0x1a && header[7] === 0x0a;
    const webp = header[0] === 0x52 && header[1] === 0x49 && header[2] === 0x46
      && header[3] === 0x46 && header[8] === 0x57 && header[9] === 0x45
      && header[10] === 0x42 && header[11] === 0x50;
    if ((type === "image/jpeg" && !jpeg) || (type === "image/png" && !png)
        || (type === "image/webp" && !webp)) return null;
    let width = 0, height = 0, bitmap = null;
    const turn = reserveImagePreparation();
    await turn.ready;
    try {
      const bounds = await readImageBounds(blob);
      checkedImageDimensions(bounds.width, bounds.height, REPAIR_EVIDENCE_MAX_DIMENSION, REPAIR_EVIDENCE_MAX_PIXELS);
      if (bounds.width < REPAIR_EVIDENCE_MIN_DIMENSION || bounds.height < REPAIR_EVIDENCE_MIN_DIMENSION) return null;
      bitmap = await decodeBoundedImage(blob, IMAGE_DECODE_POLICY.maxPreparedDimension);
      width = bounds.width; height = bounds.height;
    } catch (_) { return null; }
    finally { try { if (bitmap && bitmap.close) bitmap.close(); } finally { turn.done(); } }
    if (!Number.isInteger(width) || !Number.isInteger(height)
        || width < REPAIR_EVIDENCE_MIN_DIMENSION || height < REPAIR_EVIDENCE_MIN_DIMENSION
        || width > REPAIR_EVIDENCE_MAX_DIMENSION || height > REPAIR_EVIDENCE_MAX_DIMENSION
        || width * height > REPAIR_EVIDENCE_MAX_PIXELS) return null;
    return blob;
  }
  const photoToBase64 = async (v) => {
    if (!v) return null;
    checkPhotoEncodedSize(v);
    if (typeof v === "string") return v.split(",")[1];
    return await new Promise((res) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result).split(",")[1]);
      fr.onerror = () => res(null);
      fr.readAsDataURL(v);
    });
  };

  const toDict = (r) => ({ ...r, photo_url: r.photo, repair_photo_url: r.repair_photo || null });
  // The list never renders the evidence copy, so it never receives it.
  const listDict = (r) => { const d = toDict(r); delete d.photo_full; return d; };

  async function findRepairCandidate(observation) {
    if (!observation || !finiteCoord(observation.lat) || !finiteCoord(observation.lng)) return null;
    const latitudeBand = REPAIR_RADIUS_M / 110900;
    const nearby = await op("readonly", (store) => store.index("by_lat").getAll(
      IDBKeyRange.bound(observation.lat - latitudeBand, observation.lat + latitudeBand)));
    return findRepairCandidateFromReports(observation, nearby);
  }

  // Commit the before/after result and its evidence in one transaction. A native retry
  // after the WebView closes is harmless because source_event_key is idempotent.
  async function applyRepairObservation(targetId, observation) {
    const id = Number(targetId);
    const sourceEventKey = String(observation && observation.source_event_key || "").slice(0, 180);
    const nextCondition = repairConditionFor(observation);
    if (!Number.isFinite(id) || id <= 0 || !sourceEventKey || !nextCondition) {
      return { ignored: true, reason: "repair_not_proven" };
    }
    if (!repairProvenanceIsExact(observation)) {
      return { ignored: true, reason: "repair_provenance_invalid" };
    }
    const repairPhoto = await decodeRepairEvidence(observation.current_photo_data_url);
    if (!repairPhoto) return { ignored: true, reason: "repair_evidence_invalid" };
    const candidate = {
      ...observation,
      capture_source: "drive_live",
      debug_capture: false,
      drive_id: observation.drive_id == null ? null : String(observation.drive_id),
    };
    if (!finiteCoord(candidate.lat) || !finiteCoord(candidate.lng)) {
      return { ignored: true, reason: "target_ambiguous_or_mismatched" };
    }
    // The uniqueness scan and update deliberately share one read-write transaction.
    // IndexedDB serialises competing writers on this store, so no nearby report can be
    // inserted or changed between the ambiguity decision and the physical-status write.
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction("reports", "readwrite");
      const store = tx.objectStore("reports");
      let result = null, failure = null;
      const matches = [];
      const replays = [];
      const latitudeBand = REPAIR_RADIUS_M / 110900;
      const scan = store.index("by_lat").openCursor(IDBKeyRange.bound(
        candidate.lat - latitudeBand, candidate.lat + latitudeBand));
      scan.onsuccess = () => {
        const cursor = scan.result;
        if (cursor) {
          const priorKeys = Array.isArray(cursor.value.repair_source_event_keys)
            ? cursor.value.repair_source_event_keys : [];
          if (priorKeys.includes(sourceEventKey)) replays.push(cursor.value);
          if (repairTargetMatch(candidate, cursor.value)) matches.push(cursor.value);
          cursor.continue();
          return;
        }
        if (replays.length) {
          if (replays.length === 1 && Number(replays[0].id) === id) {
            result = { id, duplicate: true, condition_status: conditionStatus(replays[0]) };
          } else {
            result = { ignored: true, reason: "target_ambiguous_or_mismatched" };
          }
          return;
        }
        if (matches.length !== 1 || Number(matches[0].id) !== id) {
          result = { ignored: true, reason: "target_ambiguous_or_mismatched" };
          return;
        }
        const prior = matches[0];
        const keys = Array.isArray(prior.repair_source_event_keys)
          ? prior.repair_source_event_keys.slice() : [];
        if (keys.includes(sourceEventKey)) {
          result = { id, duplicate: true, condition_status: conditionStatus(prior) };
          return;
        }
        keys.push(sourceEventKey);
        const observedAt = observation.observed_at;
        const updated = {
          ...prior,
          condition_status: nextCondition,
          condition_updated_at: observedAt,
          condition_source: "ai_revisit_comparison",
          repair_observed_at: observedAt,
          repair_drive_id: candidate.drive_id,
          repair_source_event_keys: keys.slice(-64),
          repair_photo: repairPhoto,
          repair_lat: observation.lat,
          repair_lng: observation.lng,
          repair_gps_accuracy: observation.gps_accuracy,
          repair_speed_mps: Number.isFinite(observation.speed_mps) ? observation.speed_mps : null,
          repair_heading: Number.isFinite(observation.heading) ? observation.heading : null,
          repair_current_condition: observation.current_condition,
          repair_assessment: observation.assessment,
          repair_image_quality: observation.image_quality,
          repair_same_location_visible: observation.same_location_visible,
          repair_completed_visible: observation.completed_repair_visible,
          repair_description: String(observation.description || "").trim().slice(0, 1000),
          repair_detection_model: observation.detection_model,
          repair_image_detail: observation.image_detail,
          repair_prompt_version: observation.prompt_version,
          repair_schema_version: observation.schema_version,
        };
        const write = store.put(updated);
        write.onsuccess = () => {
          result = { id, duplicate: false, condition_status: nextCondition, report: toDict(updated) };
        };
        write.onerror = () => { failure = write.error; };
      };
      scan.onerror = () => { failure = scan.error; };
      tx.oncomplete = () => resolve(result || { ignored: true, reason: "target_ambiguous_or_mismatched" });
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = () => {};
    }));
  }

  const MAX_REPAIR_TARGETS = 2000;
  const MAX_REPAIR_TARGET_BATCH_SIZE = 2;
  const MAX_REPAIR_TARGET_IMAGE_BYTES = 4 * 1024 * 1024;
  const MAX_REPAIR_TARGET_TOTAL_BYTES = 512 * 1024 * 1024;

  function fullFramePhoto(report) {
    if (!report) return null;
    if (report.photo_full) return report.photo_full;
    if (isManualCaptureSource(report.capture_source)) return report.photo || null;
    // v13 is the first Drive contract that guarantees every working and evidence image is
    // a complete frame. v16 remains valid after the confirmation-policy upgrade.
    // Older Web Drive rows may store a crop in `photo`, so fail closed.
    return (report.prompt_version === PROMPT_VERSION
      || report.prompt_version === LEGACY_NATIVE_V16_PROMPT_VERSION
      || report.prompt_version === LEGACY_NATIVE_V15_PROMPT_VERSION
      || report.prompt_version === LEGACY_NATIVE_V13_PROMPT_VERSION)
      ? report.photo || null : null;
  }

  function eligibleRepairTarget(report) {
    if (!acceptedReport(report) || conditionStatus(report) === "fixed"
        || report.debug_capture || report.dedupe_eligible === false || !fullFramePhoto(report)
        || report.capture_source === "manual_import"
        || !finiteCoord(report.lat) || !finiteCoord(report.lng)
        || !Number.isFinite(eventTime(report))
        || !Number.isFinite(report.gps_accuracy) || report.gps_accuracy < 0
        || report.gps_accuracy > REPAIR_MAX_ACCURACY_M) return false;
    return isRoadDamageType(report.issue_type);
  }

  function repairTargetPhotoBytes(photo) {
    if (typeof photo === "string") {
      const match = photo.match(/^data:image\/(?:jpeg|jpg|png|webp|gif);base64,([A-Za-z0-9+/]*={0,2})$/i);
      if (!match) return NaN;
      const payload = match[1];
      const padding = payload.endsWith("==") ? 2 : payload.endsWith("=") ? 1 : 0;
      return Math.floor(payload.length * 3 / 4) - padding;
    }
    return photo && Number.isFinite(photo.size) ? Number(photo.size) : NaN;
  }

  // The manifest cursor keeps only numeric ids and stops after the newest 2,000. Calling
  // getAll() here cloned every historical photo into one JS heap before the native bridge
  // had a chance to apply its cap.
  function getRepairTargetIds() {
    return idb().then((d) => new Promise((resolve, reject) => {
      const tx = d.transaction("reports", "readonly");
      const ids = [];
      let selectedBytes = 0;
      let failure = null;
      const scan = tx.objectStore("reports").openCursor(null, "prev");
      scan.onsuccess = () => {
        const cursor = scan.result;
        if (!cursor || ids.length >= MAX_REPAIR_TARGETS) return;
        const report = cursor.value;
        const id = Number(report && report.id);
        const photoBytes = repairTargetPhotoBytes(fullFramePhoto(report));
        if (Number.isSafeInteger(id) && id > 0 && eligibleRepairTarget(report)
            && Number.isFinite(photoBytes) && photoBytes > 0
            && photoBytes <= MAX_REPAIR_TARGET_IMAGE_BYTES
            && selectedBytes <= MAX_REPAIR_TARGET_TOTAL_BYTES - photoBytes) {
          ids.push(id);
          selectedBytes += photoBytes;
        }
        cursor.continue();
      };
      scan.onerror = () => { failure = scan.error; };
      tx.oncomplete = () => failure ? reject(storageError(failure)) : resolve(ids);
      const died = () => reject(storageError(failure || tx.error));
      tx.onabort = died;
      tx.onerror = () => {};
    }));
  }

  async function getRepairTargetBatch(ids) {
    if (!Array.isArray(ids) || !ids.length || ids.length > MAX_REPAIR_TARGET_BATCH_SIZE
        || ids.some((id) => !Number.isSafeInteger(id) || id <= 0)
        || new Set(ids).size !== ids.length) {
      throw new Error("Repair target batch must contain one or two unique report ids.");
    }
    // At most two records and two photos exist in this call at any time.
    const reports = await Promise.all(ids.map((id) => getReport(id)));
    const targets = [];
    for (let index = 0; index < ids.length; index++) {
      const report = reports[index];
      if (!report || Number(report.id) !== ids[index] || !eligibleRepairTarget(report)) {
        throw new Error("Repair history changed while its native cache was being refreshed.");
      }
      const photoBytes = repairTargetPhotoBytes(fullFramePhoto(report));
      if (!Number.isFinite(photoBytes) || photoBytes <= 0
          || photoBytes > MAX_REPAIR_TARGET_IMAGE_BYTES) {
        throw new Error("A repair target photo exceeds the 4 MB native cache limit.");
      }
      targets.push({
        id: report.id,
        lat: report.lat,
        lng: report.lng,
        gps_accuracy: report.gps_accuracy,
        heading: Number.isFinite(report.heading) ? report.heading : null,
        capture_source: report.capture_source || null,
        photo_data_url: await blobToDataUrl(fullFramePhoto(report)),
        last_damage_observed_at: eventTime(report),
        damage_type: storedDamageType(report),
        condition_status: conditionStatus(report),
      });
    }
    return targets;
  }

  async function verifyRepairCandidate(prior, contextDataUrl, fullViews, primaryIndex,
                                       model, detail) {
    const oldEvidence = await blobToDataUrl(fullFramePhoto(prior));
    if (!oldEvidence || !contextDataUrl || !Array.isArray(fullViews) || !fullViews.length) {
      return null;
    }
    // Preserve camera time exactly. Primary-frame quality is already communicated by the
    // layout note; moving it to the front would make the promised chronology false.
    const current = fullViews.filter(Boolean);
    const images = [{ url: oldEvidence }, { url: contextDataUrl },
      ...current.map((url) => ({ url }))];
    const language = LANG() === "uz" ? "\n- Write description in clear Uzbek (Latin script)." : "";
    return analyzeImage(images, REPAIR_PROMPT + language, "road_repair_verification",
      REPAIR_SCHEMA, model, null, false, detail);
  }

  // ---------- image ----------

  // Every detection view preserves the camera's complete field of view. Only whole-frame
  // downscaling, compression, orientation correction, and enhancement are permitted.
  const MAX_PREPARED_FRAME_DIMENSION = 1280;

  function detectionEnhancementPlan(data, width, height) {
    if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0
        || !data || data.length !== width * height * 4) {
      throw new Error("Enhancement pixels must match positive dimensions");
    }
    const step = Math.max(1, Math.floor(Math.sqrt((width * height) / 12000)));
    let luminanceSum = 0, sampleCount = 0, darkCount = 0, brightCount = 0;
    for (let y = 0; y < height; y += step) {
      for (let x = 0; x < width; x += step) {
        const i = (y * width + x) * 4;
        const luminance = 2126 * data[i] + 7152 * data[i + 1] + 722 * data[i + 2];
        luminanceSum += luminance; sampleCount++;
        if (luminance < 120000) darkCount++;
        if (luminance > 2450000) brightCount++;
      }
    }
    const enhanced = luminanceSum < 720000 * sampleCount
      && brightCount * 100 < 8 * sampleCount;
    let gainNumerator = 1, gainDenominator = 1;
    if (enhanced) {
      gainNumerator = 935000 * sampleCount;
      gainDenominator = Math.max(luminanceSum, 350000 * sampleCount);
      if (gainNumerator * 1000 < 1265 * gainDenominator) {
        gainNumerator = 1265; gainDenominator = 1000;
      } else if (gainNumerator * 1000 > 1815 * gainDenominator) {
        gainNumerator = 1815; gainDenominator = 1000;
      }
    }
    return {
      enhanced, sampleCount, luminanceSum, darkCount, brightCount,
      gainNumerator, gainDenominator,
      mean: sampleCount ? luminanceSum / (10000 * sampleCount) : 0,
      dark: sampleCount ? darkCount / sampleCount : 1,
      bright: sampleCount ? brightCount / sampleCount : 0,
    };
  }

  function applyDetectionEnhancement(data, plan) {
    if (!plan || !plan.enhanced) return data;
    const denominator = 2 * plan.gainDenominator;
    const lookup = new Uint8Array(256);
    for (let channel = 0; channel < lookup.length; channel++) {
      const numerator = 2 * channel * plan.gainNumerator + plan.gainDenominator;
      lookup[channel] = Math.max(0, Math.min(255, Math.floor(numerator / denominator)));
    }
    for (let i = 0; i < data.length; i += 4) {
      data[i] = lookup[data[i]];
      data[i + 1] = lookup[data[i + 1]];
      data[i + 2] = lookup[data[i + 2]];
    }
    return data;
  }

  function averageLuminance(ctx, width, height) {
    return detectionEnhancementPlan(ctx.getImageData(0, 0, width, height).data, width, height);
  }

  async function toDataUrl(blob, maxDim, quality = 0.85, boost = false, asBlob = false) {
    const turn = reserveImagePreparation();
    await turn.ready;
    let bmp = null;
    let c = null;
    try {
      bmp = await decodeBoundedImage(blob, maxDim);
      const sw = bmp.width, sh = bmp.height;
      // Match native live detection: preserve the full frame and downscale only. Upscaling
      // invents no detail and would make replay use different pixels from live inference.
      const scale = Math.min(1, maxDim / Math.max(sw, sh));
      c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(sw * scale));
      c.height = Math.max(1, Math.round(sh * scale));
      const ctx = c.getContext("2d");
      ctx.drawImage(bmp, 0, 0, sw, sh, 0, 0, c.width, c.height);
      // Enhancement follows the pixels, not the wall clock. Fixed evening hours boosted
      // bright street-lit frames and amplified noise. Preserve the original evidence copy;
      // this is only the small image used for detection.
      const imageData = boost ? ctx.getImageData(0, 0, c.width, c.height) : null;
      const light = imageData
        ? detectionEnhancementPlan(imageData.data, c.width, c.height) : null;
      if (light && light.enhanced) {
        applyDetectionEnhancement(imageData.data, light);
        ctx.putImageData(imageData, 0, 0);
      }
      if (asBlob) {
        const encoded = await new Promise(resolve => c.toBlob(resolve, "image/jpeg", quality));
        if (!encoded || encoded.size > IMAGE_DECODE_POLICY.maxEncodedBytes) throw imageDecodeError();
        return encoded;
      }
      return c.toDataURL("image/jpeg", quality);
    } finally {
      try {
        if (bmp && bmp.close) bmp.close();
      } finally {
        // Resetting the bitmap dimensions asks WebView to free its graphics backing
        // store immediately instead of retaining it until the canvas is collected.
        try { if (c) { c.width = 0; c.height = 0; } } finally { turn.done(); }
      }
    }
  }

  // ---------- pipeline ----------
  // Detection requests stay concurrent, but their final storage decisions must follow
  // capture order within one drive. Otherwise a later frame can finish inference first,
  // sit just outside the historical radius, and briefly become a second canonical before
  // the earlier bridging frame is known. Callers submit live/VOD frames chronologically;
  // this queue serialises only the short post-detection commit, not model inference.
  const driveCommitTails = new Map();
  function reserveDriveCommit(driveId) {
    if (driveId == null) return null;
    const key = String(driveId);
    const wait = driveCommitTails.get(key) || Promise.resolve();
    let release;
    const own = new Promise((resolve) => { release = resolve; });
    const tail = wait.then(() => own);
    driveCommitTails.set(key, tail);
    tail.finally(() => { if (driveCommitTails.get(key) === tail) driveCommitTails.delete(key); });
    let finished = false;
    return {
      wait,
      done() {
        if (finished) return;
        finished = true;
        release();
      },
    };
  }

  // VOD replay can keep several detector requests in flight. A 1280px canvas plus its
  // ImageData is intentionally short-lived, but preparing one burst per request at the
  // same time can still exhaust a WebView. Serialize only pixel preparation; the lock is
  // released before network inference so model calls retain their existing concurrency.
  let driveImagePreparationTail = Promise.resolve();
  async function withDriveImagePreparation(work) {
    const wait = driveImagePreparationTail;
    let release;
    driveImagePreparationTail = new Promise((resolve) => { release = resolve; });
    await wait;
    try {
      return await work();
    } finally {
      release();
    }
  }

  async function createReport(fd, driveMode) {
    const photos = (fd.getAll ? fd.getAll("photo") : [fd.get("photo")])
      .filter((p) => p && p.size).slice(0, 3);
    if (!photos.length) throw new Error("Empty photo.");
    const requestedPrimary = parseInt(fd.get("primary_index"), 10);
    const primaryIndex = Number.isInteger(requestedPrimary) && requestedPrimary >= 0 && requestedPrimary < photos.length
      ? requestedPrimary : 0;
    const photo = photos[primaryIndex];
    const latRaw = fd.get("lat"), lngRaw = fd.get("lng");
    const lat = latRaw != null && latRaw !== "" ? parseFloat(latRaw) : null;
    const lng = lngRaw != null && lngRaw !== "" ? parseFloat(lngRaw) : null;
    const driveId = driveMode ? (fd.get("drive_id") || null) : null;
    const commitTurn = driveMode ? reserveDriveCommit(driveId) : null;
    try {
    const capturedAtRaw = parseInt(fd.get("captured_at_ms"), 10);
    const sourceOffsetRaw = parseInt(fd.get("source_offset_ms"), 10);
    const gpsAccuracyRaw = parseFloat(fd.get("gps_accuracy"));
    const speedRaw = parseFloat(fd.get("speed"));
    const headingRaw = parseFloat(fd.get("heading"));
    const requestedSource = String(fd.get("capture_source") || "");
    const captureSource = driveMode
      ? (requestedSource === "drive_vod" ? "drive_vod" : "drive_live")
      : normaliseManualCaptureSource(requestedSource);
    const sourceEventKey = driveMode && fd.get("source_event_key")
      ? String(fd.get("source_event_key")).slice(0, 180) : null;
    // Bind the request to the mode in which it began. A Settings change while a slow
    // request is finishing must not unpredictably change whether that observation saves.
    const dedupe = !S.debug;
    let frameQuality = null;
    try { frameQuality = JSON.parse(fd.get("frame_quality") || "null"); } catch (e) {}
    const normalizedHeading = Number.isFinite(headingRaw)
      ? ((headingRaw % 360) + 360) % 360 : null;
    const repairObservationBase = {
      capture_source: captureSource,
      debug_capture: !dedupe,
      drive_id: driveId,
      lat, lng,
      gps_accuracy: Number.isFinite(gpsAccuracyRaw) ? gpsAccuracyRaw : null,
      speed_mps: Number.isFinite(speedRaw) ? speedRaw : null,
      heading: normalizedHeading,
      source_event_key: sourceEventKey,
      observed_at: Number.isFinite(capturedAtRaw) ? capturedAtRaw / 1000 : Date.now() / 1000,
    };
    // Start the local lookup while pixels are resized. Only a precise, later live drive
    // can be a repair revisit; footage replay and Debug must never change real status.
    const repairCandidateP = driveMode && captureSource === "drive_live" && dedupe
      ? findRepairCandidate(repairObservationBase).catch(() => null) : null;

    progress(driveMode ? pmsg("capture") : pmsg("compress"));
    // Measured on a real device: a 2000px frame is ~1.1 MB of base64 and every request
    // is marshalled across the JS-to-native bridge, which made a live detection call
    // take 13.5s median and stuttered the preview. The live pass therefore runs on a
    // smaller frame. Native Drive retains sparse 720p evidence frames beside low-resolution
    // video, so interrupted saved-frame checks can be retried later with nearby temporal
    // context. Single shots stay at full size:
    // one photo, someone waiting, and no footage behind it.
    // Drive Mode supplies one short burst. The model sees a full context encoding of the
    // sharpest frame plus three complete camera frames in chronological order. No model
    // input is cropped, tiled, masked, or limited to a region of interest.
    let imageInputs, dataUrl, fullViews = null, contextDataUrl = null;
    if (driveMode) {
      const prepared = await withDriveImagePreparation(async () => {
        // Build the three complete frames one at a time, preserving chronological order.
        const orderedFullViews = [];
        for (const p of photos) {
          orderedFullViews.push(await toDataUrl(
            p, MAX_PREPARED_FRAME_DIMENSION, 0.85, true
          ));
        }
        return {
          fullViews: orderedFullViews,
          contextDataUrl: await toDataUrl(photo, 768, 0.82, false),
        };
      });
      fullViews = prepared.fullViews;
      contextDataUrl = prepared.contextDataUrl;
      imageInputs = [{ url: contextDataUrl }, ...fullViews.map((url) => ({ url }))];
      dataUrl = fullViews[primaryIndex];
    } else {
      dataUrl = await toDataUrl(photo, 2000, 0.85, true);
      imageInputs = [{ url: dataUrl }];
    }
    // A waiting single-shot user benefits from speculative geocoding. Drive Mode rejects
    // most bursts, so starting a location lookup for every road sample would hammer the
    // public geocoder; it starts only after a burst is accepted.
    const geoP = !driveMode && lat != null
      ? reverseGeocode(lat, lng).catch(() => null) : null;
    const shortOf = (g) => (g && g.short) || null;
    progress(pmsg("detect"));
    const sequenceNote = driveMode
      ? `\n- Capture layout: image 1 is downscaled full-frame context from the sharpest burst frame. Images 2-${imageInputs.length} are complete camera frames in chronological order; chronological frame ${primaryIndex + 1} is the sharpest. No image is cropped, tiled, masked, or limited to a region of interest.`
      : "\n- Capture layout: one user-framed full image.";
    const promptVersion = driveMode ? PROMPT_VERSION : PHOTO_PROMPT_VERSION;
    const detectPrompt = DETECT_PROMPT + (driveMode ? "" : PHOTO_ONLY_PROMPT_SUFFIX)
      + sequenceNote + (LANG() === "uz"
      ? "\n- Write the description field in clear Uzbek (Latin script)."
      : "");
    const detectionModel = driveMode ? DRIVE_DETECTION_MODEL : S.model;
    const detectionDetail = driveMode ? DRIVE_DETECTION_DETAIL : S.detail;
    const repairCandidate = repairCandidateP ? await repairCandidateP : null;
    // Single shot has one verdict on screen, so show it the moment it streams in.
    // Drive Mode analyses run concurrently and report through the HUD instead.
    // Drive Mode has no verdict on screen to update, so it passed no callback and took
    // the unstreamed path, waiting for a description it discards on every rejected frame.
    // It streams now purely to stop as soon as the frame is known to be rejected.
    const modelAssessment = await analyzeImage(imageInputs, detectPrompt, "pothole_binary_assessment",
      ASSESS_SCHEMA, detectionModel, driveMode ? null : emitVerdict,
      driveMode && !S.debug && !repairCandidate, detectionDetail,
      driveMode ? "low" : null);
    let a = binaryAssessment(modelAssessment, driveMode, photos.length);
    if (temporarySurfaceNeedsConfirmation(modelAssessment, driveMode)) {
      // Complete eligible temporary-surface results use a bounded two-of-three vote.
      // Obvious ordinary NOs still stopped in the first stream; any failed or ineligible
      // follow-up remains fail-closed.
      const attempts = [modelAssessment];
      while (temporarySurfaceVoteNeedsAnother(attempts, driveMode, photos.length)) {
        const next = await analyzeImage(
          imageInputs, detectPrompt, "pothole_binary_assessment", ASSESS_SCHEMA,
          detectionModel, null, driveMode && !S.debug && !repairCandidate,
          detectionDetail, "low"
        ).catch(() => null);
        if (!next) break;
        attempts.push(next);
      }
      a = confirmedTemporaryAssessment(
        attempts[0], attempts[1], driveMode, photos.length, attempts[2]
      );
    }
    const decision = decisionFor(a, driveMode, photos.length);
    const accepted = decision === "accept";
    const detector = { model: detectionModel, detail: detectionDetail, prompt_version: promptVersion,
                       schema_version: SCHEMA_VERSION, evidence_count: imageInputs.length };
    if (driveMode && !accepted) {
      // Ordinary non-detection is only the gate. Fixed requires a separate model call
      // that sees the saved before photo and the current usable revisit together.
      if (repairCandidate && clearAbsenceForRepair(a)) {
        progress(pmsg("repair"));
        const comparison = await verifyRepairCandidate(repairCandidate, contextDataUrl,
          fullViews, primaryIndex, detectionModel, detectionDetail).catch(() => null);
        const provenCondition = repairConditionFor(comparison);
        if (provenCondition) {
          if (commitTurn) await commitTurn.wait;
          const repairResult = await applyRepairObservation(repairCandidate.id, {
            ...repairObservationBase,
            ...comparison,
            // Preserve the full scene so a later reviewer can audit whether the before/after
            // frames show the same footprint.
            current_photo_data_url: contextDataUrl,
            detection_model: detectionModel,
            image_detail: detectionDetail,
            prompt_version: REPAIR_PROMPT_VERSION,
            schema_version: REPAIR_SCHEMA_VERSION,
          });
          const applied = !repairResult.ignored ? repairResult.condition_status : null;
          return { analyzed: true, accepted: false, stored: false, found: false,
                   duplicate: false, duplicate_of: null, decision, review: false,
                   repaired: applied === "fixed", repair_review: applied === "repair_review",
                   repair_target_id: repairCandidate.id, repair_result: repairResult,
                   ...a, observation: { ...a }, repair_observation: comparison, detector };
        }
      }
      return { analyzed: true, accepted: false, stored: false, found: false,
               duplicate: false, duplicate_of: null, decision, review: false,
               ...a, observation: { ...a }, detector };
    }

    const duplicateResult = (existing) => driveMode
      ? { analyzed: true, accepted: true, stored: false, found: false,
          duplicate: true, duplicate_of: existing.id, existing_report_id: existing.id,
          skipped: "already reported nearby", decision, review: false,
          ...a, observation: { ...a }, detector }
      : { ...toDict(existing), duplicate: true, duplicate_of: existing.id };

    if (accepted) progress(pmsg("finalize"));
    const geo = accepted
      ? await (geoP || (lat != null ? reverseGeocode(lat, lng).catch(() => null) : Promise.resolve(null)))
      : null;
    const address = shortOf(geo);
    if (accepted) progress(pmsg("write"));
    // The evidence copy keeps the complete camera field of view at higher quality than
    // the detection encoding. Every accepted report keeps it, wherever it happened.
    const photoFull = accepted ? await toDataUrl(photo, 4000, 0.92, false) : null;

    const rec = {
      created_at: Date.now() / 1000, lat, lng, address,
      photo: await dataUrlToBlob(dataUrl), photo_full: await dataUrlToBlob(photoFull),
      issue_type: "road_damage",
      report_origin: "ai_detection",
      is_reportable: a.reportable ? 1 : 0,
      is_pothole: a.damage_type === "pothole_cavity" ? 1 : 0,
      looks_like_speed_breaker: a.looks_like_speed_breaker === true,
      damage_type: a.damage_type, assessment: a.assessment, image_quality: a.image_quality,
      defect_type: a.defect_type,
      surface_type: a.surface_type,
      measurement_provenance: a.measurement_provenance,
      measurement_confidence: a.measurement_confidence,
      measurement_length_cm: a.measurement_length_cm,
      measurement_width_cm: a.measurement_width_cm,
      measurement_depth_cm: a.measurement_depth_cm,
      on_drivable_surface: !!a.on_drivable_surface,
      has_localized_cavity: !!a.has_localized_cavity,
      has_unambiguous_lower_interior: !!a.has_unambiguous_lower_interior,
      has_broken_edge_or_rim: !!a.has_broken_edge_or_rim,
      has_depth_or_surface_loss: !!a.has_depth_or_surface_loss,
      temporal_consistency: a.temporal_consistency,
      size: a.size,
      decision,
      description: a.description,
      status: accepted ? "draft" : "rejected",
      condition_status: "open", condition_updated_at: null, condition_source: null,
      detection_model: detectionModel, image_detail: detectionDetail, prompt_version: promptVersion,
      schema_version: SCHEMA_VERSION, evidence_count: imageInputs.length,
      drive_id: driveId,
      capture_source: captureSource,
      location_source: driveMode ? "drive_gps" : (fd.get("location_source") || null),
      source_event_key: sourceEventKey,
      source_event_keys: sourceEventKey ? [sourceEventKey] : [],
      captured_at: Number.isFinite(capturedAtRaw) ? capturedAtRaw / 1000 : null,
      source_offset_s: Number.isFinite(sourceOffsetRaw) ? sourceOffsetRaw / 1000 : null,
      gps_accuracy: Number.isFinite(gpsAccuracyRaw) ? gpsAccuracyRaw : null,
      speed_mps: Number.isFinite(speedRaw) ? speedRaw : null,
      heading: normalizedHeading,
      frame_quality: Array.isArray(frameQuality) ? frameQuality : null,
      primary_frame_index: primaryIndex,
      debug_capture: !dedupe,
      dedupe_eligible: accepted && dedupe,
      event_sightings: accepted ? [eventSighting({
        drive_id: driveId, lat, lng,
        source_offset_s: Number.isFinite(sourceOffsetRaw) ? sourceOffsetRaw / 1000 : null,
        captured_at: Number.isFinite(capturedAtRaw) ? capturedAtRaw / 1000 : null,
        gps_accuracy: Number.isFinite(gpsAccuracyRaw) ? gpsAccuracyRaw : null,
        speed_mps: Number.isFinite(speedRaw) ? speedRaw : null,
        heading: normalizedHeading,
        source_event_key: sourceEventKey,
      })] : [],
      sighting_drive_ids: accepted && driveId != null ? [String(driveId)] : [],
      seen_count: accepted ? 1 : 0,
      last_seen_at: accepted
        ? (Number.isFinite(capturedAtRaw) ? capturedAtRaw / 1000 : Date.now() / 1000) : null,
    };
    if (accepted) {
      if (commitTurn) await commitTurn.wait;
      const committed = await addReportUnlessDuplicate(rec, dedupe);
      if (committed.duplicate) return duplicateResult(committed.duplicate);
      rec.id = committed.id;
    } else {
      rec.id = await addReport(rec);
    }
    return driveMode
      ? { analyzed: true, accepted: true, stored: true, found: true,
          duplicate: false, duplicate_of: null, decision, review: false,
          ...a, observation: { ...a }, detector, report: toDict(rec) }
      : toDict(rec);
    } finally {
      if (commitTurn) commitTurn.done();
    }
  }

  // A pothole the person photographed and confirmed themselves. It is stored as the
  // person's own report and never shown as AI-confirmed.
  async function createManualReport(fd) {
    const photo = fd.get("photo");
    if (!photo || !photo.size) throw new Error("Empty photo.");
    if (fd.get("issue_confirmed") !== "true") {
      throw new Error("Confirm that this photo shows the pothole you want to report.");
    }
    const latRaw = fd.get("lat"), lngRaw = fd.get("lng");
    const lat = latRaw != null && latRaw !== "" ? parseFloat(latRaw) : null;
    const lng = lngRaw != null && lngRaw !== "" ? parseFloat(lngRaw) : null;
    const gpsAccuracyRaw = parseFloat(fd.get("gps_accuracy"));
    const speedRaw = parseFloat(fd.get("speed"));
    const headingRaw = parseFloat(fd.get("heading"));
    const capturedAtRaw = parseInt(fd.get("captured_at_ms"), 10);
    const captureSource = normaliseManualCaptureSource(String(fd.get("capture_source") || ""));
    const locationSource = String(fd.get("location_source") || "") || null;

    progress(pmsg("compress"));
    const dataUrl = await toDataUrl(photo, 2000, 0.85, true);
    progress(pmsg("write"));
    const capturedAt = Number.isFinite(capturedAtRaw) ? capturedAtRaw / 1000 : null;
    const rec = {
      created_at: Date.now() / 1000,
      captured_at: capturedAt,
      lat, lng, address: null,
      photo: await dataUrlToBlob(dataUrl),
      // Keep the original evidence: the resized copy above is only for fast lists.
      photo_full: photo,
      issue_type: "road_damage",
      issue_confirmation: "user_confirmed_photo",
      report_origin: "user_reported",
      is_reportable: 1,
      is_pothole: null,
      damage_type: null,
      assessment: "manual",
      image_quality: null,
      on_drivable_surface: null,
      has_localized_cavity: null,
      has_unambiguous_lower_interior: null,
      has_broken_edge_or_rim: null,
      has_depth_or_surface_loss: null,
      temporal_consistency: null,
      size: null,
      decision: "manual",
      description: "User-reported pothole; not AI verified",
      status: "draft",
      condition_status: "open", condition_updated_at: null, condition_source: null,
      detection_model: null,
      image_detail: null,
      prompt_version: null,
      schema_version: null,
      evidence_count: 1,
      drive_id: null,
      capture_source: captureSource,
      location_source: locationSource,
      capture_time_source: Number.isFinite(capturedAtRaw)
        ? (captureSource === "manual_camera" ? "camera_return_time"
          : captureSource === "manual_import" ? "file_last_modified" : "provided_time")
        : null,
      source_event_key: null,
      source_event_keys: [],
      source_offset_s: null,
      gps_accuracy: Number.isFinite(gpsAccuracyRaw) ? gpsAccuracyRaw : null,
      speed_mps: Number.isFinite(speedRaw) ? speedRaw : null,
      heading: Number.isFinite(headingRaw) ? ((headingRaw % 360) + 360) % 360 : null,
      frame_quality: null,
      primary_frame_index: 0,
      debug_capture: false,
      dedupe_eligible: false,
      event_sightings: [],
      sighting_drive_ids: [],
      seen_count: 1,
      last_seen_at: capturedAt || Date.now() / 1000,
    };
    if (!finiteCoord(rec.lat) || !finiteCoord(rec.lng)
      || Math.abs(rec.lat) > 90 || Math.abs(rec.lng) > 180) rec.lat = rec.lng = null;
    rec.id = await addReport(rec);
    return toDict(rec);
  }

  // An AI-free Drive candidate: the phone's accelerometer felt a road shock and the
  // complete camera frame from just before the hit is the evidence. It is never shown as
  // a confirmed pothole; the owner's label decides what it was.
  const NATIVE_SENSOR_CAPTURE_SOURCE = "drive_sensor";
  async function importNativeSensorReport(native, nativeId) {
    const lat = Number(native.lat), lng = Number(native.lng);
    if (native.decision !== "sensor_candidate" || native.damage_type !== "road_shock"
      || !native.photo_data_url) {
      return { native_id: nativeId, ignored: true, reason: "invalid_sensor_candidate" };
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      throw new Error("Native report location is invalid.");
    }
    const sourceEventKey = String(native.source_event_key || `native:${nativeId}`).slice(0, 180);
    const gpsAccuracy = native.gps_accuracy == null ? null : Number(native.gps_accuracy);
    const speed = Number(native.speed_mps);
    const heading = Number(native.heading);
    const capturedAt = Number(native.captured_at);
    const offset = Number(native.source_offset_s);
    const driveId = native.drive_id == null ? null : String(native.drive_id);
    const debug = !!native.debug_capture;
    const geo = await reverseGeocode(lat, lng).catch(() => null);
    const address = (geo && geo.short) || native.address || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    const rec = {
      created_at: Number(native.created_at) || Date.now() / 1000,
      lat, lng, address,
      photo: await dataUrlToBlob(native.photo_data_url),
      photo_full: await dataUrlToBlob(native.photo_full_data_url || native.photo_data_url),
      issue_type: "road_damage",
      report_origin: "sensor_detected",
      is_reportable: 0,
      is_pothole: null,
      looks_like_speed_breaker: null,
      damage_type: "road_shock",
      assessment: "sensor",
      image_quality: null,
      defect_type: "unverified_road_shock",
      surface_type: "unknown",
      measurement_provenance: "accelerometer_peak_to_peak",
      measurement_confidence: "low",
      on_drivable_surface: null,
      has_localized_cavity: null,
      has_unambiguous_lower_interior: null,
      has_broken_edge_or_rim: null,
      has_depth_or_surface_loss: null,
      temporal_consistency: null,
      size: null,
      decision: "sensor_candidate",
      description: String(native.description || "Road shock felt by the phone sensor; not verified.").slice(0, 400),
      status: "draft",
      condition_status: "open", condition_updated_at: null, condition_source: null,
      detection_model: "phone_accelerometer",
      image_detail: null,
      prompt_version: String(native.prompt_version || "sensor-shock-v1").slice(0, 40),
      schema_version: Number(native.schema_version) || 1,
      evidence_count: 1,
      drive_id: driveId, capture_source: NATIVE_SENSOR_CAPTURE_SOURCE,
      source_event_key: sourceEventKey, source_event_keys: [sourceEventKey],
      captured_at: Number.isFinite(capturedAt) ? capturedAt : null,
      source_offset_s: Number.isFinite(offset) ? offset : null,
      gps_accuracy: Number.isFinite(gpsAccuracy) ? gpsAccuracy : null,
      speed_mps: Number.isFinite(speed) ? speed : null,
      heading: Number.isFinite(heading) ? ((heading % 360) + 360) % 360 : null,
      frame_quality: null, primary_frame_index: 0,
      debug_capture: debug, dedupe_eligible: !debug,
      event_sightings: [eventSighting({
        drive_id: driveId, lat, lng,
        source_offset_s: Number.isFinite(offset) ? offset : null,
        captured_at: Number.isFinite(capturedAt) ? capturedAt : null,
        gps_accuracy: Number.isFinite(gpsAccuracy) ? gpsAccuracy : null,
        speed_mps: Number.isFinite(speed) ? speed : null,
        heading: Number.isFinite(heading) ? heading : null,
        source_event_key: sourceEventKey,
      })],
      sighting_drive_ids: driveId ? [driveId] : [], seen_count: Number(native.seen_count) || 1,
      last_seen_at: Number.isFinite(Number(native.last_seen_at)) ? Number(native.last_seen_at)
        : Number.isFinite(capturedAt) ? capturedAt : Date.now() / 1000,
    };
    const committed = await addReportUnlessDuplicate(rec, !debug);
    return { native_id: nativeId, id: committed.duplicate ? committed.duplicate.id : committed.id,
             duplicate: !!committed.duplicate };
  }

  async function importNativeReport(native) {
    if (!native || typeof native !== "object") throw new Error("Native report missing.");
    const nativeId = Number(native.id);
    const lat = Number(native.lat), lng = Number(native.lng);
    if (!Number.isFinite(nativeId) || nativeId <= 0) throw new Error("Native report id missing.");
    if (native.capture_source === NATIVE_SENSOR_CAPTURE_SOURCE) return importNativeSensorReport(native, nativeId);
    const nativeIsPothole = native.is_pothole === true || Number(native.is_pothole) === 1;
    const nativeIsReportable = native.is_reportable === true || Number(native.is_reportable) === 1;
    const nativeContract = nativeDetectorContract(native);
    const nativeSize = POTHOLE_SIZES.has(native.size) ? native.size : null;
    const nativeSurface = nativeContract && nativeContract.surfaceTypes.has(native.surface_type)
      ? native.surface_type : "unknown";
    const nativeTemporal = native.temporal_consistency;
    const nativeLowerInterior = native.has_unambiguous_lower_interior === true;
    const lowerInteriorContract = nativeContract &&
      (nativeContract.kind === "current_v19" || nativeContract.kind === "legacy_v16");
    const nativePassedBinaryGate = !!nativeContract && native.decision === "accept"
      && nativeIsPothole && nativeIsReportable && native.damage_type === "pothole_cavity"
      && native.looks_like_speed_breaker === false
      && native.image_quality === "usable" && nativeContract.surfaceTypes.has(nativeSurface)
      && native.on_drivable_surface === true
      && native.has_localized_cavity === true
      && (!lowerInteriorContract || typeof native.has_unambiguous_lower_interior === "boolean")
      && (!lowerInteriorContract || nativeSurface !== TEMPORARY_DRIVABLE_SURFACE
        || nativeLowerInterior)
      && native.has_broken_edge_or_rim === true && native.has_depth_or_surface_loss === true
      && nativeTemporal === "consistent" && Number(native.evidence_count) >= 3 && !!nativeSize;
    // Contracts older than v6, malformed current rows, and v6 rows claiming a v7+-only
    // surface are acknowledged and discarded instead of looping forever or becoming a
    // complaint. Already-synced WebView reports are never reclassified here.
    if (!nativePassedBinaryGate) {
      return { native_id: nativeId, ignored: true, reason: "obsolete_or_invalid_detector_contract" };
    }
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      throw new Error("Native report location is invalid.");
    }
    const sourceEventKey = String(native.source_event_key || `native:${nativeId}`).slice(0, 180);
    const gpsAccuracy = native.gps_accuracy == null ? null : Number(native.gps_accuracy);
    const speed = Number(native.speed_mps);
    const heading = Number(native.heading);
    const geo = await reverseGeocode(lat, lng).catch(() => null);
    const address = (geo && geo.short) || native.address || `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    const assessment = binaryAssessment({
      // Every supported native version saved this row only after its own binary physical
      // gate accepted it. v16+ additionally persists the exact lower-interior verdict.
      is_pothole: true,
      looks_like_speed_breaker: false,
      image_quality: native.image_quality,
      surface_type: nativeSurface,
      on_drivable_surface: true,
      has_localized_cavity: true,
      // Feed legacy accepted rows through the current derived-field helper, then restore
      // the field to unknown below instead of inventing evidence their schema never saved.
      has_unambiguous_lower_interior: lowerInteriorContract ? nativeLowerInterior : true,
      has_broken_edge_or_rim: true,
      has_depth_or_surface_loss: true,
      temporal_consistency: nativeTemporal,
      size: nativeSize,
      description: native.description || "Pothole detected during Drive Mode.",
    }, true, Math.max(2, Number(native.evidence_count) - 1));
    if (!lowerInteriorContract) assessment.has_unambiguous_lower_interior = null;
    const capturedAt = Number(native.captured_at);
    const offset = Number(native.source_offset_s);
    const driveId = native.drive_id == null ? null : String(native.drive_id);
    const debug = !!native.debug_capture;
    const rec = {
      created_at: Number(native.created_at) || Date.now() / 1000,
      lat, lng, address,
      photo: await dataUrlToBlob(native.photo_data_url),
      photo_full: await dataUrlToBlob(native.photo_full_data_url || native.photo_data_url),
      issue_type: "road_damage",
      report_origin: "ai_detection",
      is_reportable: assessment.reportable ? 1 : 0,
      is_pothole: assessment.damage_type === "pothole_cavity" ? 1 : 0,
      looks_like_speed_breaker: false,
      damage_type: assessment.damage_type, assessment: assessment.assessment,
      image_quality: assessment.image_quality,
      defect_type: assessment.defect_type,
      surface_type: assessment.surface_type,
      measurement_provenance: assessment.measurement_provenance,
      measurement_confidence: assessment.measurement_confidence,
      measurement_length_cm: assessment.measurement_length_cm,
      measurement_width_cm: assessment.measurement_width_cm,
      measurement_depth_cm: assessment.measurement_depth_cm,
      on_drivable_surface: assessment.on_drivable_surface,
      has_localized_cavity: assessment.has_localized_cavity,
      has_unambiguous_lower_interior: assessment.has_unambiguous_lower_interior,
      has_broken_edge_or_rim: assessment.has_broken_edge_or_rim,
      has_depth_or_surface_loss: assessment.has_depth_or_surface_loss,
      temporal_consistency: assessment.temporal_consistency,
      size: assessment.size, decision: native.decision || "accept",
      description: assessment.description,
      status: "draft",
      condition_status: "open", condition_updated_at: null, condition_source: null,
      detection_model: native.detection_model || S.model,
      image_detail: native.image_detail || S.detail,
      prompt_version: native.prompt_version || PROMPT_VERSION,
      schema_version: Number(native.schema_version) || SCHEMA_VERSION,
      evidence_count: Number(native.evidence_count) || 1,
      drive_id: driveId, capture_source: "drive_live",
      source_event_key: sourceEventKey, source_event_keys: [sourceEventKey],
      captured_at: Number.isFinite(capturedAt) ? capturedAt : null,
      source_offset_s: Number.isFinite(offset) ? offset : null,
      gps_accuracy: Number.isFinite(gpsAccuracy) ? gpsAccuracy : null,
      speed_mps: Number.isFinite(speed) ? speed : null,
      heading: Number.isFinite(heading) ? ((heading % 360) + 360) % 360 : null,
      frame_quality: null, primary_frame_index: Number(native.primary_frame_index) || 0,
      debug_capture: debug, dedupe_eligible: !debug,
      event_sightings: [eventSighting({
        drive_id: driveId, lat, lng,
        source_offset_s: Number.isFinite(offset) ? offset : null,
        captured_at: Number.isFinite(capturedAt) ? capturedAt : null,
        gps_accuracy: Number.isFinite(gpsAccuracy) ? gpsAccuracy : null,
        speed_mps: Number.isFinite(speed) ? speed : null,
        heading: Number.isFinite(heading) ? heading : null,
        source_event_key: sourceEventKey,
      })],
      sighting_drive_ids: driveId ? [driveId] : [], seen_count: 1,
      last_seen_at: Number.isFinite(capturedAt) ? capturedAt : Date.now() / 1000,
    };
    const committed = await addReportUnlessDuplicate(rec, !debug);
    return { native_id: nativeId, id: committed.duplicate ? committed.duplicate.id : committed.id,
             duplicate: !!committed.duplicate };
  }


  // The photo plus a short plain-text note (when, where, how precise) for sharing.
  async function evidenceForReport(rec) {
    if (conditionStatus(rec) === "fixed") {
      throw new Error("This pothole was verified fixed on a later drive, so its old evidence is archival only.");
    }
    if (!rec || !ACCEPTED_REPORT_STATUSES.has(rec.status)) {
      throw new Error("Only an accepted report has shareable evidence.");
    }
    const fullSource = fullFramePhoto(rec);
    if (!fullSource) throw new Error("A complete full-frame evidence image is unavailable for this legacy report.");
    const source = await dataUrlToBlob(fullSource);
    const wideUrl = await toDataUrl(source, 1280, 0.86, false);
    const base64 = wideUrl && wideUrl.split(",")[1];
    if (!base64) throw new Error("The report photo could not be read.");
    const safeId = String(rec.id || "report").replace(/[^a-zA-Z0-9_-]/g, "");
    const recordedAt = Number.isFinite(rec.captured_at) ? rec.captured_at : rec.created_at;
    const captured = new Date(recordedAt * 1000);
    const when = Number.isNaN(captured.getTime()) ? "" : captured.toLocaleString("en-GB", {
      timeZone: "Asia/Tashkent", dateStyle: "medium", timeStyle: "medium",
    });
    const place = finiteCoord(rec.lat) && finiteCoord(rec.lng)
      ? `${rec.lat.toFixed(6)}, ${rec.lng.toFixed(6)}` : "";
    const lines = [
      rec.report_origin === "user_reported"
        ? "User-reported pothole; not AI verified" : "Pothole detected by Pothole Reporter",
      rec.address ? `Location: ${rec.address}` : "",
      place ? `Coordinates: ${place}` : "",
      place ? `Map: https://www.google.com/maps?q=${place.replace(/\s/g, "")}` : "",
      when ? `${rec.capture_source === "manual_import" ? "Selected photo file date"
        : Number.isFinite(rec.captured_at) ? "Captured" : "Report created"} (Tashkent time): ${when}` : "",
      rec.capture_source === "manual_import"
        ? "Photo provenance: selected/imported by the user; original capture time unknown"
        : rec.capture_source === "manual_camera" ? "Photo provenance: app camera" : "",
      Number.isFinite(rec.gps_accuracy) ? `GPS accuracy: ±${Math.round(rec.gps_accuracy)} m` : "",
    ].filter(Boolean);
    return { name: `pothole-${safeId}.jpg`, base64, text: lines.join("\n") };
  }

  // ---------- dataset export ----------
  // A stored-entry ZIP, written by hand: JPEGs are already compressed, so there is
  // nothing to gain from deflate and no reason to pull in a zip library.
  const CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return (buf) => {
      let c = 0xffffffff;
      for (let i = 0; i < buf.length; i++) c = t[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
      return (c ^ 0xffffffff) >>> 0;
    };
  })();

  function zip(files) {
    const enc = new TextEncoder();
    const chunks = [], central = [];
    let offset = 0;
    const u16 = (n) => [n & 255, (n >> 8) & 255];
    const u32 = (n) => [n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >>> 24) & 255];
    for (const f of files) {
      const name = enc.encode(f.name);
      const crc = CRC(f.data);
      const local = new Uint8Array([...u32(0x04034b50), ...u16(20), ...u16(0), ...u16(0),
        ...u16(0), ...u16(0), ...u32(crc), ...u32(f.data.length), ...u32(f.data.length),
        ...u16(name.length), ...u16(0)]);
      chunks.push(local, name, f.data);
      central.push(new Uint8Array([...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0),
        ...u16(0), ...u16(0), ...u16(0), ...u32(crc), ...u32(f.data.length), ...u32(f.data.length),
        ...u16(name.length), ...u16(0), ...u16(0), ...u16(0), ...u16(0), ...u32(0),
        ...u32(offset)]), name);
      offset += local.length + name.length + f.data.length;
    }
    const centralSize = central.reduce((n, c) => n + c.length, 0);
    const end = new Uint8Array([...u32(0x06054b50), ...u16(0), ...u16(0),
      ...u16(files.length), ...u16(files.length), ...u32(centralSize), ...u32(offset), ...u16(0)]);
    const all = [...chunks, ...central, end];
    const out = new Uint8Array(all.reduce((n, c) => n + c.length, 0));
    let at = 0;
    for (const c of all) { out.set(c, at); at += c.length; }
    return out;
  }

  const b64ToBytes = (b64) => {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  };
  const bytesToB64 = (bytes) => {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
      s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(s);
  };

  // Exports only what a human actually labelled: a model verdict is not ground truth,
  // and a benchmark built from the detector's own opinions cannot measure the detector.
  async function exportDataset() {
    const labelled = (await allReports()).filter((r) =>
      isRoadDamageType(r.issue_type) && r.human_label);
    if (!labelled.length) throw new Error("Nothing labelled yet. Open Review frames and tag some first.");
    if (labelled.some((report) => !fullFramePhoto(report))) {
      throw new Error("A labelled legacy row has no provable full-frame image; remove its label or recapture it before export.");
    }
    const files = [], index = [];
    for (const r of labelled) {
      const name = `images/frame-${r.id}.jpg`;
      files.push({ name, data: b64ToBytes(await photoToBase64(fullFramePhoto(r))) });
      index.push({
        path: name,
        label: r.human_label,
        labelled_by: "owner",
        model_said: r.report_origin === "user_reported" ? null : {
          is_pothole: !!r.is_pothole,
          is_reportable: r.is_reportable == null ? !!r.is_pothole : !!r.is_reportable,
          damage_type: damageTypeOf(r), assessment: assessmentOf(r),
          image_quality: r.image_quality || null,
          defect_type: r.defect_type || (r.is_pothole ? "pothole" : "not_pothole"),
          surface_type: r.surface_type || "unknown",
          measurement_provenance: r.measurement_provenance || null,
          measurement_confidence: r.measurement_confidence || null,
          measurement_length_cm: r.measurement_length_cm == null ? null : r.measurement_length_cm,
          measurement_width_cm: r.measurement_width_cm == null ? null : r.measurement_width_cm,
          measurement_depth_cm: r.measurement_depth_cm == null ? null : r.measurement_depth_cm,
          on_drivable_surface: r.on_drivable_surface == null ? null : !!r.on_drivable_surface,
          has_localized_cavity: r.has_localized_cavity == null ? null : !!r.has_localized_cavity,
          has_unambiguous_lower_interior: r.has_unambiguous_lower_interior == null
            ? null : !!r.has_unambiguous_lower_interior,
          has_broken_edge_or_rim: r.has_broken_edge_or_rim == null ? null : !!r.has_broken_edge_or_rim,
          has_depth_or_surface_loss: r.has_depth_or_surface_loss == null ? null : !!r.has_depth_or_surface_loss,
          temporal_consistency: r.temporal_consistency || null,
          decision: r.decision || (r.status === "rejected" ? "reject" : "accept"),
          size: r.size, description: r.description,
        },
        detector: r.report_origin === "user_reported" ? null : { model: r.detection_model || "legacy", detail: r.image_detail || null,
                    prompt_version: r.prompt_version || "legacy", schema_version: r.schema_version || 1,
                    evidence_count: r.evidence_count || 1 },
        lat: r.lat, lng: r.lng, address: r.address,
        drive_id: r.drive_id, captured_at: new Date(r.created_at * 1000).toISOString(),
      });
    }
    files.push({ name: "labels.json", data: new TextEncoder().encode(
      JSON.stringify({ exported_at: new Date().toISOString(), count: index.length, images: index }, null, 1)) });
    const bytes = zip(files);
    return { name: `road-damage-dataset-${Date.now()}.zip`, base64: bytesToB64(bytes),
             count: index.length, bytes: bytes.length };
  }

  // ---------- API dispatch ----------
  async function handle(path, opts) {
    const method = ((opts && opts.method) || "GET").toUpperCase();
    let m;
    if (path === "/api/health") {
      await CredentialBroker.ready();
      return { ai_configured: CredentialBroker.hasOpenAi(), provider: "openai",
               detection_model: S.model, image_detail: S.detail, prompt_version: PROMPT_VERSION };
    }
    if (path === "/api/reports" && method === "GET") {
      // Without photo_full. The evidence copy is a 4000px JPEG and the list only shows a
      // thumbnail, so shipping it here cost about a megabyte per report on every return
      // to the home screen, and the cost grew with every pothole ever reported. The only
      // reader of it is the email attachment, which loads the record by id anyway.
      const reports = (await allReports()).sort((a, b) => b.id - a.id);
      return reports.map(listDict);
    }
    if (path === "/api/repair-targets" && method === "GET") {
      return { target_ids: await getRepairTargetIds() };
    }
    if (path === "/api/repair-targets" && method === "POST") {
      const body = JSON.parse((opts && opts.body) || "{}");
      return { targets: await getRepairTargetBatch(body.ids) };
    }
    if (path === "/api/native-repair" && method === "POST") {
      const raw = JSON.parse(opts.body || "{}");
      const finiteNumber = (value) => value !== null && value !== "" && Number.isFinite(Number(value))
        ? Number(value) : null;
      const observation = {
        source_event_key: raw.source_event_key,
        observed_at: finiteNumber(raw.observed_at),
        drive_id: raw.drive_id == null ? null : String(raw.drive_id),
        capture_source: "drive_live",
        debug_capture: false,
        lat: finiteNumber(raw.lat),
        lng: finiteNumber(raw.lng),
        gps_accuracy: finiteNumber(raw.gps_accuracy),
        speed_mps: finiteNumber(raw.speed_mps),
        heading: finiteNumber(raw.heading),
        current_photo_data_url: raw.current_photo_data_url,
        current_condition: raw.current_condition,
        assessment: raw.assessment,
        image_quality: raw.image_quality,
        same_location_visible: raw.same_location_visible === true,
        completed_repair_visible: raw.completed_repair_visible === true,
        description: raw.description,
        detection_model: raw.detection_model,
        image_detail: raw.image_detail,
        prompt_version: raw.prompt_version,
        // Provenance is an internal native result contract, not user input to coerce.
        // applyRepairObservation validates these exact values and never fills them in.
        schema_version: raw.schema_version,
      };
      return applyRepairObservation(raw.target_report_id, observation);
    }
    if (path === "/api/reports" && method === "DELETE") {
      await clearAllStoredRecords();
      if (!(await allStoredRecordsAreEmpty())) {
        throw new Error("Some saved reports, media, drives, or other app data remain on this device.");
      }
      return { ok: true };
    }
    if (path === "/api/drives" && method === "GET") return allDrives();
    if (path === "/api/footage" && method === "POST") {
      const fd = opts.body;
      const blob = fd.get("segment"), driveId = String(fd.get("drive_id"));
      const seq = parseInt(fd.get("seq"), 10) || 0;
      const recordingStartedRaw = parseInt(fd.get("recording_started_at_ms"), 10);
      const sourceOffsetRaw = parseInt(fd.get("source_offset_ms"), 10);
      if (!blob || !blob.size) throw new Error("Empty footage segment.");
      await putFootage({ key: `${driveId}#${String(seq).padStart(5, "0")}`, drive_id: driveId,
                         seq, blob, mime: blob.type || "video/mp4", bytes: blob.size,
                         recording_started_at_ms: Number.isFinite(recordingStartedRaw) ? recordingStartedRaw : null,
                         source_offset_s: Number.isFinite(sourceOffsetRaw) ? sourceOffsetRaw / 1000 : null,
                         at: Date.now() / 1000 });
      return { ok: true, bytes: blob.size };
    }
    // Summaries only: the caller asks for the blobs separately, because a drive's
    // footage is hundreds of megabytes and must never be materialised by accident.
    if (path === "/api/footage" && method === "GET") {
      const byDrive = {};
      for (const f of await allFootage()) {
        const clipStart = Number.isFinite(f.recording_started_at_ms)
          ? f.recording_started_at_ms / 1000 : f.at;
        const d = byDrive[f.drive_id] || (byDrive[f.drive_id] = {
          drive_id: f.drive_id, segments: 0, bytes: 0, mime: f.mime,
          started_at: clipStart || null, ended_at: f.at || clipStart || null,
        });
        d.segments++; d.bytes += f.bytes;
        if (clipStart) {
          d.started_at = d.started_at == null ? clipStart : Math.min(d.started_at, clipStart);
        }
        if (f.at || clipStart) {
          const clipEnd = f.at || clipStart;
          d.ended_at = d.ended_at == null ? clipEnd : Math.max(d.ended_at, clipEnd);
        }
      }
      return Object.values(byDrive);
    }
    if ((m = path.match(/^\/api\/footage\/([^/]+)\/blobs$/)) && method === "GET") {
      const segs = (await footageFor(decodeURIComponent(m[1]))).sort((a, b) => a.seq - b.seq);
      if (!segs.length) throw new Error("No footage stored for that drive.");
      return {
        mime: segs[0].mime,
        // `blobs` keeps the old API shape for callers/tests. `clips` carries the true
        // recorder timeline, including gaps and failed sequence numbers.
        blobs: segs.map((x) => x.blob),
        clips: segs.map((x) => ({ seq: x.seq, blob: x.blob,
          recording_started_at_ms: x.recording_started_at_ms || null,
          source_offset_s: Number.isFinite(x.source_offset_s) ? x.source_offset_s : null })),
      };
    }
    if ((m = path.match(/^\/api\/footage\/([^/]+)$/)) && method === "DELETE") {
      const id = decodeURIComponent(m[1]);
      for (const f of await footageFor(id)) await op("readwrite", (s) => s.delete(f.key), "footage");
      return { ok: true };
    }
    if (path === "/api/drives" && method === "POST") {
      const d = JSON.parse(opts.body);
      if (!d || !d.id) throw new Error("Drive id missing.");
      const alreadyIds = Array.isArray(d.already_ids)
        ? [...new Set(d.already_ids.map((x) => String(x).slice(0, 64)))] : [];
      await putDrive({ id: String(d.id), started_at: d.started_at || null,
                       ended_at: Date.now() / 1000, checked: d.checked | 0, found: d.found | 0,
                       already: Math.max(d.already | 0, alreadyIds.length), already_ids: alreadyIds,
                       gps_track: keepTracks() && Array.isArray(d.gps_track) ? d.gps_track : [] });
      return { ok: true };
    }
    if ((m = path.match(/^\/api\/drives\/([^/]+)\/track$/)) && method === "DELETE") {
      const id = decodeURIComponent(m[1]);
      const existing = await getDrive(id);
      if (existing) await putDrive({ ...existing, gps_track: [], track_deleted_at: Date.now() / 1000 });
      return { ok: true };
    }
    if ((m = path.match(/^\/api\/drives\/([^/]+)\/analysis$/)) && method === "POST") {
      const id = decodeURIComponent(m[1]);
      const stats = JSON.parse(opts.body || "{}");
      const prior = await getDrive(id) || {
        id, started_at: stats.started_at || null, ended_at: Date.now() / 1000,
        checked: 0, found: 0, already: 0, already_ids: [], gps_track: [],
      };
      const priorIds = Array.isArray(prior.already_ids) ? prior.already_ids : [];
      const incomingIds = Array.isArray(stats.already_ids) ? stats.already_ids : [];
      prior.already_ids = [...new Set([...priorIds, ...incomingIds]
        .map((x) => String(x).slice(0, 64)))];
      prior.already = Math.max(prior.already | 0, prior.already_ids.length);
      prior.analysis_checked = Math.max(0, stats.checked | 0);
      prior.analysis_found = Math.max(0, stats.found | 0);
      prior.analysis_already = Math.max(0, stats.already | 0, incomingIds.length);
      prior.analysis_planned = Math.max(0, stats.planned | 0);
      prior.analysis_extracted = Math.max(0, stats.extracted | 0);
      prior.analysis_failed = Math.max(0, stats.failed | 0);
      prior.analysis_skipped = Math.max(0, stats.skipped | 0);
      prior.analysis_unreadable_clips = Math.max(0, stats.unreadable_clips | 0);
      prior.analysis_complete = stats.complete === true;
      prior.analysis_at = Date.now() / 1000;
      await putDrive(prior);
      return { ok: true };
    }
    if (path === "/api/export" && method === "POST") return exportDataset();
    if ((m = path.match(/^\/api\/reports\/(\d+)\/evidence$/)) && method === "GET") {
      const rec = await getReport(m[1]);
      if (!rec) throw new Error("Report not found.");
      return evidenceForReport(rec);
    }
    if ((m = path.match(/^\/api\/reports\/(\d+)\/label$/)) && method === "POST") {
      const want = JSON.parse(opts.body).label;
      if (!["pothole_cavity", "failed_patch", "surface_breakup", "rut_or_depression",
            "other_road_damage", "not_reportable", "pothole", "not_pothole", null].includes(want)) {
        throw new Error("Bad label.");
      }
      return mutateReportAtomically(m[1], (rec) => { rec.human_label = want; });
    }
    if ((m = path.match(/^\/api\/reports\/(\d+)\/condition$/)) && method === "POST") {
      const requested = String(JSON.parse(opts.body || "{}").condition_status || "");
      return mutateReportAtomically(m[1], (rec) => {
        if (requested === "fixed") {
          if (conditionStatus(rec) !== "repair_review"
              || rec.repair_current_condition !== "repaired"
              || rec.repair_same_location_visible !== true
              || rec.repair_completed_visible !== true
              || rec.repair_image_quality !== "usable" || !rec.repair_photo) {
            throw new Error("This revisit does not contain enough before-and-after evidence to mark the pothole fixed.");
          }
          rec.condition_status = "fixed";
          rec.condition_updated_at = Date.now() / 1000;
          rec.condition_source = "user_confirmed_revisit";
        } else if (requested === "open") {
          if (conditionStatus(rec) === "open") return;
          rec.condition_status = "open";
          rec.condition_updated_at = Date.now() / 1000;
          rec.condition_source = "user_reopened";
        } else {
          throw new Error("Condition must be fixed or open.");
        }
      });
    }
    if (path === "/api/report" && method === "POST") return createReport(opts.body, false);
    if (path === "/api/manual-report" && method === "POST") return createManualReport(opts.body);
    if ((m = path.match(/^\/api\/reports\/(\d+)\/cloud-analysis$/)) && method === "POST") {
      if (JSON.parse(opts.body || "{}").confirmed !== true) throw new Error("Cloud analysis requires confirmation.");
      const rec = await getReport(m[1]);
      if (!rec || rec.report_origin !== "user_reported" || rec.issue_type !== "road_damage") {
        throw new Error("Only a saved manual pothole report can use this action.");
      }
      const fd = new FormData();
      fd.append("photo", await dataUrlToBlob(fullFramePhoto(rec)));
      fd.append("capture_source", rec.capture_source);
      if (rec.location_source) fd.append("location_source", rec.location_source);
      if (Number.isFinite(rec.speed_mps)) fd.append("speed", String(rec.speed_mps));
      for (const field of ["lat", "lng", "gps_accuracy", "heading"]) {
        if (Number.isFinite(rec[field])) fd.append(field, String(rec[field]));
      }
      if (Number.isFinite(rec.captured_at)) fd.append("captured_at_ms", String(rec.captured_at * 1000));
      // Analysis creates a separate result; it never overwrites the private manual report.
      return createReport(fd, false);
    }
    if (path === "/api/frame" && method === "POST") return createReport(opts.body, true);
    if (path === "/api/native-report" && method === "POST") {
      return importNativeReport(JSON.parse(opts.body || "{}"));
    }
    if ((m = path.match(/^\/api\/reports\/(\d+)$/))) {
      const rec = await getReport(m[1]);
      if (!rec) throw new Error("Report not found.");
      if (method === "DELETE") {
        await delReport(rec.id);
        return { ok: true };
      }
    }
    throw new Error(`Unhandled: ${method} ${path}`);
  }

  // Native hardware back button routes through window.handleAppBack (defined by the UI).
  if (NATIVE) {
    try {
      let App = Capacitor.registerPlugin ? Capacitor.registerPlugin("App") : null;
      if (!App || !App.addListener) App = Capacitor.Plugins && Capacitor.Plugins.App;
      if (App && App.addListener) {
        App.addListener("backButton", () => {
          if (!(window.handleAppBack && window.handleAppBack())) App.exitApp();
        });
        App.addListener("appStateChange", (state) => {
          if (window.handleNativeAppStateChange) {
            window.handleNativeAppStateChange(!!(state && state.isActive));
          }
        });
      }
    } catch (e) {}
  }

  // Pure helpers, exposed for tests. These are references, not copies: a test exercises
  // exactly the code that runs in production. Nothing here holds state or a secret.
  const __pure = {
    peekVerdict, peekReject, rejectedVerdict, decisionFor, binaryAssessment,
    temporarySurfaceNeedsConfirmation, temporarySurfaceVoteEligible,
    temporarySurfaceVoteNeedsAnother, confirmedTemporaryAssessment, nativeDetectorContract,
    damageTypeOf, assessmentOf, normaliseModel, normaliseDetail, summarizeFootageAnalysis,
    vodSampleTimes, vodBurstTimes, DRIVE_DETECTION_MODEL, DRIVE_DETECTION_DETAIL,
    buildDetectionRequest, ASSESS_SCHEMA, DETECT_PROMPT, PROMPT_VERSION,
    PHOTO_ONLY_PROMPT_SUFFIX, PHOTO_PROMPT_VERSION, REPAIR_SCHEMA, REPAIR_PROMPT,
    REPAIR_PROMPT_VERSION, REPAIR_SCHEMA_VERSION, clearAbsenceForRepair, repairConditionFor,
    SCHEMA_VERSION, TRACK_RETENTION_S, trackExpired, freshnessFor, FRESH_THROUGH_S, STALE_AFTER_S, MAX_DETECTION_IMAGES, MAX_REPAIR_IMAGES, MAX_PREPARED_FRAME_DIMENSION,
    IMAGE_DECODE_POLICY, checkedImageDimensions, inspectImageHeader, readImageBounds,
    decodeBoundedImage, toDataUrl, averageLuminance, detectionEnhancementPlan,
    applyDetectionEnhancement, distMeters, roadEventMatch, sameRoadEvent, repairTargetMatch,
    findRepairCandidateFromReports, findDuplicateReport, dataUrlToBlob, blobToDataUrl,
    photoToBase64, toDict, listDict, evidenceForReport, fullFramePhoto,
  };

  window.StandaloneAPI = { __pure, handle, prewarm };

  // The home screen remains usable without an AI key because Garbage and Manhole are
  // explicit user reports. Pothole and Drive open Settings when their key is missing.
})();
