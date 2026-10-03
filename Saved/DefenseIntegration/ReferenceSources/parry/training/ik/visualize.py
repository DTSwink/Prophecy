from __future__ import annotations

# Put the files you want to compare here. Relative paths are resolved from the
# stepper project root. Leave npz_path/checkpoint_path empty to use the newest
# training run's checkpoint_best.pt and the source NPZ recorded in that checkpoint.
npz_path = ""
checkpoint_path = ""
output_path = "training/runs/model_comparisons/model_comparison.html"

import argparse
import base64
import json
import os
from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

try:
    from . import ik_core as tl
    from . import checkpoint_runtime as ckpt_runtime
    from . import excess_envelope as env
    from . import train_simple_ae_controller as simple_ctl
except ImportError:
    import ik_core as tl
    import checkpoint_runtime as ckpt_runtime
    import excess_envelope as env
    import train_simple_ae_controller as simple_ctl


PROJECT_ROOT = Path(__file__).resolve().parents[2]


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Cache-Control" content="no-store, max-age=0">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Model Motion Comparison - {title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101216;
      --panel: #1a1d22;
      --panel2: #23272f;
      --text: #edf1f7;
      --muted: #9da6b5;
      --line: #313846;
      --grid: rgba(255,255,255,0.055);
      --gt: #72a7ff;
      --pred: #ff9b6a;
      --ae-recon: #ffd84f;
      --gt-ae-recon: #67f0c4;
      --root: #e6df83;
      --accent: #55d6a7;
      --volume: rgba(223, 203, 186, 0.30);
      --volume-line: rgba(255, 238, 222, 0.48);
      --foot: rgba(236, 218, 202, 0.40);
      --foot-left: #ff5454;
      --foot-left-fill: rgba(255, 84, 84, 0.36);
      --foot-right: #4ee07e;
      --foot-right-fill: rgba(78, 224, 126, 0.34);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; background: var(--bg); }}
    body {{ font: 13px/1.35 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); }}
    #app {{ width: 100vw; height: 100vh; display: grid; grid-template-rows: 1fr auto; }}
    #viewport {{ position: relative; min-height: 0; }}
    canvas {{ display: block; width: 100%; height: 100%; background: #0f1217; cursor: grab; }}
    canvas:active {{ cursor: grabbing; }}
    .hud {{
      position: absolute;
      top: 12px;
      left: 12px;
      right: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      pointer-events: none;
    }}
    .pill {{
      padding: 6px 8px;
      border-radius: 6px;
      background: rgba(26,29,34,0.9);
      border: 1px solid rgba(255,255,255,0.08);
      color: var(--muted);
    }}
    .pill strong {{ color: var(--text); font-weight: 650; }}
    .checkpoint-picker {{
      position: relative;
      max-width: min(76vw, 760px);
      pointer-events: auto;
      cursor: pointer;
    }}
    .checkpoint-picker strong {{
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .checkpoint-menu {{
      position: absolute;
      z-index: 20;
      top: calc(100% + 6px);
      left: 0;
      display: none;
      min-width: min(76vw, 520px);
      max-width: min(86vw, 760px);
      max-height: min(58vh, 460px);
      overflow-y: auto;
      padding: 6px;
      border-radius: 6px;
      background: rgba(18, 20, 25, 0.98);
      border: 1px solid rgba(255,255,255,0.14);
      box-shadow: 0 18px 60px rgba(0,0,0,0.42);
    }}
    .checkpoint-menu.open {{ display: grid; gap: 4px; }}
    .checkpoint-menu button {{
      width: 100%;
      min-width: 0;
      height: auto;
      padding: 7px 9px;
      text-align: left;
      white-space: normal;
      line-height: 1.25;
    }}
    .checkpoint-menu button.active {{
      border-color: var(--accent);
      color: var(--text);
      background: rgba(85, 214, 167, 0.16);
    }}
    .legend-dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; }}
    #tooltip {{
      position: absolute;
      display: none;
      padding: 5px 7px;
      border-radius: 5px;
      color: var(--text);
      background: rgba(0, 0, 0, 0.78);
      border: 1px solid rgba(255,255,255,0.14);
      pointer-events: none;
      transform: translate(10px, 10px);
      white-space: nowrap;
    }}
    #loadToast {{
      position: absolute;
      left: 12px;
      bottom: 78px;
      z-index: 30;
      transform: translateY(8px);
      padding: 7px 11px;
      border-radius: 6px;
      color: var(--text);
      background: rgba(18, 20, 25, 0.92);
      border: 1px solid rgba(85, 214, 167, 0.55);
      box-shadow: 0 10px 35px rgba(0,0,0,0.34);
      opacity: 0;
      pointer-events: none;
      transition: opacity 120ms ease, transform 120ms ease;
    }}
    #loadToast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    #controls {{
      display: grid;
      grid-template-rows: auto auto;
      gap: 10px;
      padding: 10px 12px;
      background: var(--panel);
      border-top: 1px solid var(--line);
    }}
    #controlToolbar {{
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    #playbackControls {{
      display: grid;
      grid-template-columns: auto auto minmax(240px, 1fr) auto;
      gap: 10px;
      align-items: center;
    }}
    button, input, select {{
      height: 32px;
      color: var(--text);
      background: var(--panel2);
      border: 1px solid var(--line);
      border-radius: 6px;
      font: inherit;
    }}
    button {{ min-width: 42px; padding: 0 11px; cursor: pointer; }}
    button:hover, select:hover {{ border-color: #596273; }}
    button:disabled {{ opacity: 0.42; cursor: default; }}
    select {{ min-width: 220px; padding: 0 8px; }}
    input[type="range"] {{ width: 100%; accent-color: var(--accent); }}
    label {{ display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }}
    .num {{ width: 72px; padding: 0 7px; }}
    @media (max-width: 760px) {{
      #controlToolbar {{
        justify-content: flex-start;
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 2px;
        scrollbar-width: thin;
      }}
      #controlToolbar .wide-extra {{ flex: 0 0 auto; }}
      #playbackControls {{ grid-template-columns: auto minmax(120px, 1fr) auto; }}
      #playbackControls #runSelect {{ display: none !important; }}
    }}
  </style>
</head>
<body>
  <div id="app">
    <div id="viewport">
      <canvas id="canvas"></canvas>
      <div class="hud">
        <div class="pill checkpoint-picker" id="checkpointPicker" title="Click to choose a checkpoint from this run">
          <strong id="titleText">{title}</strong>
          <div id="checkpointMenu" class="checkpoint-menu"></div>
        </div>
        <div class="pill"><strong id="frameText">0</strong> / <span id="lastFrameText">{last_frame}</span></div>
        <div class="pill"><span id="fpsText">{fps}</span> FPS</div>
        <div class="pill"><span id="boneCountText">{bone_count}</span> bones</div>
        <div class="pill"><span class="legend-dot" style="background:var(--gt)"></span>ground truth</div>
        <div class="pill"><span class="legend-dot" style="background:var(--pred)"></span>model <strong id="rolloutText">autoregressive</strong></div>
        <div class="pill" id="aeReconLegend" style="display:none"><span class="legend-dot" style="background:var(--ae-recon)"></span>AE recon</div>
        <div class="pill" id="gtAeReconLegend" style="display:none"><span class="legend-dot" style="background:var(--gt-ae-recon)"></span>GT AE recon</div>
        <div class="pill"><span class="legend-dot" style="background:var(--foot-left)"></span>FootL <span class="legend-dot" style="background:var(--foot-right); margin-left:8px"></span>FootR</div>
        <div class="pill">mean joint error <strong id="errText">0.000</strong> m</div>
        <div class="pill" id="aeScorePill" style="display:none">AE score <strong id="aeScoreText">n/a</strong></div>
      </div>
      <div id="tooltip"></div>
      <div id="loadToast">Model loaded</div>
    </div>
    <div id="controls">
      <div id="controlToolbar">
        <label class="wide-extra">Scale <input id="scale" class="num" type="number" value="1" min="0.05" max="10" step="0.05"></label>
        <button id="predictionMode" class="wide-extra" title="Toggle one-step prediction or full autoregressive rollout">Autoreg</button>
        <button id="aeRecon" class="wide-extra" title="Show the autoencoder reconstruction of the current model prediction">AE Recon</button>
        <label id="aePassControl" class="wide-extra" style="display:none" title="Select recurrent AE reconstruction pass">AE Pass <input id="aePass" class="num" type="number" value="1" min="1" max="1" step="1"></label>
        <button id="gtAeRecon" class="wide-extra" title="Show the autoencoder reconstruction when fed ground-truth transition features">GT AE Recon</button>
        <button id="mode" class="wide-extra" title="Overlay or side-by-side comparison">Overlay</button>
        <button id="volumes" class="wide-extra" title="Toggle bone orientation volumes">Hide Volumes</button>
        <button id="trails" class="wide-extra" title="Toggle recent root trails">Trails</button>
        <button id="labels" class="wide-extra" title="Toggle joint labels">Labels</button>
        <button id="reset" class="wide-extra" title="Reset camera">Reset</button>
      </div>
      <div id="playbackControls">
        <select id="runSelect" title="Choose comparison run"></select>
        <button id="play" title="Play or pause">Play</button>
        <input id="frame" type="range" min="0" max="{last_frame}" value="0" step="1">
        <label>Speed <input id="speed" class="num" type="number" value="1" min="0.1" max="4" step="0.1"></label>
      </div>
    </div>
  </div>
  <script id="motion-data" type="application/json">{payload}</script>
  <script id="checkpoint-manifest" type="application/json">{checkpoint_manifest}</script>
  <script>
    const motions = JSON.parse(document.getElementById("motion-data").textContent);
    let checkpointManifest = JSON.parse(document.getElementById("checkpoint-manifest").textContent || "[]");
    const lazyCheckpointEndpoint = {lazy_checkpoint_endpoint};
    const lazyMaxFrames = {lazy_max_frames};
    const motionCache = new Map();

    function decodeMotion(item) {{
      if (!item || item._decoded) return item;
      item.gt = new Float32Array(Uint8Array.from(atob(item.gt_b64), c => c.charCodeAt(0)).buffer);
      item.gtBasis = new Float32Array(Uint8Array.from(atob(item.gt_basis_b64), c => c.charCodeAt(0)).buffer);
      item.predOne = new Float32Array(Uint8Array.from(atob(item.pred_one_step_b64), c => c.charCodeAt(0)).buffer);
      item.predOneBasis = new Float32Array(Uint8Array.from(atob(item.pred_one_step_basis_b64), c => c.charCodeAt(0)).buffer);
      item.predAr = new Float32Array(Uint8Array.from(atob(item.pred_ar_b64), c => c.charCodeAt(0)).buffer);
      item.predArBasis = new Float32Array(Uint8Array.from(atob(item.pred_ar_basis_b64), c => c.charCodeAt(0)).buffer);
      item.errOne = new Float32Array(Uint8Array.from(atob(item.err_one_step_b64), c => c.charCodeAt(0)).buffer);
      item.errAr = new Float32Array(Uint8Array.from(atob(item.err_ar_b64), c => c.charCodeAt(0)).buffer);
      item.hasAeRecon = Boolean(item.ae_recon_one_step_b64 && item.ae_recon_ar_b64);
      if (item.hasAeRecon) {{
        item.aeReconOne = new Float32Array(Uint8Array.from(atob(item.ae_recon_one_step_b64), c => c.charCodeAt(0)).buffer);
        item.aeReconOneBasis = new Float32Array(Uint8Array.from(atob(item.ae_recon_one_step_basis_b64), c => c.charCodeAt(0)).buffer);
        item.aeReconAr = new Float32Array(Uint8Array.from(atob(item.ae_recon_ar_b64), c => c.charCodeAt(0)).buffer);
        item.aeReconArBasis = new Float32Array(Uint8Array.from(atob(item.ae_recon_ar_basis_b64), c => c.charCodeAt(0)).buffer);
        item.aeScoreOne = new Float32Array(Uint8Array.from(atob(item.ae_score_one_step_b64), c => c.charCodeAt(0)).buffer);
        item.aeScoreAr = new Float32Array(Uint8Array.from(atob(item.ae_score_ar_b64), c => c.charCodeAt(0)).buffer);
        item.aePassCount = Math.max(1, Number(item.ae_recon_pass_count || 1));
        if (item.ae_recon_ar_passes_b64 && item.ae_recon_one_step_passes_b64) {{
          const posStride = item.frame_count * item.bone_count * 3;
          const basisStride = item.frame_count * item.bone_count * 9;
          const scoreStride = item.frame_count;
          const arRaw = new Float32Array(Uint8Array.from(atob(item.ae_recon_ar_passes_b64), c => c.charCodeAt(0)).buffer);
          const arBasisRaw = new Float32Array(Uint8Array.from(atob(item.ae_recon_ar_passes_basis_b64), c => c.charCodeAt(0)).buffer);
          const arScoreRaw = new Float32Array(Uint8Array.from(atob(item.ae_score_ar_passes_b64), c => c.charCodeAt(0)).buffer);
          const oneRaw = new Float32Array(Uint8Array.from(atob(item.ae_recon_one_step_passes_b64), c => c.charCodeAt(0)).buffer);
          const oneBasisRaw = new Float32Array(Uint8Array.from(atob(item.ae_recon_one_step_passes_basis_b64), c => c.charCodeAt(0)).buffer);
          const oneScoreRaw = new Float32Array(Uint8Array.from(atob(item.ae_score_one_step_passes_b64), c => c.charCodeAt(0)).buffer);
          item.aeReconArPasses = [];
          item.aeReconArBasisPasses = [];
          item.aeScoreArPasses = [];
          item.aeReconOnePasses = [];
          item.aeReconOneBasisPasses = [];
          item.aeScoreOnePasses = [];
          for (let p = 0; p < item.aePassCount; p++) {{
            item.aeReconArPasses.push(new Float32Array(arRaw.buffer, p * posStride * 4, posStride));
            item.aeReconArBasisPasses.push(new Float32Array(arBasisRaw.buffer, p * basisStride * 4, basisStride));
            item.aeScoreArPasses.push(new Float32Array(arScoreRaw.buffer, p * scoreStride * 4, scoreStride));
            item.aeReconOnePasses.push(new Float32Array(oneRaw.buffer, p * posStride * 4, posStride));
            item.aeReconOneBasisPasses.push(new Float32Array(oneBasisRaw.buffer, p * basisStride * 4, basisStride));
            item.aeScoreOnePasses.push(new Float32Array(oneScoreRaw.buffer, p * scoreStride * 4, scoreStride));
          }}
        }}
      }}
      item.hasGtAeRecon = Boolean(item.gt_ae_recon_b64);
      if (item.hasGtAeRecon) {{
        item.gtAeRecon = new Float32Array(Uint8Array.from(atob(item.gt_ae_recon_b64), c => c.charCodeAt(0)).buffer);
        item.gtAeReconBasis = new Float32Array(Uint8Array.from(atob(item.gt_ae_recon_basis_b64), c => c.charCodeAt(0)).buffer);
        item.gtAeScore = new Float32Array(Uint8Array.from(atob(item.gt_ae_score_b64), c => c.charCodeAt(0)).buffer);
      }}
      item.pinnedGt = new Int8Array(Uint8Array.from(atob(item.pinned_gt_b64), c => c.charCodeAt(0)).buffer);
      item.pinnedOne = new Int8Array(Uint8Array.from(atob(item.pinned_one_step_b64), c => c.charCodeAt(0)).buffer);
      item.pinnedAr = new Int8Array(Uint8Array.from(atob(item.pinned_ar_b64), c => c.charCodeAt(0)).buffer);
      delete item.gt_b64;
      delete item.gt_basis_b64;
      delete item.pred_one_step_b64;
      delete item.pred_one_step_basis_b64;
      delete item.pred_ar_b64;
      delete item.pred_ar_basis_b64;
      delete item.err_one_step_b64;
      delete item.err_ar_b64;
      delete item.ae_recon_one_step_b64;
      delete item.ae_recon_one_step_basis_b64;
      delete item.ae_recon_ar_b64;
      delete item.ae_recon_ar_basis_b64;
      delete item.ae_recon_one_step_passes_b64;
      delete item.ae_recon_one_step_passes_basis_b64;
      delete item.ae_recon_ar_passes_b64;
      delete item.ae_recon_ar_passes_basis_b64;
      delete item.ae_score_one_step_passes_b64;
      delete item.ae_score_ar_passes_b64;
      delete item.ae_score_one_step_b64;
      delete item.ae_score_ar_b64;
      delete item.gt_ae_recon_b64;
      delete item.gt_ae_recon_basis_b64;
      delete item.gt_ae_score_b64;
      delete item.pinned_gt_b64;
      delete item.pinned_one_step_b64;
      delete item.pinned_ar_b64;
      item._decoded = true;
      return item;
    }}

    function payloadUrl(entry, includeAe) {{
      const url = new URL(lazyCheckpointEndpoint);
      url.searchParams.set("checkpoint", entry.checkpoint_path);
      if (entry.npz_path) url.searchParams.set("npz", entry.npz_path);
      if (entry.ae_checkpoint_path) url.searchParams.set("ae_checkpoint", entry.ae_checkpoint_path);
      if (entry.ae_recon_passes) url.searchParams.set("ae_recon_passes", String(entry.ae_recon_passes));
      if (lazyMaxFrames !== null && lazyMaxFrames !== undefined) url.searchParams.set("max_frames", String(lazyMaxFrames));
      url.searchParams.set("include_ae", includeAe ? "1" : "0");
      return url;
    }}

    function manifestUrl() {{
      if (!lazyCheckpointEndpoint) return null;
      const ref = motion || checkpointManifest[activeMotionIndex] || checkpointManifest[0] || motions[0];
      if (!ref || !ref.checkpoint_path) return null;
      const url = new URL(lazyCheckpointEndpoint);
      url.pathname = "/manifest";
      url.search = "";
      url.searchParams.set("checkpoint", ref.checkpoint_path);
      if (ref.npz_path) url.searchParams.set("npz", ref.npz_path);
      if (ref.ae_checkpoint_path) url.searchParams.set("ae_checkpoint", ref.ae_checkpoint_path);
      if (ref.ae_recon_passes) url.searchParams.set("ae_recon_passes", String(ref.ae_recon_passes));
      return url;
    }}

    function updateAeButtons() {{
      if (!motion.hasAeRecon) showAeRecon = false;
      if (!motion.hasGtAeRecon) showGtAeRecon = false;
      aeReconButton.disabled = !motion.hasAeRecon;
      gtAeReconButton.disabled = !motion.hasGtAeRecon;
      const passCount = Math.max(1, Number(motion.aePassCount || 1));
      aePass = Math.max(1, Math.min(passCount, aePass));
      aePassInput.max = String(passCount);
      aePassInput.value = String(aePass);
      aePassControl.style.display = motion.hasAeRecon && passCount > 1 ? "" : "none";
    }}

    function applyAePayload(target, source) {{
      const keys = [
        "hasAeRecon", "aeReconOne", "aeReconOneBasis", "aeReconAr", "aeReconArBasis", "aeScoreOne", "aeScoreAr",
        "hasGtAeRecon", "gtAeRecon", "gtAeReconBasis", "gtAeScore"
      ];
      for (const key of keys) {{
        if (Object.prototype.hasOwnProperty.call(source, key)) target[key] = source[key];
      }}
      target._aeLoading = false;
      target._aeLoaded = Boolean(target.hasAeRecon || target.hasGtAeRecon);
      if (target === motion) updateAeButtons();
    }}

    async function loadManifestAe(index, target) {{
      if (!checkpointManifest.length || !lazyCheckpointEndpoint || !target) return;
      if (target._aeLoaded || target._aeLoading || target.hasAeRecon || target.hasGtAeRecon) return;
      const entry = checkpointManifest[index];
      if (!entry) return;
      target._aeLoading = true;
      try {{
        const response = await fetch(payloadUrl(entry, true).toString(), {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        const aePayload = decodeMotion(await response.json());
        const cached = motionCache.get(index) || target;
        applyAePayload(cached, aePayload);
      }} catch (error) {{
        target._aeLoading = false;
        console.error(error);
      }}
    }}

    for (const item of motions) {{
      decodeMotion(item);
      if (checkpointManifest.length && Number.isInteger(item.manifest_index)) {{
        motionCache.set(item.manifest_index, item);
      }}
    }}

    const initialChoiceCount = checkpointManifest.length ? checkpointManifest.length : motions.length;
    const initialMotionIndex = Math.max(0, Math.min(initialChoiceCount - 1, Number({initial_motion_index})));
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const runSelect = document.getElementById("runSelect");
    const checkpointPicker = document.getElementById("checkpointPicker");
    const checkpointMenu = document.getElementById("checkpointMenu");
    const titleText = document.getElementById("titleText");
    const frameSlider = document.getElementById("frame");
    const frameText = document.getElementById("frameText");
    const lastFrameText = document.getElementById("lastFrameText");
    const fpsText = document.getElementById("fpsText");
    const boneCountText = document.getElementById("boneCountText");
    const errText = document.getElementById("errText");
    const aeScorePill = document.getElementById("aeScorePill");
    const aeScoreText = document.getElementById("aeScoreText");
    const aeReconLegend = document.getElementById("aeReconLegend");
    const gtAeReconLegend = document.getElementById("gtAeReconLegend");
    const aePassControl = document.getElementById("aePassControl");
    const aePassInput = document.getElementById("aePass");
    const rolloutText = document.getElementById("rolloutText");
    const playButton = document.getElementById("play");
    const speedInput = document.getElementById("speed");
    const scaleInput = document.getElementById("scale");
    const predictionModeButton = document.getElementById("predictionMode");
    const aeReconButton = document.getElementById("aeRecon");
    const gtAeReconButton = document.getElementById("gtAeRecon");
    const modeButton = document.getElementById("mode");
    const volumesButton = document.getElementById("volumes");
    const trailsButton = document.getElementById("trails");
    const labelsButton = document.getElementById("labels");
    const resetButton = document.getElementById("reset");
    const tooltip = document.getElementById("tooltip");
    const loadToast = document.getElementById("loadToast");

    let activeMotionIndex = initialMotionIndex;
    let motion = checkpointManifest.length ? (motionCache.get(activeMotionIndex) || motions[0]) : (motions[activeMotionIndex] || motions[0]);
    let T = 0;
    let J = 0;
    let parents = [];
    let names = [];
    let rootIndex = 0;
    let bounds = null;
    let center = [0, 0, 0];
    let extent = 1;
    let volumeSpecs = [];
    let footSpecs = [];
    let handSpecs = [];
    let renderBones = [];

    let frame = motion.initial_frame || 0;
    let playing = false;
    let showLabels = false;
    let showTrails = true;
    let showVolumes = true;
    let showAeRecon = false;
    let showGtAeRecon = false;
    let aePass = 1;
    let splitMode = false;
    let predictionMode = "autoregressive";
    let yaw = -0.75;
    let pitch = -0.18;
    let zoom = 1.0;
    let panX = 0;
    let panY = 0;
    let dragging = false;
    let panning = false;
    let lastX = 0;
    let lastY = 0;
    let lastTime = performance.now();
    let frameCarry = 0;
    let hoverName = "";

    function checkpointLabel(item, fallbackIndex) {{
      return item.checkpoint_label || item.title || `checkpoint ${{fallbackIndex + 1}}`;
    }}

    let loadToastTimeout = null;
    function showLoadToast(text = "Model loaded") {{
      loadToast.textContent = text;
      loadToast.classList.add("show");
      if (loadToastTimeout !== null) window.clearTimeout(loadToastTimeout);
      loadToastTimeout = window.setTimeout(() => {{
        loadToast.classList.remove("show");
        loadToastTimeout = null;
      }}, 2000);
    }}

    async function loadManifestMotion(index) {{
      if (!checkpointManifest.length) return motions[index];
      if (motionCache.has(index)) {{
        const cached = motionCache.get(index);
        void loadManifestAe(index, cached);
        return cached;
      }}
      const entry = checkpointManifest[index];
      if (!entry || !lazyCheckpointEndpoint) return null;
      const previousTitle = titleText.textContent;
      titleText.textContent = `loading ${{checkpointLabel(entry, index)}}`;
      try {{
        const response = await fetch(payloadUrl(entry, false).toString(), {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        const payload = decodeMotion(await response.json());
        payload.manifest_index = index;
        motionCache.set(index, payload);
        void loadManifestAe(index, payload);
        return payload;
      }} catch (error) {{
        titleText.textContent = `failed to load ${{checkpointLabel(entry, index)}}`;
        console.error(error);
        setTimeout(() => {{ titleText.textContent = previousTitle; }}, 2200);
        return null;
      }}
    }}

    function refreshCheckpointMenu() {{
      for (const button of checkpointMenu.querySelectorAll("button")) {{
        button.classList.toggle("active", Number(button.dataset.index) === activeMotionIndex);
      }}
    }}

    let choiceCount = 0;
    function renderCheckpointChoices() {{
      choiceCount = checkpointManifest.length ? checkpointManifest.length : motions.length;
      runSelect.replaceChildren();
      checkpointMenu.replaceChildren();
      for (let i = 0; i < choiceCount; i++) {{
        const choice = checkpointManifest.length ? checkpointManifest[i] : motions[i];
        const option = document.createElement("option");
        option.value = String(i);
        option.textContent = checkpointLabel(choice, i);
        runSelect.appendChild(option);
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.index = String(i);
        button.textContent = checkpointLabel(choice, i);
        button.addEventListener("click", (event) => {{
          event.stopPropagation();
          checkpointMenu.classList.remove("open");
          void activateMotion(i, true, true);
        }});
        checkpointMenu.appendChild(button);
      }}
      runSelect.style.display = choiceCount > 1 ? "block" : "none";
      checkpointPicker.style.cursor = choiceCount > 1 ? "pointer" : "default";
    }}

    let manifestLoading = false;
    async function refreshManifest() {{
      if (!checkpointManifest.length || manifestLoading) return;
      const url = manifestUrl();
      if (!url) return;
      const currentPath = motion && motion.checkpoint_path ? motion.checkpoint_path : checkpointManifest[activeMotionIndex]?.checkpoint_path;
      manifestLoading = true;
      try {{
        const response = await fetch(url.toString(), {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        const nextManifest = await response.json();
        if (!Array.isArray(nextManifest) || !nextManifest.length) return;
        const cacheByPath = new Map();
        for (let i = 0; i < checkpointManifest.length; i++) {{
          const cached = motionCache.get(i);
          const path = checkpointManifest[i]?.checkpoint_path;
          if (cached && path) cacheByPath.set(path, cached);
        }}
        checkpointManifest = nextManifest;
        motionCache.clear();
        for (let i = 0; i < checkpointManifest.length; i++) {{
          const cached = cacheByPath.get(checkpointManifest[i].checkpoint_path);
          if (cached) {{
            cached.manifest_index = i;
            motionCache.set(i, cached);
          }}
        }}
        const newIndex = checkpointManifest.findIndex(entry => entry.checkpoint_path === currentPath);
        if (newIndex >= 0) {{
          activeMotionIndex = newIndex;
          if (motion) {{
            motion.manifest_index = newIndex;
            motionCache.set(newIndex, motion);
          }}
        }}
        renderCheckpointChoices();
        refreshCheckpointMenu();
      }} catch (error) {{
        console.error(error);
      }} finally {{
        manifestLoading = false;
      }}
    }}

    async function activateMotion(index, preserveFrame = false, announce = false) {{
      activeMotionIndex = Math.max(0, Math.min(motions.length - 1, index));
      if (checkpointManifest.length) {{
        activeMotionIndex = Math.max(0, Math.min(checkpointManifest.length - 1, index));
        const loaded = await loadManifestMotion(activeMotionIndex);
        if (!loaded) return;
        motion = loaded;
      }} else {{
        motion = motions[activeMotionIndex];
      }}
      T = motion.frame_count;
      J = motion.bone_count;
      parents = motion.parents;
      names = motion.bone_names;
      rootIndex = motion.root_index;
      bounds = motion.bounds;
      center = [
        (bounds.min[0] + bounds.max[0]) * 0.5,
        (bounds.min[1] + bounds.max[1]) * 0.5,
        (bounds.min[2] + bounds.max[2]) * 0.5
      ];
      extent = Math.max(
        bounds.max[0] - bounds.min[0],
        bounds.max[1] - bounds.min[1],
        bounds.max[2] - bounds.min[2],
        1
      );
      if (!preserveFrame) frame = motion.initial_frame || 0;
      frame = Math.max(0, Math.min(T - 1, frame));
      updateAeButtons();
      frameSlider.max = String(T - 1);
      frameSlider.value = String(frame);
      const baseTitle = motion.title || "model comparison";
      titleText.textContent = choiceCount > 1 ? `${{baseTitle}} · ${{checkpointLabel(motion, activeMotionIndex)}}` : baseTitle;
      if (runSelect.value !== String(activeMotionIndex)) runSelect.value = String(activeMotionIndex);
      refreshCheckpointMenu();
      lastFrameText.textContent = String(T - 1);
      fpsText.textContent = String(Math.round(motion.fps));
      boneCountText.textContent = String(J);
      const nameToIndex = new Map(names.map((name, index) => [name, index]));
      const lowerOnly = motion.render_lower_only || motion.body_mode === "lower_body";
      const lowerNames = new Set(["pelvis", "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r"]);
      renderBones = names.map(name => !lowerOnly || lowerNames.has(name));
      volumeSpecs = [
        ["pelvis", "spine_01", 12.5], ["spine_01", "spine_02", 13.5], ["spine_02", "spine_03", 14.5],
        ["spine_03", "spine_04", 14.5], ["spine_04", "spine_05", 13.5], ["spine_05", "neck_01", 8.5],
        ["neck_02", "head", 10],
        ["clavicle_l", "upperarm_l", 5.5], ["upperarm_l", "lowerarm_l", 5.8], ["lowerarm_l", "hand_l", 4.8],
        ["clavicle_r", "upperarm_r", 5.5], ["upperarm_r", "lowerarm_r", 5.8], ["lowerarm_r", "hand_r", 4.8],
        ["pelvis", "thigh_l", 9.5], ["thigh_l", "calf_l", 8.3], ["calf_l", "foot_l", 6.2],
        ["pelvis", "thigh_r", 9.5], ["thigh_r", "calf_r", 8.3], ["calf_r", "foot_r", 6.2]
      ].map(([a, b, r]) => ({{ a: nameToIndex.get(a), b: nameToIndex.get(b), r }})).filter(v => v.a !== undefined && v.b !== undefined && renderBones[v.a] && renderBones[v.b]);
      footSpecs = [
        {{ ankle: nameToIndex.get("foot_l"), toe: nameToIndex.get("ball_l"), side: 0 }},
        {{ ankle: nameToIndex.get("foot_r"), toe: nameToIndex.get("ball_r"), side: 1 }}
      ].filter(v => v.ankle !== undefined && v.toe !== undefined);
      handSpecs = lowerOnly ? [] : [
        {{ bone: nameToIndex.get("hand_l"), mid: nameToIndex.get("middle_03_l") }},
        {{ bone: nameToIndex.get("hand_r"), mid: nameToIndex.get("middle_03_r") }}
      ].filter(v => v.bone !== undefined);
      frameCarry = 0;
      if (announce) showLoadToast("Model loaded");
    }}

    renderCheckpointChoices();
    void activateMotion(initialMotionIndex);
    void refreshManifest();

    function resize() {{
      const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }}

    function posAt(arr, f, j, offsetX = 0) {{
      const i = (f * J + j) * 3;
      return [arr[i] + offsetX, arr[i + 1], arr[i + 2]];
    }}
    function basisAxisAt(basis, f, j, axis) {{
      const i = (f * J + j) * 9 + axis * 3;
      return [basis[i], basis[i + 1], basis[i + 2]];
    }}
    function add3(a, b) {{ return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }}
    function sub3(a, b) {{ return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }}
    function mul3(a, s) {{ return [a[0] * s, a[1] * s, a[2] * s]; }}
    function dot3(a, b) {{ return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }}
    function len3(a) {{ return Math.max(1e-6, Math.hypot(a[0], a[1], a[2])); }}

    function rotateProject(p) {{
      const scale = Number(scaleInput.value) || 1;
      const x0 = (p[0] - center[0]) * scale;
      const y0 = (p[1] - center[1]) * scale;
      const z0 = (p[2] - center[2]) * scale;
      const cy = Math.cos(yaw), sy = Math.sin(yaw);
      const cp = Math.cos(pitch), sp = Math.sin(pitch);
      const x1 = x0 * cy - z0 * sy;
      const z1 = x0 * sy + z0 * cy;
      const y1 = y0 * cp - z1 * sp;
      const z2 = y0 * sp + z1 * cp;
      const s = Math.min(canvas.clientWidth, canvas.clientHeight) * 0.72 * zoom / extent;
      return {{
        x: canvas.clientWidth * 0.5 + panX + x1 * s,
        y: canvas.clientHeight * 0.55 + panY - y1 * s,
        z: z2
      }};
    }}

    function drawGrid() {{
      const step = 0.5;
      const size = Math.max(3, Math.ceil(extent / step) * step);
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--grid").trim();
      ctx.lineWidth = 1;
      for (let i = -size; i <= size + 1e-4; i += step) {{
        const a = rotateProject([center[0] - size, 0, center[2] + i]);
        const b = rotateProject([center[0] + size, 0, center[2] + i]);
        const c = rotateProject([center[0] + i, 0, center[2] - size]);
        const d = rotateProject([center[0] + i, 0, center[2] + size]);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(d.x, d.y); ctx.stroke();
      }}
    }}

    function drawJoint(p, color, radius) {{
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }}

    function worldRadiusPx(radiusWorld) {{
      const scale = Number(scaleInput.value) || 1;
      return Math.max(3, radiusWorld * scale * Math.min(canvas.clientWidth, canvas.clientHeight) * 0.72 * zoom / extent);
    }}

    function drawCapsule(arr, a, b, radiusWorld, offsetX, fill, stroke, alpha) {{
      const pa = rotateProject(posAt(arr, frame, a, offsetX));
      const pb = rotateProject(posAt(arr, frame, b, offsetX));
      const radiusPx = worldRadiusPx(radiusWorld);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = fill;
      ctx.lineWidth = radiusPx * 2;
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = Math.max(1, radiusPx * 0.08);
      ctx.beginPath();
      ctx.moveTo(pa.x, pa.y);
      ctx.lineTo(pb.x, pb.y);
      ctx.stroke();
      ctx.restore();
    }}

    function drawAxisTick(center, axis, length, color) {{
      const a = rotateProject(center);
      const b = rotateProject(add3(center, mul3(axis, length)));
      ctx.save();
      ctx.strokeStyle = color;
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.restore();
    }}

    function drawOrientedBox(center, axisX, axisY, axisZ, dims, stroke, fill, alpha) {{
      const hx = dims[0] * 0.5, hy = dims[1] * 0.5, hz = dims[2] * 0.5;
      const corners = [
        [-hx,-hy,-hz], [ hx,-hy,-hz], [ hx, hy,-hz], [-hx, hy,-hz],
        [-hx,-hy, hz], [ hx,-hy, hz], [ hx, hy, hz], [-hx, hy, hz]
      ].map(c => rotateProject(add3(add3(add3(center, mul3(axisX, c[0])), mul3(axisY, c[1])), mul3(axisZ, c[2]))));
      const faces = [
        [0,1,2,3], [4,5,6,7], [0,1,5,4], [1,2,6,5], [2,3,7,6], [3,0,4,7]
      ].map(face => ({{
        face,
        z: face.reduce((acc, i) => acc + corners[i].z, 0) / face.length
      }})).sort((a, b) => a.z - b.z);
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = fill;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1.1;
      for (const item of faces) {{
        ctx.beginPath();
        for (let k = 0; k < item.face.length; k++) {{
          const p = corners[item.face[k]];
          if (k === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        }}
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }}
      ctx.restore();
    }}

    function footBlockSpec(arr, basis, ankle, toe, offsetX) {{
      const foot = posAt(arr, frame, ankle, offsetX);
      const toePos = posAt(arr, frame, toe, offsetX);
      let up = basisAxisAt(basis, frame, ankle, 0);
      let forward = basisAxisAt(basis, frame, ankle, 1);
      const sideAxis = basisAxisAt(basis, frame, ankle, 2);
      const toeVector = sub3(toePos, foot);
      if (dot3(forward, toeVector) < 0) forward = mul3(forward, -1);
      if (up[1] < 0) up = mul3(up, -1);
      const ballDistance = Math.max(0.10, Math.min(0.28, Math.abs(dot3(toeVector, forward))));
      const heelLength = 0.07;
      const length = ballDistance + heelLength;
      const width = 0.11;
      const height = 0.064;
      const ballBack = add3(toePos, mul3(forward, -ballDistance));
      const heelBack = add3(ballBack, mul3(forward, -heelLength));
      const c = add3(add3(heelBack, mul3(forward, length * 0.5)), mul3(up, -0.006));
      return {{ center: c, forward, sideAxis, up, dims: [length, width, height] }};
    }}

    function toeBlockSpec(arr, basis, ankle, toe, offsetX) {{
      const foot = posAt(arr, frame, ankle, offsetX);
      const toePos = posAt(arr, frame, toe, offsetX);
      let forward = basisAxisAt(basis, frame, toe, 0);
      let up = basisAxisAt(basis, frame, toe, 1);
      const sideAxis = basisAxisAt(basis, frame, toe, 2);
      const toeVector = sub3(toePos, foot);
      if (dot3(forward, toeVector) < 0) forward = mul3(forward, -1);
      if (up[1] < 0) up = mul3(up, -1);
      const toeLength = 0.065;
      const c = add3(add3(toePos, mul3(forward, toeLength * 0.5)), mul3(up, -0.006));
      return {{ center: c, forward, sideAxis, up, dims: [toeLength, 0.11, 0.064] }};
    }}

    function colliderBottomY(spec) {{
      return spec.center[1] - Math.abs(spec.up[1]) * spec.dims[2] * 0.5;
    }}

    function pinnedFootSide(arr, basis, offsetX) {{
      let bestSide = -1;
      let bestY = Infinity;
      for (const f of footSpecs) {{
        const footSpec = footBlockSpec(arr, basis, f.ankle, f.toe, offsetX);
        const toeSpec = toeBlockSpec(arr, basis, f.ankle, f.toe, offsetX);
        const y = Math.min(colliderBottomY(footSpec), colliderBottomY(toeSpec));
        if (y < bestY) {{
          bestY = y;
          bestSide = f.side;
        }}
      }}
      return bestSide;
    }}

    function drawFootBlock(arr, basis, ankle, toe, offsetX, color, fill, alpha) {{
      const spec = footBlockSpec(arr, basis, ankle, toe, offsetX);
      drawOrientedBox(spec.center, spec.forward, spec.sideAxis, spec.up, spec.dims, color, fill, alpha);
      drawAxisTick(spec.center, spec.forward, spec.dims[0] * 0.5, color);
    }}

    function drawToeBlock(arr, basis, ankle, toe, offsetX, color, fill, alpha) {{
      const spec = toeBlockSpec(arr, basis, ankle, toe, offsetX);
      drawOrientedBox(spec.center, spec.forward, spec.sideAxis, spec.up, spec.dims, color, fill, alpha);
      drawAxisTick(spec.center, spec.forward, spec.dims[0] * 0.5, color);
    }}

    function drawHandBox(arr, basis, spec, offsetX, color, alpha) {{
      const bone = spec.bone;
      const hand = posAt(arr, frame, bone, offsetX);
      let forward = basisAxisAt(basis, frame, bone, 0);
      const sideAxis = basisAxisAt(basis, frame, bone, 1);
      let up = basisAxisAt(basis, frame, bone, 2);
      if (spec.mid !== undefined) {{
        const fingerVector = sub3(posAt(arr, frame, spec.mid, offsetX), hand);
        if (dot3(forward, fingerVector) < 0) forward = mul3(forward, -1);
      }}
      if (up[1] < 0) up = mul3(up, -1);
      const c = add3(add3(hand, mul3(forward, 0.052)), mul3(up, -0.0025));
      drawOrientedBox(c, forward, up, sideAxis, [0.125, 0.115, 0.038], color, "rgba(236, 218, 202, 0.38)", alpha);
      drawAxisTick(c, forward, 0.08, color);
    }}

    function drawVolumesFor(arr, basis, color, offsetX, alpha) {{
      if (!showVolumes) return;
      const fill = getComputedStyle(document.documentElement).getPropertyValue("--volume").trim();
      const footLeftColor = getComputedStyle(document.documentElement).getPropertyValue("--foot-left").trim();
      const footLeftFill = getComputedStyle(document.documentElement).getPropertyValue("--foot-left-fill").trim();
      const footRightColor = getComputedStyle(document.documentElement).getPropertyValue("--foot-right").trim();
      const footRightFill = getComputedStyle(document.documentElement).getPropertyValue("--foot-right-fill").trim();
      for (const v of volumeSpecs) drawCapsule(arr, v.a, v.b, v.r * 0.01, offsetX, fill, color, alpha);
      for (const h of handSpecs) drawHandBox(arr, basis, h, offsetX, color, alpha);
      for (const f of footSpecs) {{
        const isFootR = f.side === 1;
        const footColor = isFootR ? footRightColor : footLeftColor;
        const footFill = isFootR ? footRightFill : footLeftFill;
        drawFootBlock(arr, basis, f.ankle, f.toe, offsetX, footColor, footFill, alpha);
        drawToeBlock(arr, basis, f.ankle, f.toe, offsetX, footColor, footFill, alpha);
      }}
    }}

    function drawSkeleton(arr, color, offsetX, alpha, width) {{
      const points = Array.from({{ length: J }}, (_, j) => rotateProject(posAt(arr, frame, j, offsetX)));
      const edges = [];
      for (let j = 0; j < J; j++) {{
        const p = parents[j];
        if (p >= 0 && renderBones[j] && renderBones[p]) edges.push([points[j].z + points[p].z, j, p]);
      }}
      edges.sort((a, b) => a[0] - b[0]);
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      for (const [, j, p] of edges) {{
        ctx.beginPath();
        ctx.moveTo(points[p].x, points[p].y);
        ctx.lineTo(points[j].x, points[j].y);
        ctx.stroke();
      }}
      for (let j = 0; j < J; j++) {{
        if (!renderBones[j]) continue;
        drawJoint(points[j], color, j === rootIndex ? 4.5 : 2.6);
      }}
      ctx.globalAlpha = 1;
      return points;
    }}

    function drawTrailsFor(arr, color, offsetX) {{
      if (!showTrails) return;
      const start = Math.max(0, frame - 45);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.42;
      ctx.beginPath();
      for (let f = start; f <= frame; f++) {{
        const p = rotateProject(posAt(arr, f, rootIndex, offsetX));
        if (f === start) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }}
      ctx.stroke();
      ctx.globalAlpha = 1;
    }}

    function draw() {{
      resize();
      ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      drawGrid();
      const gtColor = getComputedStyle(document.documentElement).getPropertyValue("--gt").trim();
      const predColor = getComputedStyle(document.documentElement).getPropertyValue("--pred").trim();
      const aeColor = getComputedStyle(document.documentElement).getPropertyValue("--ae-recon").trim();
      const gtAeColor = getComputedStyle(document.documentElement).getPropertyValue("--gt-ae-recon").trim();
      const pred = predictionMode === "autoregressive" ? motion.predAr : motion.predOne;
      const predBasis = predictionMode === "autoregressive" ? motion.predArBasis : motion.predOneBasis;
      const err = predictionMode === "autoregressive" ? motion.errAr : motion.errOne;
      const passIndex = Math.max(0, Math.min(Math.max(1, Number(motion.aePassCount || 1)) - 1, aePass - 1));
      const aeRecon = predictionMode === "autoregressive"
        ? (motion.aeReconArPasses ? motion.aeReconArPasses[passIndex] : motion.aeReconAr)
        : (motion.aeReconOnePasses ? motion.aeReconOnePasses[passIndex] : motion.aeReconOne);
      const aeReconBasis = predictionMode === "autoregressive"
        ? (motion.aeReconArBasisPasses ? motion.aeReconArBasisPasses[passIndex] : motion.aeReconArBasis)
        : (motion.aeReconOneBasisPasses ? motion.aeReconOneBasisPasses[passIndex] : motion.aeReconOneBasis);
      const aeScore = predictionMode === "autoregressive"
        ? (motion.aeScoreArPasses ? motion.aeScoreArPasses[passIndex] : motion.aeScoreAr)
        : (motion.aeScoreOnePasses ? motion.aeScoreOnePasses[passIndex] : motion.aeScoreOne);
      const drawAeRecon = showAeRecon && motion.hasAeRecon && aeRecon && aeReconBasis && aeScore;
      const drawGtAeRecon = showGtAeRecon && motion.hasGtAeRecon && motion.gtAeRecon && motion.gtAeReconBasis && motion.gtAeScore;
      const sep = splitMode ? extent * 0.42 : 0;
      drawTrailsFor(motion.gt, gtColor, -sep);
      drawTrailsFor(pred, predColor, sep);
      if (drawAeRecon) drawTrailsFor(aeRecon, aeColor, sep);
      if (drawGtAeRecon) drawTrailsFor(motion.gtAeRecon, gtAeColor, -sep);
      drawVolumesFor(motion.gt, motion.gtBasis, gtColor, -sep, splitMode ? 0.36 : 0.22);
      drawVolumesFor(pred, predBasis, predColor, sep, 0.42);
      if (drawAeRecon) drawVolumesFor(aeRecon, aeReconBasis, aeColor, sep, 0.28);
      if (drawGtAeRecon) drawVolumesFor(motion.gtAeRecon, motion.gtAeReconBasis, gtAeColor, -sep, 0.32);
      const gtPoints = drawSkeleton(motion.gt, gtColor, -sep, splitMode ? 0.9 : 0.54, splitMode ? 4.0 : 5.0);
      const predPoints = drawSkeleton(pred, predColor, sep, 0.92, 3.2);
      if (drawAeRecon) drawSkeleton(aeRecon, aeColor, sep, 0.96, 2.8);
      if (drawGtAeRecon) drawSkeleton(motion.gtAeRecon, gtAeColor, -sep, 0.96, 2.8);

      if (!splitMode) {{
        ctx.strokeStyle = "rgba(255,255,255,0.18)";
        ctx.lineWidth = 1;
        for (let j = 0; j < J; j += 3) {{
          if (!renderBones[j]) continue;
          ctx.beginPath();
          ctx.moveTo(gtPoints[j].x, gtPoints[j].y);
          ctx.lineTo(predPoints[j].x, predPoints[j].y);
          ctx.stroke();
        }}
      }}

      if (showLabels) {{
        ctx.font = "11px system-ui, sans-serif";
        ctx.fillStyle = "rgba(237,241,247,0.72)";
        for (let j = 0; j < J; j++) {{
          if (!renderBones[j]) continue;
          const p = predPoints[j];
          ctx.fillText(names[j], p.x + 5, p.y - 5);
        }}
      }}

      if (splitMode) {{
        ctx.font = "15px system-ui, sans-serif";
        ctx.fillStyle = gtColor;
        ctx.fillText("ground truth", 16, canvas.clientHeight - 18);
        ctx.fillStyle = predColor;
        ctx.fillText("model", canvas.clientWidth - 70, canvas.clientHeight - 18);
      }}
      frameSlider.value = frame;
      frameText.textContent = String(frame);
      errText.textContent = err[frame].toFixed(4);
      const scoreParts = [];
      if (drawAeRecon) {{
        const score = aeScore[frame];
        const label = Math.max(1, Number(motion.aePassCount || 1)) > 1 ? `model p${{passIndex + 1}} ` : "model ";
        scoreParts.push(label + (Number.isFinite(score) ? score.toFixed(6) : "n/a"));
      }}
      if (drawGtAeRecon) {{
        const score = motion.gtAeScore[frame];
        scoreParts.push("GT " + (Number.isFinite(score) ? score.toFixed(6) : "n/a"));
      }}
      aeScoreText.textContent = scoreParts.length ? scoreParts.join(" / ") : "n/a";
      aeScorePill.style.display = scoreParts.length ? "" : "none";
      aeReconLegend.style.display = drawAeRecon ? "" : "none";
      gtAeReconLegend.style.display = drawGtAeRecon ? "" : "none";
      rolloutText.textContent = predictionMode === "autoregressive" ? "autoregressive" : "one-step";
      playButton.textContent = playing ? "Pause" : "Play";
      predictionModeButton.textContent = predictionMode === "autoregressive" ? "Autoreg" : "One-step";
      aeReconButton.textContent = showAeRecon ? "Hide AE Recon" : "AE Recon";
      gtAeReconButton.textContent = showGtAeRecon ? "Hide GT AE" : "GT AE Recon";
      modeButton.textContent = splitMode ? "Split" : "Overlay";
      volumesButton.textContent = showVolumes ? "Hide Volumes" : "Volumes";
      trailsButton.textContent = showTrails ? "Hide Trails" : "Trails";
      labelsButton.textContent = showLabels ? "Hide Labels" : "Labels";
    }}

    function tick(now) {{
      const dt = Math.min(0.1, (now - lastTime) / 1000);
      lastTime = now;
      if (playing) {{
        frameCarry += dt * motion.fps * (Number(speedInput.value) || 1);
        while (frameCarry >= 1) {{
          frame = (frame + 1) % T;
          frameCarry -= 1;
        }}
      }}
      draw();
      requestAnimationFrame(tick);
    }}

    canvas.addEventListener("mousemove", (event) => {{
      if (dragging) {{
        const dx = event.clientX - lastX;
        const dy = event.clientY - lastY;
        if (panning) {{
          panX += dx;
          panY += dy;
        }} else {{
          yaw += dx * 0.006;
          pitch = Math.max(-1.35, Math.min(1.35, pitch + dy * 0.006));
        }}
        lastX = event.clientX;
        lastY = event.clientY;
      }}
      tooltip.style.display = hoverName ? "block" : "none";
      tooltip.style.left = event.clientX + "px";
      tooltip.style.top = event.clientY + "px";
      tooltip.textContent = hoverName;
    }});
    canvas.addEventListener("mousedown", (event) => {{
      dragging = true;
      panning = event.button === 1 || event.shiftKey;
      lastX = event.clientX;
      lastY = event.clientY;
    }});
    window.addEventListener("mouseup", () => {{ dragging = false; }});
    canvas.addEventListener("wheel", (event) => {{
      event.preventDefault();
      zoom = Math.max(0.15, Math.min(8, zoom * Math.exp(-event.deltaY * 0.001)));
    }}, {{ passive: false }});
    frameSlider.addEventListener("input", () => {{
      frame = Number(frameSlider.value);
      frameCarry = 0;
    }});
    runSelect.addEventListener("change", () => {{
      activateMotion(Number(runSelect.value), true, true);
    }});
    checkpointPicker.addEventListener("click", (event) => {{
      if (choiceCount <= 1) return;
      event.stopPropagation();
      void refreshManifest();
      checkpointMenu.classList.toggle("open");
      refreshCheckpointMenu();
    }});
    window.addEventListener("click", () => {{
      checkpointMenu.classList.remove("open");
    }});
    playButton.addEventListener("click", () => {{ playing = !playing; }});
    predictionModeButton.addEventListener("click", () => {{
      predictionMode = predictionMode === "autoregressive" ? "one_step" : "autoregressive";
    }});
    aeReconButton.addEventListener("click", () => {{
      if (motion.hasAeRecon) showAeRecon = !showAeRecon;
    }});
    aePassInput.addEventListener("input", () => {{
      const passCount = Math.max(1, Number(motion.aePassCount || 1));
      aePass = Math.max(1, Math.min(passCount, Number(aePassInput.value) || 1));
      aePassInput.value = String(aePass);
    }});
    gtAeReconButton.addEventListener("click", () => {{
      if (motion.hasGtAeRecon) showGtAeRecon = !showGtAeRecon;
    }});
    modeButton.addEventListener("click", () => {{ splitMode = !splitMode; }});
    volumesButton.addEventListener("click", () => {{ showVolumes = !showVolumes; }});
    trailsButton.addEventListener("click", () => {{ showTrails = !showTrails; }});
    labelsButton.addEventListener("click", () => {{ showLabels = !showLabels; }});
    resetButton.addEventListener("click", () => {{
      yaw = -0.75; pitch = -0.18; zoom = 1.0; panX = 0; panY = 0;
    }});
    window.addEventListener("keydown", (event) => {{
      if (event.code === "Space") {{ event.preventDefault(); playing = !playing; }}
      if (event.key === "ArrowRight") frame = Math.min(T - 1, frame + 1);
      if (event.key === "ArrowLeft") frame = Math.max(0, frame - 1);
    }});
    window.addEventListener("resize", resize);
    requestAnimationFrame(tick);
  </script>
</body>
</html>
"""


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def resolve_optional_path(path_text: str | None) -> Path | None:
    if path_text is None or not str(path_text).strip():
        return None
    return resolve_path(str(path_text))


def checkpoint_tag_priority(path: Path) -> int:
    name = path.name.lower()
    if name.endswith("_last.pt") or name == "checkpoint_last.pt":
        return 4
    if name.endswith("_latest.pt") or name == "checkpoint_latest.pt":
        return 3
    if "_stage_" in name:
        return 2
    if name.endswith("_best.pt") or name == "checkpoint_best.pt":
        return 1
    return 0


def checkpoint_sort_key(path: Path) -> tuple[int, int, str]:
    try:
        checkpoint_mtime = int(path.stat().st_mtime_ns)
    except OSError:
        checkpoint_mtime = 0
    return (checkpoint_mtime, checkpoint_tag_priority(path), str(path).lower())


def likely_controller_checkpoint_path(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() not in {".pt", ".pth"}:
        return False
    lower_name = path.name.lower()
    if lower_name.endswith("_init.pt") or lower_name == "checkpoint_init.pt":
        return False
    if path.parent.name != "checkpoints":
        return False
    return True


def is_current_controller_checkpoint_path(path: Path) -> bool:
    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
    except Exception:
        return False
    return ckpt_runtime.is_current_ik_controller_checkpoint(ckpt)


def find_latest_checkpoint(name_contains: str = "") -> Path:
    run_root = PROJECT_ROOT / "training" / "runs"
    filter_text = str(name_contains or "").lower().strip()
    candidates: list[Path] = []
    if run_root.exists():
        for checkpoint_dir in run_root.glob("*/checkpoints"):
            try:
                candidates.extend(
                    path for path in checkpoint_dir.glob("*.pt") if likely_controller_checkpoint_path(path)
                )
            except OSError:
                continue
    if not candidates:
        raise FileNotFoundError(f"No checkpoints found under {run_root}")
    for checkpoint in sorted(candidates, key=checkpoint_sort_key, reverse=True):
        if filter_text and filter_text not in str(checkpoint).lower():
            continue
        if is_current_controller_checkpoint_path(checkpoint):
            return checkpoint.resolve()
    raise FileNotFoundError(f"No current IK controller checkpoints found under {run_root}")


def infer_npz_path(ckpt: dict, checkpoint: Path) -> Path:
    metadata = ckpt.get("metadata", {})
    source_paths = metadata.get("source_npz_paths", [])
    if not source_paths:
        source_paths = metadata.get("npz_paths", [])
    if source_paths:
        return resolve_path(str(source_paths[0]))
    npz_folder = metadata.get("npz_folder")
    if npz_folder:
        folder = resolve_path(str(npz_folder))
        npz_files = sorted(folder.glob("*.npz"))
        if npz_files:
            return npz_files[0].resolve()
    raise ValueError(
        "No --npz-path was provided and the checkpoint does not record a usable source NPZ "
        f"({checkpoint})"
    )


def infer_cyclic_from_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    stem = path.stem.lower()
    if "loop" in stem or "animations_omni" in text:
        return True
    if "transition" in text or "turn" in stem or "reface" in stem or "diamond" in stem:
        return False
    return False


def infer_npz_cyclic_flag(ckpt: dict, npz: Path) -> bool | None:
    metadata = ckpt.get("metadata", {})
    npz_resolved = npz.resolve()
    for item in metadata.get("npz_folders", []):
        if not isinstance(item, dict):
            continue
        folder_text = item.get("path")
        if not folder_text:
            continue
        try:
            folder = resolve_path(str(folder_text))
        except Exception:
            continue
        if npz_resolved.parent == folder:
            return bool(item.get("cyclic", False))
    for path_text in metadata.get("npz_paths", []):
        try:
            if resolve_path(str(path_text)) == npz_resolved:
                # The current IK controller trainer records one-off --npz
                # paths as cyclic.
                if ckpt_runtime.is_current_ik_controller_checkpoint(ckpt):
                    return True
        except Exception:
            continue
    return infer_cyclic_from_path(npz_resolved)


def apply_config_dict(cfg: tl.TrainConfig, values: dict) -> None:
    valid = {field.name for field in fields(tl.TrainConfig)}
    for key, value in values.items():
        if key not in valid:
            continue
        current = getattr(cfg, key)
        if isinstance(current, tuple) and isinstance(value, list):
            value = tuple(value)
        setattr(cfg, key, value)


def load_model(checkpoint: dict, clip: tl.MotionClip, cfg: tl.TrainConfig, device: torch.device) -> tl.MLPController:
    input_dim, output_dim = tl.make_batch_dims(clip, cfg)
    model = tl.MLPController(input_dim, tl.controller_output_dim(clip, cfg), cfg).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model


def is_current_ik_controller_checkpoint(checkpoint: dict) -> bool:
    return ckpt_runtime.is_current_ik_controller_checkpoint(checkpoint)


def checkpoint_output_contract(checkpoint: dict) -> tuple[str, str]:
    policy = ckpt_runtime.checkpoint_policy(checkpoint)
    root = tl.normalized_output_reference_root(policy.get("output_reference_root", tl.OUTPUT_REFERENCE_ROOT))
    prediction = tl.normalized_output_prediction_mode(ckpt_runtime.checkpoint_output_prediction_mode(checkpoint))
    return root, prediction


def apply_simple_controller_policy(checkpoint: dict) -> None:
    simple_ctl.FAKE_GRAVITY_ENABLED = float(simple_ctl.DEFAULT_FAKE_GRAVITY_ENABLED)
    simple_ctl.FAKE_GRAVITY_MPS2 = float(simple_ctl.DEFAULT_FAKE_GRAVITY_MPS2)
    simple_ctl.FAKE_GRAVITY_USES_HEIGHT_GATE = bool(simple_ctl.DEFAULT_FAKE_GRAVITY_USES_HEIGHT_GATE)
    simple_ctl.apply_foot_roll_runtime_policy_from_checkpoint(checkpoint)
    metadata = checkpoint.get("metadata", {}) if isinstance(checkpoint, dict) else {}
    policy = metadata.get("policy", {}) if isinstance(metadata, dict) else {}
    fake_policy = policy.get("fake_gravity", {}) if isinstance(policy, dict) else {}
    if isinstance(fake_policy, dict):
        def _as_fake_weight(raw: object) -> float:
            try:
                return min(1.0, max(0.0, float(raw)))
            except (TypeError, ValueError):
                return float(simple_ctl.DEFAULT_FAKE_GRAVITY_ENABLED)
        if "strength" in fake_policy:
            simple_ctl.FAKE_GRAVITY_ENABLED = _as_fake_weight(fake_policy["strength"])
        elif "enabled" in fake_policy:
            simple_ctl.FAKE_GRAVITY_ENABLED = _as_fake_weight(fake_policy["enabled"])
        if "gravity_mps2" in fake_policy:
            simple_ctl.FAKE_GRAVITY_MPS2 = max(0.0, float(fake_policy["gravity_mps2"]))
        if "uses_height_gate" in fake_policy:
            simple_ctl.FAKE_GRAVITY_USES_HEIGHT_GATE = bool(fake_policy["uses_height_gate"])
    if isinstance(policy, dict) and "ae_scores_ignore_foot_vertical_location" in policy:
        simple_ctl.AE_IGNORE_FOOT_VERTICAL_LOCATION = bool(policy["ae_scores_ignore_foot_vertical_location"])


@contextmanager
def use_checkpoint_output_contract(checkpoint: dict):
    previous_root = tl.OUTPUT_REFERENCE_ROOT
    previous_prediction = tl.OUTPUT_PREDICTION_MODE
    root, prediction = checkpoint_output_contract(checkpoint)
    tl.OUTPUT_REFERENCE_ROOT = root
    tl.OUTPUT_PREDICTION_MODE = prediction
    try:
        yield root, prediction
    finally:
        tl.OUTPUT_REFERENCE_ROOT = previous_root
        tl.OUTPUT_PREDICTION_MODE = previous_prediction


@torch.no_grad()
def ae_reconstruct_output_rows(
    ae: torch.nn.Module,
    mean: torch.Tensor,
    std: torch.Tensor,
    store: simple_ctl.SimpleClipStore,
    controller_input: torch.Tensor,
    predicted_output: torch.Tensor,
    context: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    feature, frames, input_dim, output_dim = simple_ctl.ae_feature_rows(mean, controller_input, predicted_output, context)
    model_feature = simple_ctl.ae_model_feature(ae, feature)
    x = (model_feature - mean) / std
    recon = ae(x)
    base_dim = input_dim + output_dim
    output_start = (frames - 1) * base_dim + input_dim
    output_end = output_start + output_dim
    if simple_ctl.AE_SCORE_OUTPUT_ONLY:
        score = (recon[:, output_start:output_end] - x[:, output_start:output_end]).square().mean(dim=-1)
    else:
        score = (recon - x).square().mean(dim=-1)
    recon_feature = recon * std + mean
    schema = getattr(ae, "_simple_ae_schema", {})
    if isinstance(schema, dict) and str(schema.get("ae_feature_mode", "pose")).strip().lower() == "velocity_current_root":
        pose_dim = int(schema.get("pose_dim", output_dim))
        scale = max(float(schema.get("pose_delta_scale_final", 1.0)), 1e-8)
        cur_start = (frames - 1) * base_dim
        comparable = min(pose_dim, output_dim)
        recon_output = predicted_output.clone()
        recon_output[:, :comparable] = (
            feature[:, cur_start : cur_start + comparable]
            + recon_feature[:, output_start : output_start + comparable] * scale
        )
        if output_dim > comparable:
            recon_output[:, comparable:] = recon_feature[:, output_start + comparable : output_end]
    else:
        recon_output = recon_feature[:, output_start:output_end]
    return simple_ctl.clean_output_vector(recon_output, store), score


@torch.no_grad()
def rollout_ik_controller_model(
    model: torch.nn.Module,
    clip: tl.MotionClip,
    cfg: tl.TrainConfig,
    device: torch.device,
    max_frames: int | None,
    ae_bundle: tuple[torch.nn.Module, torch.Tensor, torch.Tensor] | None = None,
    ae_recon_passes: int = 1,
) -> tuple[np.ndarray, ...]:
    frame_count = clip.T if max_frames is None else min(clip.T, max(3, max_frames))
    ae_recon_passes = max(1, int(ae_recon_passes))
    frame_idx = torch.arange(frame_count, dtype=torch.long, device=device)
    gt_pos_t, gt_rot_t = tl.global_from_clip(clip, frame_idx, cfg, device)
    pred_ar_pos_t = torch.empty_like(gt_pos_t)
    pred_one_step_pos_t = torch.empty_like(gt_pos_t)
    pred_ar_rot_t = torch.empty_like(gt_rot_t)
    pred_one_step_rot_t = torch.empty_like(gt_rot_t)
    pred_ar_ae_pos_t = torch.empty_like(gt_pos_t) if ae_bundle is not None else None
    pred_one_step_ae_pos_t = torch.empty_like(gt_pos_t) if ae_bundle is not None else None
    pred_ar_ae_rot_t = torch.empty_like(gt_rot_t) if ae_bundle is not None else None
    pred_one_step_ae_rot_t = torch.empty_like(gt_rot_t) if ae_bundle is not None else None
    gt_ae_pos_t = torch.empty_like(gt_pos_t) if ae_bundle is not None else None
    gt_ae_rot_t = torch.empty_like(gt_rot_t) if ae_bundle is not None else None
    ae_score_ar_t = torch.full((frame_count,), float("nan"), dtype=torch.float32, device=device) if ae_bundle is not None else None
    ae_score_one_step_t = (
        torch.full((frame_count,), float("nan"), dtype=torch.float32, device=device) if ae_bundle is not None else None
    )
    ae_score_gt_t = (
        torch.full((frame_count,), float("nan"), dtype=torch.float32, device=device) if ae_bundle is not None else None
    )
    pred_ar_ae_pass_pos_t = (
        torch.empty((ae_recon_passes, *gt_pos_t.shape), dtype=gt_pos_t.dtype, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    pred_ar_ae_pass_rot_t = (
        torch.empty((ae_recon_passes, *gt_rot_t.shape), dtype=gt_rot_t.dtype, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    pred_one_step_ae_pass_pos_t = (
        torch.empty((ae_recon_passes, *gt_pos_t.shape), dtype=gt_pos_t.dtype, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    pred_one_step_ae_pass_rot_t = (
        torch.empty((ae_recon_passes, *gt_rot_t.shape), dtype=gt_rot_t.dtype, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    ae_score_ar_pass_t = (
        torch.full((ae_recon_passes, frame_count), float("nan"), dtype=torch.float32, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    ae_score_one_step_pass_t = (
        torch.full((ae_recon_passes, frame_count), float("nan"), dtype=torch.float32, device=device)
        if ae_bundle is not None and ae_recon_passes > 1
        else None
    )
    pred_ar_pos_t[:2] = gt_pos_t[:2]
    pred_one_step_pos_t[:2] = gt_pos_t[:2]
    pred_ar_rot_t[:2] = gt_rot_t[:2]
    pred_one_step_rot_t[:2] = gt_rot_t[:2]
    if ae_bundle is not None:
        assert pred_ar_ae_pos_t is not None
        assert pred_one_step_ae_pos_t is not None
        assert pred_ar_ae_rot_t is not None
        assert pred_one_step_ae_rot_t is not None
        assert gt_ae_pos_t is not None
        assert gt_ae_rot_t is not None
        pred_ar_ae_pos_t[:2] = gt_pos_t[:2]
        pred_one_step_ae_pos_t[:2] = gt_pos_t[:2]
        pred_ar_ae_rot_t[:2] = gt_rot_t[:2]
        pred_one_step_ae_rot_t[:2] = gt_rot_t[:2]
        gt_ae_pos_t[:2] = gt_pos_t[:2]
        gt_ae_rot_t[:2] = gt_rot_t[:2]
        if pred_ar_ae_pass_pos_t is not None:
            pred_ar_ae_pass_pos_t[:, :2] = gt_pos_t[:2]
            pred_ar_ae_pass_rot_t[:, :2] = gt_rot_t[:2]
            pred_one_step_ae_pass_pos_t[:, :2] = gt_pos_t[:2]
            pred_one_step_ae_pass_rot_t[:, :2] = gt_rot_t[:2]

    store = simple_ctl.SimpleClipStore([clip], cfg, device)
    clip_ids = torch.zeros(1, dtype=torch.long, device=device)
    ae = mean = std = None
    ae_frames = 1
    if ae_bundle is not None:
        ae, mean, std = ae_bundle
        input_dim, output_dim = tl.make_batch_dims(clip, cfg)
        ae_frames = simple_ctl.ae_window_frames_from_dims(mean, input_dim, output_dim)

    cur_idx = torch.tensor([1], dtype=torch.long, device=device)
    prev_vec, prev_pelvis, prev_payload = simple_ctl.target_state(store, clip_ids, cur_idx - 1)
    cur_vec, cur_pelvis, cur_payload = simple_ctl.target_state(store, clip_ids, cur_idx)
    ar_ae_history: list[torch.Tensor] = []

    for target in range(2, frame_count):
        target_idx = torch.tensor([target], dtype=torch.long, device=device)

        one_cur_idx = torch.tensor([target - 1], dtype=torch.long, device=device)
        one_root_pos, one_root_rot, _one_yaw, _one_heading = store.root_state(clip_ids, one_cur_idx)
        one_prev_vec, one_prev_pelvis, one_prev_payload = simple_ctl.target_state(store, clip_ids, one_cur_idx - 1)
        one_cur_vec, one_cur_pelvis, one_cur_payload = simple_ctl.target_state(store, clip_ids, one_cur_idx)
        one_inp = simple_ctl.build_controller_input(
            store,
            clip_ids,
            one_cur_idx,
            one_prev_vec,
            one_cur_vec,
            one_prev_pelvis,
            one_cur_pelvis,
            one_prev_payload,
            one_cur_payload,
        )
        one_raw = simple_ctl.model_forward(model, one_inp, one_cur_vec, store)
        one_vec = simple_ctl.clean_output_vector(one_raw, store, one_cur_vec, one_prev_vec)
        one_pose, _ = tl.output_to_pose(one_vec, clip)
        one_decode_root_pos, one_decode_root_rot = simple_ctl.transition_output_root_state(store, clip_ids, one_cur_idx)
        one_global_pos, one_global_rot, _ = tl.fk_from_pose(
            clip, one_decode_root_pos, one_decode_root_rot, one_pose, device
        )
        pred_one_step_pos_t[target] = one_global_pos[0]
        pred_one_step_rot_t[target] = one_global_rot[0]
        if ae_bundle is not None:
            assert ae is not None and mean is not None and std is not None
            assert pred_one_step_ae_pos_t is not None
            assert pred_one_step_ae_rot_t is not None
            assert ae_score_one_step_t is not None
            one_context = None
            if ae_frames > 1 and int(one_cur_idx.item()) >= ae_frames:
                one_context = simple_ctl.initial_ae_context(store, clip_ids, one_cur_idx, ae_frames)
            if ae_frames <= 1 or one_context is not None:
                one_candidate = one_vec
                for pass_i in range(ae_recon_passes):
                    one_candidate, one_score = ae_reconstruct_output_rows(ae, mean, std, store, one_inp, one_candidate, one_context)
                    one_recon_pose, _ = tl.output_to_pose(one_candidate, clip)
                    one_recon_global_pos, one_recon_global_rot, _ = tl.fk_from_pose(
                        clip, one_decode_root_pos, one_decode_root_rot, one_recon_pose, device
                    )
                    if pass_i == 0:
                        pred_one_step_ae_pos_t[target] = one_recon_global_pos[0]
                        pred_one_step_ae_rot_t[target] = one_recon_global_rot[0]
                        ae_score_one_step_t[target] = one_score[0]
                    if pred_one_step_ae_pass_pos_t is not None:
                        pred_one_step_ae_pass_pos_t[pass_i, target] = one_recon_global_pos[0]
                        pred_one_step_ae_pass_rot_t[pass_i, target] = one_recon_global_rot[0]
                        ae_score_one_step_pass_t[pass_i, target] = one_score[0]
            else:
                pred_one_step_ae_pos_t[target] = one_global_pos[0]
                pred_one_step_ae_rot_t[target] = one_global_rot[0]
                if pred_one_step_ae_pass_pos_t is not None:
                    pred_one_step_ae_pass_pos_t[:, target] = one_global_pos[0]
                    pred_one_step_ae_pass_rot_t[:, target] = one_global_rot[0]

            assert gt_ae_pos_t is not None
            assert gt_ae_rot_t is not None
            assert ae_score_gt_t is not None
            gt_transition_vec = simple_ctl.transition_target_output(store, clip_ids, one_cur_idx)
            if ae_frames <= 1 or one_context is not None:
                gt_recon_vec, gt_score = ae_reconstruct_output_rows(ae, mean, std, store, one_inp, gt_transition_vec, one_context)
                gt_recon_pose, _ = tl.output_to_pose(gt_recon_vec, clip)
                gt_recon_global_pos, gt_recon_global_rot, _ = tl.fk_from_pose(
                    clip, one_decode_root_pos, one_decode_root_rot, gt_recon_pose, device
                )
                gt_ae_pos_t[target] = gt_recon_global_pos[0]
                gt_ae_rot_t[target] = gt_recon_global_rot[0]
                ae_score_gt_t[target] = gt_score[0]
            else:
                gt_ae_pos_t[target] = gt_pos_t[target]
                gt_ae_rot_t[target] = gt_rot_t[target]

        inp = simple_ctl.build_controller_input(
            store,
            clip_ids,
            cur_idx,
            prev_vec,
            cur_vec,
            prev_pelvis,
            cur_pelvis,
            prev_payload,
            cur_payload,
        )
        pred_vec = simple_ctl.model_forward(model, inp, cur_vec, store, prev_vec)
        pred_pose, _ = tl.output_to_pose(pred_vec, clip)
        root_pos, root_rot = simple_ctl.transition_output_root_state(store, clip_ids, cur_idx)
        global_pos, global_rot, _ = tl.fk_from_pose(clip, root_pos, root_rot, pred_pose, device)
        pred_ar_pos_t[target] = global_pos[0]
        pred_ar_rot_t[target] = global_rot[0]
        if ae_bundle is not None:
            assert ae is not None and mean is not None and std is not None
            assert pred_ar_ae_pos_t is not None
            assert pred_ar_ae_rot_t is not None
            assert ae_score_ar_t is not None
            ar_context = None
            if ae_frames > 1 and len(ar_ae_history) >= ae_frames - 1:
                ar_context = torch.stack(ar_ae_history[-(ae_frames - 1) :], dim=1)
            if ae_frames <= 1 or ar_context is not None:
                ar_candidate = pred_vec
                for pass_i in range(ae_recon_passes):
                    ar_candidate, score = ae_reconstruct_output_rows(ae, mean, std, store, inp, ar_candidate, ar_context)
                    recon_pose, _ = tl.output_to_pose(ar_candidate, clip)
                    recon_global_pos, recon_global_rot, _ = tl.fk_from_pose(clip, root_pos, root_rot, recon_pose, device)
                    if pass_i == 0:
                        pred_ar_ae_pos_t[target] = recon_global_pos[0]
                        pred_ar_ae_rot_t[target] = recon_global_rot[0]
                        ae_score_ar_t[target] = score[0]
                    if pred_ar_ae_pass_pos_t is not None:
                        pred_ar_ae_pass_pos_t[pass_i, target] = recon_global_pos[0]
                        pred_ar_ae_pass_rot_t[pass_i, target] = recon_global_rot[0]
                        ae_score_ar_pass_t[pass_i, target] = score[0]
            else:
                pred_ar_ae_pos_t[target] = global_pos[0]
                pred_ar_ae_rot_t[target] = global_rot[0]
                if pred_ar_ae_pass_pos_t is not None:
                    pred_ar_ae_pass_pos_t[:, target] = global_pos[0]
                    pred_ar_ae_pass_rot_t[:, target] = global_rot[0]
            ar_ae_history.append(torch.cat((inp, pred_vec), dim=-1).detach())

        prev_vec = cur_vec
        prev_pelvis = cur_pelvis
        prev_payload = cur_payload
        cur_vec, cur_pelvis, cur_payload = simple_ctl.advance_transition_state(store, clip_ids, cur_idx, pred_vec)
        cur_idx = target_idx

    error_indices = torch.tensor(visible_error_bone_indices(clip), dtype=torch.long, device=device)
    gt_error_pos = gt_pos_t.index_select(1, error_indices)
    error_ar = (
        (pred_ar_pos_t.index_select(1, error_indices) - gt_error_pos)
        .norm(dim=-1)
        .mean(dim=-1)
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    error_one_step = (
        (pred_one_step_pos_t.index_select(1, error_indices) - gt_error_pos)
        .norm(dim=-1)
        .mean(dim=-1)
        .detach()
        .cpu()
        .numpy()
        .astype(np.float32)
    )
    result = (
        gt_pos_t.detach().cpu().numpy().astype(np.float32),
        gt_rot_t.detach().cpu().numpy().astype(np.float32),
        pred_one_step_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_one_step_rot_t.detach().cpu().numpy().astype(np.float32),
        error_one_step,
        pred_ar_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_ar_rot_t.detach().cpu().numpy().astype(np.float32),
        error_ar,
    )
    if ae_bundle is None:
        return result
    assert pred_one_step_ae_pos_t is not None
    assert pred_one_step_ae_rot_t is not None
    assert pred_ar_ae_pos_t is not None
    assert pred_ar_ae_rot_t is not None
    assert gt_ae_pos_t is not None
    assert gt_ae_rot_t is not None
    assert ae_score_one_step_t is not None
    assert ae_score_ar_t is not None
    assert ae_score_gt_t is not None
    ae_result = (
        *result,
        pred_one_step_ae_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_one_step_ae_rot_t.detach().cpu().numpy().astype(np.float32),
        pred_ar_ae_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_ar_ae_rot_t.detach().cpu().numpy().astype(np.float32),
        ae_score_one_step_t.detach().cpu().numpy().astype(np.float32),
        ae_score_ar_t.detach().cpu().numpy().astype(np.float32),
        gt_ae_pos_t.detach().cpu().numpy().astype(np.float32),
        gt_ae_rot_t.detach().cpu().numpy().astype(np.float32),
        ae_score_gt_t.detach().cpu().numpy().astype(np.float32),
    )
    if pred_ar_ae_pass_pos_t is None:
        return ae_result
    assert pred_ar_ae_pass_rot_t is not None
    assert pred_one_step_ae_pass_pos_t is not None
    assert pred_one_step_ae_pass_rot_t is not None
    assert ae_score_ar_pass_t is not None
    assert ae_score_one_step_pass_t is not None
    return (
        *ae_result,
        pred_one_step_ae_pass_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_one_step_ae_pass_rot_t.detach().cpu().numpy().astype(np.float32),
        pred_ar_ae_pass_pos_t.detach().cpu().numpy().astype(np.float32),
        pred_ar_ae_pass_rot_t.detach().cpu().numpy().astype(np.float32),
        ae_score_one_step_pass_t.detach().cpu().numpy().astype(np.float32),
        ae_score_ar_pass_t.detach().cpu().numpy().astype(np.float32),
    )


LOWER_RENDER_BONE_NAMES = {"pelvis", "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r"}


def visible_error_bone_indices(clip: tl.MotionClip) -> list[int]:
    body_mode = tl.normalized_body_mode(getattr(clip, "body_mode", tl.BODY_MODE_LOWER))
    if not tl.body_mode_render_lower_only(body_mode):
        return list(range(len(clip.body_names)))
    selected = [i for i, name in enumerate(clip.body_names) if name in LOWER_RENDER_BONE_NAMES]
    return selected or list(range(len(clip.body_names)))


def pinned_sides_from_motion(clip: tl.MotionClip, positions: np.ndarray, rotations: np.ndarray) -> np.ndarray:
    frame_count = int(positions.shape[0])
    if frame_count < 2:
        return np.zeros((frame_count,), dtype=np.int8)
    order = tuple(int(clip.body_names.index(name)) for name in ("foot_l", "ball_l", "foot_r", "ball_r"))
    pos_t = torch.from_numpy(np.ascontiguousarray(positions[:, order], dtype=np.float32))
    rot_t = torch.from_numpy(np.ascontiguousarray(rotations[:, order], dtype=np.float32))
    _linear, _angular, planted = env.compact_slide_yaw_selected_with_planted(
        pos_t[:-1],
        rot_t[:-1],
        pos_t[1:],
        rot_t[1:],
        clip.fps,
    )
    sides = planted.detach().cpu().numpy().astype(np.int8)
    return np.concatenate((sides, sides[-1:]), axis=0)


def make_payload(
    clip: tl.MotionClip,
    gt_pos: np.ndarray,
    gt_rot: np.ndarray,
    pred_one_step_pos: np.ndarray,
    pred_one_step_rot: np.ndarray,
    error_one_step: np.ndarray,
    pred_ar_pos: np.ndarray,
    pred_ar_rot: np.ndarray,
    error_ar: np.ndarray,
    pred_one_step_ae_recon_pos: np.ndarray | None = None,
    pred_one_step_ae_recon_rot: np.ndarray | None = None,
    pred_ar_ae_recon_pos: np.ndarray | None = None,
    pred_ar_ae_recon_rot: np.ndarray | None = None,
    ae_score_one_step: np.ndarray | None = None,
    ae_score_ar: np.ndarray | None = None,
    gt_ae_recon_pos: np.ndarray | None = None,
    gt_ae_recon_rot: np.ndarray | None = None,
    ae_score_gt: np.ndarray | None = None,
    pred_one_step_ae_pass_pos: np.ndarray | None = None,
    pred_one_step_ae_pass_rot: np.ndarray | None = None,
    pred_ar_ae_pass_pos: np.ndarray | None = None,
    pred_ar_ae_pass_rot: np.ndarray | None = None,
    ae_score_one_step_pass: np.ndarray | None = None,
    ae_score_ar_pass: np.ndarray | None = None,
) -> dict:
    body_mode = tl.normalized_body_mode(getattr(clip, "body_mode", tl.BODY_MODE_LOWER))
    render_lower_only = bool(tl.body_mode_render_lower_only(body_mode))
    bounds_indices = np.arange(gt_pos.shape[1])
    if render_lower_only:
        selected = visible_error_bone_indices(clip)
        if selected:
            bounds_indices = np.asarray(selected, dtype=np.int64)
    bounds_parts = [gt_pos[:, bounds_indices], pred_one_step_pos[:, bounds_indices], pred_ar_pos[:, bounds_indices]]
    if pred_one_step_ae_recon_pos is not None:
        bounds_parts.append(pred_one_step_ae_recon_pos[:, bounds_indices])
    if pred_ar_ae_recon_pos is not None:
        bounds_parts.append(pred_ar_ae_recon_pos[:, bounds_indices])
    if gt_ae_recon_pos is not None:
        bounds_parts.append(gt_ae_recon_pos[:, bounds_indices])
    both = np.concatenate(tuple(bounds_parts), axis=1)
    bounds_min = both.reshape(-1, 3).min(axis=0)
    bounds_max = both.reshape(-1, 3).max(axis=0)
    pinned_gt = pinned_sides_from_motion(clip, gt_pos, gt_rot)
    pinned_one_step = pinned_sides_from_motion(clip, pred_one_step_pos, pred_one_step_rot)
    pinned_ar = pinned_sides_from_motion(clip, pred_ar_pos, pred_ar_rot)
    payload = {
        "title": "",
        "frame_count": int(gt_pos.shape[0]),
        "bone_count": int(gt_pos.shape[1]),
        "fps": float(clip.fps),
        "bone_names": clip.body_names,
        "parents": clip.parents_body.cpu().numpy().astype(int).tolist(),
        "root_index": int(clip.pelvis),
        "body_mode": body_mode,
        "render_lower_only": render_lower_only,
        "initial_frame": int(min(max(2, gt_pos.shape[0] // 2), gt_pos.shape[0] - 1)),
        "bounds": {"min": bounds_min.tolist(), "max": bounds_max.tolist()},
        "gt_b64": base64.b64encode(np.ascontiguousarray(gt_pos, dtype=np.float32).tobytes()).decode("ascii"),
        "gt_basis_b64": base64.b64encode(np.ascontiguousarray(gt_rot, dtype=np.float32).tobytes()).decode("ascii"),
        "pred_one_step_b64": base64.b64encode(np.ascontiguousarray(pred_one_step_pos, dtype=np.float32).tobytes()).decode("ascii"),
        "pred_one_step_basis_b64": base64.b64encode(np.ascontiguousarray(pred_one_step_rot, dtype=np.float32).tobytes()).decode("ascii"),
        "pred_ar_b64": base64.b64encode(np.ascontiguousarray(pred_ar_pos, dtype=np.float32).tobytes()).decode("ascii"),
        "pred_ar_basis_b64": base64.b64encode(np.ascontiguousarray(pred_ar_rot, dtype=np.float32).tobytes()).decode("ascii"),
        "err_one_step_b64": base64.b64encode(np.ascontiguousarray(error_one_step, dtype=np.float32).tobytes()).decode("ascii"),
        "err_ar_b64": base64.b64encode(np.ascontiguousarray(error_ar, dtype=np.float32).tobytes()).decode("ascii"),
        "pinned_gt_b64": base64.b64encode(np.ascontiguousarray(pinned_gt, dtype=np.int8).tobytes()).decode("ascii"),
        "pinned_one_step_b64": base64.b64encode(np.ascontiguousarray(pinned_one_step, dtype=np.int8).tobytes()).decode("ascii"),
        "pinned_ar_b64": base64.b64encode(np.ascontiguousarray(pinned_ar, dtype=np.int8).tobytes()).decode("ascii"),
    }
    if (
        pred_one_step_ae_recon_pos is not None
        and pred_one_step_ae_recon_rot is not None
        and pred_ar_ae_recon_pos is not None
        and pred_ar_ae_recon_rot is not None
        and ae_score_one_step is not None
        and ae_score_ar is not None
    ):
        payload.update(
            {
                "ae_recon_one_step_b64": base64.b64encode(
                    np.ascontiguousarray(pred_one_step_ae_recon_pos, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_one_step_basis_b64": base64.b64encode(
                    np.ascontiguousarray(pred_one_step_ae_recon_rot, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_ar_b64": base64.b64encode(
                    np.ascontiguousarray(pred_ar_ae_recon_pos, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_ar_basis_b64": base64.b64encode(
                    np.ascontiguousarray(pred_ar_ae_recon_rot, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_score_one_step_b64": base64.b64encode(
                    np.ascontiguousarray(ae_score_one_step, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_score_ar_b64": base64.b64encode(
                    np.ascontiguousarray(ae_score_ar, dtype=np.float32).tobytes()
                ).decode("ascii"),
            }
        )
    if gt_ae_recon_pos is not None and gt_ae_recon_rot is not None and ae_score_gt is not None:
        payload.update(
            {
                "gt_ae_recon_b64": base64.b64encode(
                    np.ascontiguousarray(gt_ae_recon_pos, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "gt_ae_recon_basis_b64": base64.b64encode(
                    np.ascontiguousarray(gt_ae_recon_rot, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "gt_ae_score_b64": base64.b64encode(
                    np.ascontiguousarray(ae_score_gt, dtype=np.float32).tobytes()
                ).decode("ascii"),
            }
        )
    if (
        pred_one_step_ae_pass_pos is not None
        and pred_one_step_ae_pass_rot is not None
        and pred_ar_ae_pass_pos is not None
        and pred_ar_ae_pass_rot is not None
        and ae_score_one_step_pass is not None
        and ae_score_ar_pass is not None
    ):
        payload.update(
            {
                "ae_recon_pass_count": int(pred_ar_ae_pass_pos.shape[0]),
                "ae_recon_one_step_passes_b64": base64.b64encode(
                    np.ascontiguousarray(pred_one_step_ae_pass_pos, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_one_step_passes_basis_b64": base64.b64encode(
                    np.ascontiguousarray(pred_one_step_ae_pass_rot, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_ar_passes_b64": base64.b64encode(
                    np.ascontiguousarray(pred_ar_ae_pass_pos, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_recon_ar_passes_basis_b64": base64.b64encode(
                    np.ascontiguousarray(pred_ar_ae_pass_rot, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_score_one_step_passes_b64": base64.b64encode(
                    np.ascontiguousarray(ae_score_one_step_pass, dtype=np.float32).tobytes()
                ).decode("ascii"),
                "ae_score_ar_passes_b64": base64.b64encode(
                    np.ascontiguousarray(ae_score_ar_pass, dtype=np.float32).tobytes()
                ).decode("ascii"),
            }
        )
    return payload


def write_html(
    payload: dict | list[dict],
    output: Path,
    title: str,
    initial_motion_index: int = 0,
    checkpoint_manifest: list[dict[str, object]] | None = None,
    lazy_checkpoint_endpoint: str | None = None,
    lazy_max_frames: int | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payloads = payload if isinstance(payload, list) else [payload]
    manifest_count = len(checkpoint_manifest or [])
    max_index = manifest_count - 1 if manifest_count else len(payloads) - 1
    initial_motion_index = max(0, min(max_index, int(initial_motion_index)))
    html = HTML_TEMPLATE.format(
        title=title,
        last_frame=payloads[0]["frame_count"] - 1,
        fps=f"{payloads[0]['fps']:.0f}",
        bone_count=payloads[0]["bone_count"],
        initial_motion_index=initial_motion_index,
        payload=json.dumps(payloads, separators=(",", ":")),
        checkpoint_manifest=json.dumps(checkpoint_manifest or [], separators=(",", ":")),
        lazy_checkpoint_endpoint=json.dumps(lazy_checkpoint_endpoint),
        lazy_max_frames=json.dumps(lazy_max_frames),
    )
    tmp = output.with_name(f"{output.name}.{os.getpid()}.tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(output)


def checkpoint_display_label(path: Path) -> str:
    try:
        stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        stamp = "unknown time"
    run_name = path.parent.parent.name if path.parent.name == "checkpoints" else path.parent.name
    stem = path.stem
    prefix = f"{run_name}_"
    if stem.startswith(prefix):
        stem = stem[len(prefix) :]
    if stem == "best":
        return f"{stamp}  {run_name}"
    return f"{stamp}  {stem}"


def run_checkpoint_candidates(checkpoint: Path) -> list[Path]:
    checkpoint_dir = checkpoint.parent if checkpoint.parent.name == "checkpoints" else checkpoint.parent / "checkpoints"
    if not checkpoint_dir.exists():
        return [checkpoint]
    candidates = [
        path.resolve()
        for path in checkpoint_dir.glob("*.pt")
        if likely_controller_checkpoint_path(path) and is_current_controller_checkpoint_path(path)
    ]
    if checkpoint.resolve() not in candidates:
        candidates.append(checkpoint.resolve())
    return sorted(dict.fromkeys(candidates), key=checkpoint_sort_key)


def runs_best_checkpoint_candidates(checkpoint: Path, npz: Path | None = None) -> list[Path]:
    run_root = PROJECT_ROOT / "training" / "runs"
    candidates: list[Path] = []
    for path in run_root.glob("*/checkpoints/*_best.pt"):
        resolved = path.resolve()
        if not likely_controller_checkpoint_path(resolved):
            continue
        try:
            ckpt = torch.load(resolved, map_location="cpu", weights_only=False)
        except Exception:
            continue
        if not ckpt_runtime.is_current_ik_controller_checkpoint(ckpt):
            continue
        if npz is not None:
            try:
                if infer_npz_path(ckpt, resolved).resolve() != npz.resolve():
                    continue
            except Exception:
                continue
        candidates.append(resolved)
    if checkpoint.name.lower().endswith("_best.pt") and checkpoint.resolve() not in candidates:
        candidates.append(checkpoint.resolve())
    return sorted(dict.fromkeys(candidates), key=checkpoint_sort_key, reverse=True)


def initial_checkpoint_index(candidates: list[Path], checkpoint: Path) -> int:
    checkpoint = checkpoint.resolve()
    for index, candidate in enumerate(candidates):
        if candidate == checkpoint:
            return index
    current_run = checkpoint.parent.parent if checkpoint.parent.name == "checkpoints" else checkpoint.parent
    for index, candidate in enumerate(candidates):
        run_dir = candidate.parent.parent if candidate.parent.name == "checkpoints" else candidate.parent
        if run_dir == current_run:
            return index
    return max(0, len(candidates) - 1)


def build_checkpoint_payload(
    *,
    checkpoint: Path,
    npz: Path | None,
    device: torch.device,
    max_frames: int | None,
    include_ae: bool = True,
    ae_checkpoint: Path | None = None,
    ae_recon_passes: int = 1,
) -> tuple[dict[str, object], dict[str, object]]:
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
    ckpt_runtime.require_current_ik_controller_checkpoint(ckpt, checkpoint)
    with use_checkpoint_output_contract(ckpt) as (output_root, prediction_mode):
        apply_simple_controller_policy(ckpt)
        resolved_npz = npz or infer_npz_path(ckpt, checkpoint)
        cfg = tl.TrainConfig()
        apply_config_dict(cfg, ckpt.get("config", {}))
        cfg.device = str(device)
        cfg.use_torch_compile = False

        clip = tl.MotionClip(resolved_npz, cfg, cyclic_animation=infer_npz_cyclic_flag(ckpt, resolved_npz))
        model = load_model(ckpt, clip, cfg, device)
        ae_bundle = None
        ae_path_text = str(ae_checkpoint) if ae_checkpoint is not None else ckpt.get("metadata", {}).get("simple_ae_checkpoint") if include_ae else None
        if ae_path_text:
            ae_bundle = simple_ctl.load_simple_ae(resolve_path(str(ae_path_text)), device, cfg.body_mode)[:3]
        rollout = rollout_ik_controller_model(model, clip, cfg, device, max_frames, ae_bundle, ae_recon_passes=ae_recon_passes)
        gt_pos, gt_rot, pred_one_step_pos, pred_one_step_rot, error_one_step, pred_ar_pos, pred_ar_rot, error_ar = (
            rollout[:8]
        )
        ae_payload = rollout[8:] if len(rollout) > 8 else ()
        payload = make_payload(
            clip,
            gt_pos,
            gt_rot,
            pred_one_step_pos,
            pred_one_step_rot,
            error_one_step,
            pred_ar_pos,
            pred_ar_rot,
            error_ar,
            *ae_payload,
        )
        title = f"{resolved_npz.stem} vs {checkpoint.parent.parent.name}"
        payload["title"] = title
        payload["checkpoint_label"] = checkpoint_display_label(checkpoint)
        payload["checkpoint_path"] = str(checkpoint)
        if ae_path_text:
            payload["ae_checkpoint_path"] = str(resolve_path(str(ae_path_text)))
        payload["output_reference_root"] = output_root
        payload["output_prediction_mode"] = prediction_mode
        info = {
            "checkpoint": checkpoint,
            "npz": resolved_npz,
            "runtime": ckpt_runtime.runtime_name(ckpt),
            "output_reference_root": output_root,
            "output_prediction_mode": prediction_mode,
            "frame_count": int(payload["frame_count"]),
            "bone_count": int(payload["bone_count"]),
            "fps": float(payload["fps"]),
            "one_step_start": float(error_one_step[0]),
            "one_step_end": float(error_one_step[-1]),
            "one_step_avg": float(error_one_step.mean()),
            "one_step_max": float(error_one_step.max()),
            "autoregressive_start": float(error_ar[0]),
            "autoregressive_end": float(error_ar[-1]),
            "autoregressive_avg": float(error_ar.mean()),
            "autoregressive_max": float(error_ar.max()),
        }
        return payload, info


def render_checkpoint_to_html(
    *,
    checkpoint: Path,
    output: Path,
    npz: Path | None = None,
    device: torch.device | None = None,
    max_frames: int | None = None,
    include_run_checkpoints: bool = False,
    include_runs_best_checkpoints: bool = False,
    lazy_checkpoint_endpoint: str | None = None,
    ae_checkpoint: Path | None = None,
    ae_recon_passes: int = 1,
) -> dict[str, object]:
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = checkpoint.resolve()
    if include_runs_best_checkpoints:
        candidates = runs_best_checkpoint_candidates(checkpoint, npz)
        if not candidates:
            candidates = [checkpoint]
        initial_index = initial_checkpoint_index(candidates, checkpoint)
        initial_checkpoint = candidates[initial_index]
        manifest = [
            {
                "label": checkpoint_display_label(candidate),
                "checkpoint_label": checkpoint_display_label(candidate),
                "checkpoint_path": str(candidate),
                "npz_path": str(npz.resolve()) if npz is not None else "",
                "ae_checkpoint_path": str(ae_checkpoint.resolve()) if ae_checkpoint is not None else "",
                "ae_recon_passes": int(max(1, ae_recon_passes)),
            }
            for candidate in candidates
        ]
        payload, info = build_checkpoint_payload(
            checkpoint=initial_checkpoint,
            npz=npz,
            device=device,
            max_frames=max_frames,
            ae_checkpoint=ae_checkpoint,
            ae_recon_passes=ae_recon_passes,
        )
        payload["manifest_index"] = initial_index
        write_html(
            payload,
            output,
            str(payload.get("title", output.stem)),
            initial_index,
            checkpoint_manifest=manifest,
            lazy_checkpoint_endpoint=lazy_checkpoint_endpoint,
            lazy_max_frames=max_frames,
        )
        info["checkpoint_count"] = len(manifest)
        info["lazy_checkpoint_endpoint"] = lazy_checkpoint_endpoint or ""
        return info
    if include_run_checkpoints or include_runs_best_checkpoints:
        payloads: list[dict[str, object]] = []
        infos: list[dict[str, object]] = []
        candidates = run_checkpoint_candidates(checkpoint)
        if not candidates:
            candidates = [checkpoint]
        initial_index = initial_checkpoint_index(candidates, checkpoint)
        for index, candidate in enumerate(candidates):
            payload, info = build_checkpoint_payload(
                checkpoint=candidate,
                npz=npz,
                device=device,
                max_frames=max_frames,
                ae_checkpoint=ae_checkpoint,
                ae_recon_passes=ae_recon_passes,
            )
            payloads.append(payload)
            infos.append(info)
        title = str(payloads[initial_index].get("title", output.stem))
        write_html(payloads, output, title, initial_index)
        info = dict(infos[initial_index])
        info["checkpoint_count"] = len(payloads)
        return info
    payload, info = build_checkpoint_payload(
        checkpoint=checkpoint,
        npz=npz,
        device=device,
        max_frames=max_frames,
        ae_checkpoint=ae_checkpoint,
        ae_recon_passes=ae_recon_passes,
    )
    write_html(payload, output, str(payload.get("title", output.stem)))
    info["checkpoint_count"] = 1
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize autoregressive model rollout against NPZ ground truth.")
    parser.add_argument("--npz-path", default=npz_path)
    parser.add_argument("--checkpoint-path", default=checkpoint_path)
    parser.add_argument("--ae-checkpoint-path", default="", help="Override the checkpoint used by the yellow AE reconstruction overlay.")
    parser.add_argument("--ae-recon-passes", type=int, default=1, help="Number of recurrent AE passes to embed for the yellow overlay.")
    parser.add_argument("--output-path", default=output_path)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument(
        "--include-run-checkpoints",
        action="store_true",
        help="Embed chronological non-init checkpoints from the same run so the HTML title can switch between them.",
    )
    parser.add_argument(
        "--include-runs-best-checkpoints",
        action="store_true",
        help="Embed newest-first current-controller *_best.pt checkpoints from training/runs that match the selected NPZ.",
    )
    parser.add_argument(
        "--lazy-checkpoint-endpoint",
        default="http://127.0.0.1:8775/payload",
        help="Local endpoint used by --include-runs-best-checkpoints to fetch checkpoint payloads on click.",
    )
    args = parser.parse_args()

    checkpoint = resolve_optional_path(args.checkpoint_path) or find_latest_checkpoint()
    output = resolve_path(args.output_path)
    device = torch.device(args.device)

    info = render_checkpoint_to_html(
        checkpoint=checkpoint,
        output=output,
        npz=resolve_optional_path(args.npz_path),
        device=device,
        max_frames=args.max_frames,
        include_run_checkpoints=args.include_run_checkpoints,
        include_runs_best_checkpoints=args.include_runs_best_checkpoints,
        lazy_checkpoint_endpoint=args.lazy_checkpoint_endpoint,
        ae_checkpoint=resolve_optional_path(args.ae_checkpoint_path),
        ae_recon_passes=max(1, int(args.ae_recon_passes)),
    )

    print(f"wrote {output}")
    print(f"checkpoint {info['checkpoint']}")
    print(f"checkpoint_count {info.get('checkpoint_count', 1)}")
    if info.get("lazy_checkpoint_endpoint"):
        print(f"lazy_checkpoint_endpoint {info['lazy_checkpoint_endpoint']}")
    print(f"npz {info['npz']}")
    print(f"runtime {info['runtime']}")
    print(f"output_reference_root {info['output_reference_root']}")
    print(f"output_prediction_mode {info['output_prediction_mode']}")
    print(f"frames {info['frame_count']} bones {info['bone_count']} fps {info['fps']:.0f}")
    print(f"one_step_mean_joint_error_start {info['one_step_start']:.6f}")
    print(f"one_step_mean_joint_error_end {info['one_step_end']:.6f}")
    print(f"one_step_mean_joint_error_avg {info['one_step_avg']:.6f}")
    print(f"one_step_mean_joint_error_max {info['one_step_max']:.6f}")
    print(f"autoregressive_mean_joint_error_start {info['autoregressive_start']:.6f}")
    print(f"autoregressive_mean_joint_error_end {info['autoregressive_end']:.6f}")
    print(f"autoregressive_mean_joint_error_avg {info['autoregressive_avg']:.6f}")
    print(f"autoregressive_mean_joint_error_max {info['autoregressive_max']:.6f}")


if __name__ == "__main__":
    main()
