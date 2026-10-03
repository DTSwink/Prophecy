"use strict";

class WebGLMotionRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: true,
      depth: true,
      premultipliedAlpha: false,
    }) || canvas.getContext("webgl", {
      alpha: false,
      antialias: true,
      depth: true,
      premultipliedAlpha: false,
    });
    if (!this.gl) throw new Error("The dataset viewer requires WebGL with a depth buffer");
    this.drag = null;
    this.initProgram();
    this.bindCamera();
    new ResizeObserver(() => drawAll()).observe(canvas);
  }

  compile(type, source) {
    const gl = this.gl;
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader) || "unknown shader error";
      gl.deleteShader(shader);
      throw new Error(message);
    }
    return shader;
  }

  initProgram() {
    const gl = this.gl;
    const vertexShader = this.compile(gl.VERTEX_SHADER, `
      attribute vec3 aPosition;
      attribute vec3 aNormal;
      attribute vec3 aColor;
      uniform mat4 uViewProjection;
      varying vec3 vWorld;
      varying vec3 vNormal;
      varying vec3 vColor;
      void main() {
        vWorld = aPosition;
        vNormal = aNormal;
        vColor = aColor;
        gl_Position = uViewProjection * vec4(aPosition, 1.0);
      }
    `);
    const fragmentShader = this.compile(gl.FRAGMENT_SHADER, `
      precision highp float;
      varying vec3 vWorld;
      varying vec3 vNormal;
      varying vec3 vColor;
      uniform vec3 uCamera;
      uniform vec3 uLightDirection;
      uniform vec3 uFogColor;
      uniform float uFogNear;
      uniform float uFogFar;
      void main() {
        vec3 normal = normalize(vNormal);
        vec3 lightDirection = normalize(uLightDirection);
        vec3 viewDirection = normalize(uCamera - vWorld);
        float diffuse = max(dot(normal, lightDirection), 0.0);
        vec3 fillDirection = normalize(vec3(0.55, 0.34, 0.76));
        float fill = max(dot(normal, fillDirection), 0.0);
        float skyFill = normal.y * 0.5 + 0.5;
        float lightLevel = 0.44 + diffuse * 0.68 + fill * 0.15 + skyFill * 0.06;
        vec3 halfDirection = normalize(lightDirection + viewDirection);
        float specular = pow(max(dot(normal, halfDirection), 0.0), 42.0) * 0.34;
        float rim = pow(1.0 - max(dot(normal, viewDirection), 0.0), 3.0) * 0.13;
        vec3 lit = vColor * lightLevel + vec3(1.0, 0.78, 0.60) * specular + vColor * rim;
        float distanceToCamera = length(uCamera - vWorld);
        float fog = smoothstep(uFogNear, uFogFar, distanceToCamera);
        gl_FragColor = vec4(mix(lit, uFogColor, fog * 0.28), 1.0);
      }
    `);
    this.program = gl.createProgram();
    gl.attachShader(this.program, vertexShader);
    gl.attachShader(this.program, fragmentShader);
    gl.linkProgram(this.program);
    if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(this.program) || "WebGL link failed");
    }
    this.locations = {
      position: gl.getAttribLocation(this.program, "aPosition"),
      normal: gl.getAttribLocation(this.program, "aNormal"),
      color: gl.getAttribLocation(this.program, "aColor"),
      viewProjection: gl.getUniformLocation(this.program, "uViewProjection"),
      camera: gl.getUniformLocation(this.program, "uCamera"),
      lightDirection: gl.getUniformLocation(this.program, "uLightDirection"),
      fogColor: gl.getUniformLocation(this.program, "uFogColor"),
      fogNear: gl.getUniformLocation(this.program, "uFogNear"),
      fogFar: gl.getUniformLocation(this.program, "uFogFar"),
    };
    this.meshBuffer = gl.createBuffer();
    this.lineBuffer = gl.createBuffer();
  }

  bindCamera() {
    this.canvas.addEventListener("pointerdown", event => {
      this.canvas.setPointerCapture(event.pointerId);
      this.drag = { x: event.clientX, y: event.clientY, button: event.button };
    });
    this.canvas.addEventListener("pointermove", event => {
      if (!this.drag) return;
      const dx = event.clientX - this.drag.x;
      const dy = event.clientY - this.drag.y;
      this.drag.x = event.clientX;
      this.drag.y = event.clientY;
      if (this.drag.button === 2) {
        cameraState.panX += dx;
        cameraState.panY += dy;
      } else {
        cameraState.yaw += dx * 0.008;
        cameraState.pitch = clamp(cameraState.pitch + dy * 0.006, -1.15, 1.15);
      }
      drawAll();
    });
    this.canvas.addEventListener("pointerup", () => { this.drag = null; });
    this.canvas.addEventListener("pointercancel", () => { this.drag = null; });
    this.canvas.addEventListener("contextmenu", event => event.preventDefault());
    this.canvas.addEventListener("wheel", event => {
      event.preventDefault();
      cameraState.zoom = clamp(cameraState.zoom * Math.exp(-event.deltaY * 0.001), 0.35, 4.5);
      drawAll();
    }, { passive: false });
    this.canvas.addEventListener("dblclick", () => resetCamera());
  }

  matrixMultiply(a, b) {
    const out = new Float32Array(16);
    for (let column = 0; column < 4; column++) {
      for (let row = 0; row < 4; row++) {
        let value = 0;
        for (let inner = 0; inner < 4; inner++) value += a[inner * 4 + row] * b[column * 4 + inner];
        out[column * 4 + row] = value;
      }
    }
    return out;
  }

  perspective(fovRadians, aspect, near, far) {
    const f = 1 / Math.tan(fovRadians * .5);
    const range = 1 / (near - far);
    return new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * range, -1,
      0, 0, 2 * far * near * range, 0,
    ]);
  }

  lookAt(eye, target, upReference) {
    const z = normalize(sub(eye, target));
    let x = normalize(cross(upReference, z));
    if (norm(x) < 1e-6) x = [1, 0, 0];
    const y = normalize(cross(z, x));
    return new Float32Array([
      x[0], y[0], z[0], 0,
      x[1], y[1], z[1], 0,
      x[2], y[2], z[2], 0,
      -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
    ]);
  }

  vertex(target, position, normal, color) {
    target.push(
      position[0], position[1], position[2],
      normal[0], normal[1], normal[2],
      color[0], color[1], color[2],
    );
  }

  triangle(target, a, b, c, normal, color) {
    this.vertex(target, a, normal, color);
    this.vertex(target, b, normal, color);
    this.vertex(target, c, normal, color);
  }

  quad(target, a, b, c, d, normal, color) {
    this.triangle(target, a, b, c, normal, color);
    this.triangle(target, a, c, d, normal, color);
  }

  line(target, a, b, color) {
    this.vertex(target, a, [0, 1, 0], color);
    this.vertex(target, b, [0, 1, 0], color);
  }

  groundPoint(target, center, radius, color, segments = 24) {
    for (let segment = 0; segment < segments; segment++) {
      const angleA = segment * Math.PI * 2 / segments;
      const angleB = (segment + 1) * Math.PI * 2 / segments;
      const pointA = [center[0] + Math.cos(angleA) * radius, center[1], center[2] + Math.sin(angleA) * radius];
      const pointB = [center[0] + Math.cos(angleB) * radius, center[1], center[2] + Math.sin(angleB) * radius];
      this.triangle(target, center, pointB, pointA, [0, 1, 0], color);
    }
  }

  groundRing(target, center, innerRadius, outerRadius, color, segments = 32) {
    for (let segment = 0; segment < segments; segment++) {
      const angleA = segment * Math.PI * 2 / segments;
      const angleB = (segment + 1) * Math.PI * 2 / segments;
      const innerA = [center[0] + Math.cos(angleA) * innerRadius, center[1], center[2] + Math.sin(angleA) * innerRadius];
      const innerB = [center[0] + Math.cos(angleB) * innerRadius, center[1], center[2] + Math.sin(angleB) * innerRadius];
      const outerA = [center[0] + Math.cos(angleA) * outerRadius, center[1], center[2] + Math.sin(angleA) * outerRadius];
      const outerB = [center[0] + Math.cos(angleB) * outerRadius, center[1], center[2] + Math.sin(angleB) * outerRadius];
      this.quad(target, innerA, innerB, outerB, outerA, [0, 1, 0], color);
    }
  }

  capsule(target, pointA, pointB, radius, color, segments = 18, hemisphereSteps = 6) {
    let axis = normalize(sub(pointB, pointA));
    if (norm(axis) < 1e-6) axis = [0, 1, 0];
    const reference = Math.abs(axis[1]) < .88 ? [0, 1, 0] : [1, 0, 0];
    const tangent = normalize(cross(axis, reference));
    const bitangent = normalize(cross(axis, tangent));
    const rings = [];
    const addRing = (center, phi) => {
      const sinPhi = Math.sin(phi);
      const cosPhi = Math.cos(phi);
      const ring = [];
      for (let segment = 0; segment < segments; segment++) {
        const theta = segment * Math.PI * 2 / segments;
        const radial = add(mul(tangent, Math.cos(theta)), mul(bitangent, Math.sin(theta)));
        const normal = normalize(add(mul(axis, sinPhi), mul(radial, cosPhi)));
        ring.push({ position: add(center, mul(normal, radius)), normal });
      }
      rings.push(ring);
    };
    for (let step = 0; step <= hemisphereSteps; step++) addRing(pointA, -Math.PI * .5 + Math.PI * .5 * step / hemisphereSteps);
    addRing(pointB, 0);
    for (let step = 1; step <= hemisphereSteps; step++) addRing(pointB, Math.PI * .5 * step / hemisphereSteps);
    for (let ringIndex = 0; ringIndex < rings.length - 1; ringIndex++) {
      const ringA = rings[ringIndex];
      const ringB = rings[ringIndex + 1];
      for (let segment = 0; segment < segments; segment++) {
        const next = (segment + 1) % segments;
        const a = ringA[segment];
        const b = ringB[segment];
        const c = ringB[next];
        const d = ringA[next];
        this.vertex(target, a.position, a.normal, color);
        this.vertex(target, b.position, b.normal, color);
        this.vertex(target, c.position, c.normal, color);
        this.vertex(target, a.position, a.normal, color);
        this.vertex(target, c.position, c.normal, color);
        this.vertex(target, d.position, d.normal, color);
      }
    }
  }

  controllerAxis(target, origin, direction, color, length = .20) {
    const axis = normalize(direction);
    if (norm(axis) < 1e-7) return;
    const tip = add(origin, mul(axis, length));
    this.capsule(target, origin, tip, .008, color, 10, 4);
    let side = normalize(cross(axis, [0, 1, 0]));
    if (norm(side) < 1e-7) side = normalize(cross(axis, [1, 0, 0]));
    const head = add(tip, mul(axis, -.050));
    this.capsule(target, tip, add(head, mul(side, .026)), .009, color, 10, 4);
    this.capsule(target, tip, add(head, mul(side, -.026)), .009, color, 10, 4);
  }

  box(target, box, color) {
    const hx = box.dims[0] * .5;
    const hy = box.dims[1] * .5;
    const hz = box.dims[2] * .5;
    const axisX = normalize(box.forward);
    const axisY = normalize(box.side);
    const axisZ = normalize(box.up || box.palmNormal);
    const corner = (x, y, z) => add(add(add(box.center, mul(axisX, x)), mul(axisY, y)), mul(axisZ, z));
    const corners = [
      corner(-hx,-hy,-hz), corner(hx,-hy,-hz), corner(hx,hy,-hz), corner(-hx,hy,-hz),
      corner(-hx,-hy,hz), corner(hx,-hy,hz), corner(hx,hy,hz), corner(-hx,hy,hz),
    ];
    const faces = [
      [[0,3,2,1], mul(axisZ, -1)], [[4,5,6,7], axisZ],
      [[0,1,5,4], mul(axisY, -1)], [[1,2,6,5], axisX],
      [[2,3,7,6], axisY], [[3,0,4,7], mul(axisX, -1)],
    ];
    for (const [indices, normal] of faces) {
      const [a, b, c, d] = indices.map(index => corners[index]);
      this.triangle(target, a, b, c, normal, color);
      this.triangle(target, a, c, d, normal, color);
    }
  }

  spineBlock(target, data, lowerIndex, upperIndex, lowerWidth, upperWidth, lowerDepth, upperDepth, color, sharedSide = null) {
    const rawLower = posAt(data, lowerIndex);
    const rawUpper = posAt(data, upperIndex);
    let direction = normalize(sub(rawUpper, rawLower));
    if (norm(direction) < 1e-6) direction = [0, 1, 0];
    const seamInset = Math.min(.004, norm(sub(rawUpper, rawLower)) * .08);
    const lower = add(rawLower, mul(direction, seamInset));
    const upper = add(rawUpper, mul(direction, -seamInset));
    const makeSide = index => {
      let side = axisAt(data, index, 2);
      side = normalize(sub(side, mul(direction, dot(side, direction))));
      if (norm(side) < 1e-6) {
        const reference = Math.abs(direction[1]) < .9 ? [0, 1, 0] : [1, 0, 0];
        side = normalize(cross(direction, reference));
      }
      return side;
    };
    let lowerSide = makeSide(lowerIndex);
    if (sharedSide && norm(sharedSide) > 1e-6 && dot(lowerSide, sharedSide) < 0) {
      lowerSide = mul(lowerSide, -1);
    }
    const frame = { side: lowerSide, forward: normalize(cross(lowerSide, direction)) };
    const corner = (center, sideAmount, forwardAmount) => add(add(center, mul(frame.side, sideAmount)), mul(frame.forward, forwardAmount));
    const lowerCorners = [
      corner(lower, -lowerWidth * .5, -lowerDepth * .5), corner(lower, lowerWidth * .5, -lowerDepth * .5),
      corner(lower, lowerWidth * .5, lowerDepth * .5), corner(lower, -lowerWidth * .5, lowerDepth * .5),
    ];
    const upperCorners = [
      corner(upper, -upperWidth * .5, -upperDepth * .5), corner(upper, upperWidth * .5, -upperDepth * .5),
      corner(upper, upperWidth * .5, upperDepth * .5), corner(upper, -upperWidth * .5, upperDepth * .5),
    ];
    this.quad(target, lowerCorners[0], lowerCorners[1], lowerCorners[2], lowerCorners[3], mul(direction, -1), color);
    this.quad(target, upperCorners[3], upperCorners[2], upperCorners[1], upperCorners[0], direction, color);
    this.quad(target, lowerCorners[0], upperCorners[0], upperCorners[1], lowerCorners[1], mul(frame.forward, -1), color);
    this.quad(target, lowerCorners[1], upperCorners[1], upperCorners[2], lowerCorners[2], frame.side, color);
    this.quad(target, lowerCorners[2], upperCorners[2], upperCorners[3], lowerCorners[3], frame.forward, color);
    this.quad(target, lowerCorners[3], upperCorners[3], upperCorners[0], lowerCorners[0], mul(frame.side, -1), color);
  }

  headFrame(data) {
    const head = nameToIndex.get("head");
    const neck2 = nameToIndex.get("neck_02");
    if (head === undefined) return null;
    const upperAuthored = posAt(data, head);
    const up = axisAt(data, head, 0);
    const forward = mul(axisAt(data, head, 1), -1);
    const side = axisAt(data, head, 2);
    const lowerAuthored = neck2 === undefined ? add(upperAuthored, mul(up, -.054)) : posAt(data, neck2);
    const segmentLength = Math.max(.054, norm(sub(upperAuthored, lowerAuthored)));
    return {
      lower: lowerAuthored.slice(),
      upper: add(lowerAuthored, mul(up, segmentLength)),
      up, forward, side, radius: .100, segmentLength,
    };
  }

  headSurface(frameSpec, upOffset, sideOffset, lift = 0) {
    let capOffset = 0;
    if (upOffset > 0) capOffset = upOffset;
    else if (upOffset < -frameSpec.segmentLength) capOffset = upOffset + frameSpec.segmentLength;
    const forwardRadius = Math.sqrt(Math.max(0, frameSpec.radius ** 2 - sideOffset ** 2 - capOffset ** 2));
    return add(add(add(frameSpec.upper, mul(frameSpec.up, upOffset)), mul(frameSpec.side, sideOffset)), mul(frameSpec.forward, forwardRadius + lift));
  }

  handBox(data, spec) {
    const axes = [axisAt(data, spec.hand, 0), axisAt(data, spec.hand, 1), axisAt(data, spec.hand, 2)];
    const forward = spec.side === 1 ? mul(axes[0], -1) : axes[0];
    const palmNormal = axes[1];
    const side = axes[2];
    const dims = [.145, .090, .045];
    const hand = posAt(data, spec.hand);
    const center = add(add(hand, mul(forward, dims[0] * .5)), mul(palmNormal, -.0025));
    return { center, forward, side, palmNormal, dims };
  }

  footBoxes(data, spec) {
    const footDims = [.175, .120, .051];
    const toeDims = [.048, .120, .049];
    const ankle = posAt(data, spec.ankle);
    const toe = posAt(data, spec.toe);
    const toeVector = sub(toe, ankle);
    let footForward = axisAt(data, spec.ankle, 1);
    if (dot(footForward, toeVector) < 0) footForward = mul(footForward, -1);
    let footUp = axisAt(data, spec.ankle, 0);
    const footSide = axisAt(data, spec.ankle, 2);
    if (footUp[1] < 0) footUp = mul(footUp, -1);
    const heelBack = add(toe, mul(footForward, -footDims[0]));
    const footCenter = add(add(heelBack, mul(footForward, footDims[0] * .5)), mul(footUp, -.006));

    let toeFootForward = axisAt(data, spec.ankle, 1);
    if (dot(toeFootForward, toeVector) < 0) toeFootForward = mul(toeFootForward, -1);
    let toeForward = axisAt(data, spec.toe, 0);
    if (dot(toeForward, toeFootForward) < 0) toeForward = mul(toeForward, -1);
    let toeUp = axisAt(data, spec.toe, 1);
    const referenceSide = axisAt(data, spec.toe, 2);
    if (toeUp[1] < 0) toeUp = mul(toeUp, -1);
    let toeSide = normalize(cross(toeForward, toeUp));
    if (norm(toeSide) < 1e-6) toeSide = referenceSide;
    if (dot(toeSide, referenceSide) < 0) toeSide = mul(toeSide, -1);
    toeUp = normalize(cross(toeSide, toeForward));
    if (toeUp[1] < 0) { toeUp = mul(toeUp, -1); toeSide = mul(toeSide, -1); }
    const toeCenter = add(add(toe, mul(toeForward, toeDims[0] * .5)), mul(toeUp, -.006));
    return {
      foot: { center: footCenter, forward: footForward, side: footSide, up: footUp, dims: footDims },
      toe: { center: toeCenter, forward: toeForward, side: toeSide, up: toeUp, dims: toeDims },
    };
  }

  swordVertex(index) {
    const offset = index * 3;
    return [swordMesh.vertices[offset], swordMesh.vertices[offset + 1], swordMesh.vertices[offset + 2]];
  }

  swordLocalToWorld(local, handPosition, handAxes) {
    const matrix = swordMesh.local_to_hand;
    const inHand = [
      local[0] * matrix[0] + local[1] * matrix[4] + local[2] * matrix[8] + matrix[12],
      local[0] * matrix[1] + local[1] * matrix[5] + local[2] * matrix[9] + matrix[13],
      local[0] * matrix[2] + local[1] * matrix[6] + local[2] * matrix[10] + matrix[14],
    ];
    return add(add(add(handPosition, mul(handAxes[0], inHand[0])), mul(handAxes[1], inHand[1])), mul(handAxes[2], inHand[2]));
  }

  addSword(target, data) {
    if (!swordMesh) return;
    const hand = nameToIndex.get(swordMesh.hand_node || "hand_r");
    if (hand === undefined) return;
    const handPosition = posAt(data, hand);
    const handAxes = [axisAt(data, hand, 0), axisAt(data, hand, 1), axisAt(data, hand, 2)];
    for (let triangle = 0; triangle < swordMesh.triangles.length; triangle += 3) {
      const indices = [swordMesh.triangles[triangle], swordMesh.triangles[triangle + 1], swordMesh.triangles[triangle + 2]];
      const points = indices.map(index => this.swordLocalToWorld(this.swordVertex(index), handPosition, handAxes));
      const normal = normalize(cross(sub(points[1], points[0]), sub(points[2], points[0])));
      const blade = indices.some(index => swordMesh.bladeMask[index]);
      this.triangle(target, points[0], points[1], points[2], normal, blade ? [.86, .93, .98] : [.52, .24, .07]);
    }
  }

  addBody(mesh, data) {
    const bodyColor = [.91, .49, .25];
    const defs = [
      ["pelvis", "spine_01", .125], ["spine_01", "spine_02", .135], ["spine_02", "spine_03", .145],
      ["spine_03", "spine_04", .145], ["spine_04", "spine_05", .135], ["spine_05", "neck_01", .085],
      ["neck_02", "head", .100],
      ["clavicle_l", "upperarm_l", .055], ["upperarm_l", "lowerarm_l", .058], ["lowerarm_l", "hand_l", .048],
      ["clavicle_r", "upperarm_r", .055], ["upperarm_r", "lowerarm_r", .058], ["lowerarm_r", "hand_r", .048],
      ["pelvis", "thigh_l", .095], ["thigh_l", "calf_l", .083], ["calf_l", "foot_l", .062],
      ["pelvis", "thigh_r", .095], ["thigh_r", "calf_r", .083], ["calf_r", "foot_r", .062],
    ].map(([a, b, r]) => ({ a: nameToIndex.get(a), b: nameToIndex.get(b), aName: a, bName: b, r }))
      .filter(item => item.a !== undefined && item.b !== undefined);
    const spineNames = new Set(["pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01"]);
    for (const volume of defs) {
      const isHipBridge = volume.aName === "pelvis" && (volume.bName === "thigh_l" || volume.bName === "thigh_r");
      const isHead = volume.aName === "neck_02" && volume.bName === "head";
      const isSpine = spineNames.has(volume.aName) && spineNames.has(volume.bName);
      if (isHipBridge || isHead || isSpine) continue;
      this.capsule(mesh, posAt(data, volume.a), posAt(data, volume.b), volume.r, bodyColor);
    }

    const spineBlocks = [
      ["pelvis", "spine_02", .205, .215, .115, .120],
      ["spine_02", "spine_04", .230, .255, .125, .140],
      ["spine_04", "spine_05", .255, .265, .140, .145],
    ];
    const clavicleLeft = nameToIndex.get("clavicle_l");
    const clavicleRight = nameToIndex.get("clavicle_r");
    const torsoSide = clavicleLeft !== undefined && clavicleRight !== undefined
      ? normalize(sub(posAt(data, clavicleRight), posAt(data, clavicleLeft)))
      : null;
    for (const [lowerName, upperName, lowerWidth, upperWidth, lowerDepth, upperDepth] of spineBlocks) {
      const lower = nameToIndex.get(lowerName);
      const upper = nameToIndex.get(upperName);
      if (lower === undefined || upper === undefined) continue;
      this.spineBlock(mesh, data, lower, upper, lowerWidth, upperWidth, lowerDepth, upperDepth, bodyColor, torsoSide);
    }

    const headSpec = this.headFrame(data);
    const neck1 = nameToIndex.get("neck_01");
    const neck2 = nameToIndex.get("neck_02");
    if (headSpec && neck1 !== undefined && neck2 !== undefined) {
      this.box(mesh, {
        center: mul(add(posAt(data, neck1), posAt(data, neck2)), .5),
        dims: [.105, .105, .105],
        forward: headSpec.forward,
        side: headSpec.side,
        up: headSpec.up,
      }, bodyColor);
    }
    if (headSpec) this.capsule(mesh, headSpec.lower, headSpec.upper, headSpec.radius, bodyColor, 16, 5);

    const handSpecs = [
      { hand: nameToIndex.get("hand_l"), lower: nameToIndex.get("lowerarm_l"), side: 0 },
      { hand: nameToIndex.get("hand_r"), lower: nameToIndex.get("lowerarm_r"), side: 1 },
    ].filter(spec => spec.hand !== undefined && spec.lower !== undefined);
    for (const spec of handSpecs) this.box(mesh, this.handBox(data, spec), spec.side === 0 ? [.20, .72, .88] : [.86, .20, .13]);

    const footSpecs = [
      { ankle: nameToIndex.get("foot_l"), toe: nameToIndex.get("ball_l"), side: 0 },
      { ankle: nameToIndex.get("foot_r"), toe: nameToIndex.get("ball_r"), side: 1 },
    ].filter(spec => spec.ankle !== undefined && spec.toe !== undefined);
    for (const spec of footSpecs) {
      const boxes = this.footBoxes(data, spec);
      const color = spec.side === 0 ? [.88, .18, .14] : [.18, .72, .34];
      this.box(mesh, boxes.foot, color);
      this.box(mesh, boxes.toe, color);
    }

    this.addSword(mesh, data);
    if (headSpec) {
      for (const sign of [-1, 1]) {
        const eye = this.headSurface(headSpec, -.010, sign * .031, .003);
        this.capsule(mesh, eye, eye, .008, [.055, .075, .095], 12, 5);
      }
      const noseBridge = this.headSurface(headSpec, -.026, 0, .002);
      const noseBase = this.headSurface(headSpec, -.054, 0, .002);
      const noseTip = this.headSurface(headSpec, -.054, 0, .026);
      this.capsule(mesh, noseBridge, noseBase, .0055, [.58, .20, .08], 10, 4);
      this.capsule(mesh, noseBase, noseTip, .007, [.58, .20, .08], 10, 4);
      const mouthLeft = this.headSurface(headSpec, -.083, -.034, .003);
      const mouthLow = this.headSurface(headSpec, -.088, 0, .003);
      const mouthRight = this.headSurface(headSpec, -.083, .034, .003);
      this.capsule(mesh, mouthLeft, mouthLow, .0045, [.40, .025, .018], 10, 4);
      this.capsule(mesh, mouthLow, mouthRight, .0045, [.40, .025, .018], 10, 4);
    }
  }

  bindAndDraw(buffer, values, mode) {
    if (!values.length) return;
    const gl = this.gl;
    const stride = 9 * 4;
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(values), gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(this.locations.position);
    gl.enableVertexAttribArray(this.locations.normal);
    gl.enableVertexAttribArray(this.locations.color);
    gl.vertexAttribPointer(this.locations.position, 3, gl.FLOAT, false, stride, 0);
    gl.vertexAttribPointer(this.locations.normal, 3, gl.FLOAT, false, stride, 3 * 4);
    gl.vertexAttribPointer(this.locations.color, 3, gl.FLOAT, false, stride, 6 * 4);
    gl.drawArrays(mode, 0, values.length / 9);
  }

  draw(data, sharedRoot) {
    const gl = this.gl;
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(rect.width * dpr));
    const height = Math.max(1, Math.floor(rect.height * dpr));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    gl.viewport(0, 0, width, height);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(.078, .096, .128, 1);
    gl.clearDepth(1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    if (!data) return;

    const distance = 3.55 / cameraState.zoom;
    const cameraTarget = [sharedRoot[0], .87, sharedRoot[2]];
    const rawEye = [
      cameraTarget[0] + Math.sin(cameraState.yaw) * distance,
      cameraTarget[1] + distance * (.27 - cameraState.pitch * .55),
      cameraTarget[2] + Math.cos(cameraState.yaw) * distance,
    ];
    const forward = normalize(sub(cameraTarget, rawEye));
    let right = normalize(cross(forward, [0, 1, 0]));
    if (norm(right) < 1e-6) right = [1, 0, 0];
    const up = normalize(cross(right, forward));
    const targetDepth = Math.max(.01, dot(sub(cameraTarget, rawEye), forward));
    const focalCss = (rect.height * .5) / Math.tan(45 * Math.PI / 360);
    const pixelsPerMeter = focalCss / targetDepth;
    const shift = add(mul(right, -cameraState.panX / Math.max(1e-6, pixelsPerMeter)), mul(up, cameraState.panY / Math.max(1e-6, pixelsPerMeter)));
    const eye = add(rawEye, shift);
    const target = add(cameraTarget, shift);
    const view = this.lookAt(eye, target, [0, 1, 0]);
    const projection = this.perspective(45 * Math.PI / 180, width / height, .02, 60);
    const viewProjection = this.matrixMultiply(projection, view);

    gl.useProgram(this.program);
    gl.uniformMatrix4fv(this.locations.viewProjection, false, viewProjection);
    gl.uniform3fv(this.locations.camera, eye);
    gl.uniform3fv(this.locations.lightDirection, [-.58, .78, -.24]);
    gl.uniform3fv(this.locations.fogColor, [.078, .096, .128]);
    gl.uniform1f(this.locations.fogNear, Math.max(1.2, targetDepth * .68));
    gl.uniform1f(this.locations.fogFar, targetDepth * 1.55 + 3.5);

    const mesh = [];
    const lines = [];
    const floorRadius = 6.5;
    const floorY = -.006;
    const floorColor = [.050, .102, .174];
    const floorA = [sharedRoot[0] - floorRadius, floorY, sharedRoot[2] - floorRadius];
    const floorB = [sharedRoot[0] + floorRadius, floorY, sharedRoot[2] - floorRadius];
    const floorC = [sharedRoot[0] + floorRadius, floorY, sharedRoot[2] + floorRadius];
    const floorD = [sharedRoot[0] - floorRadius, floorY, sharedRoot[2] + floorRadius];
    this.triangle(mesh, floorA, floorC, floorB, [0, 1, 0], floorColor);
    this.triangle(mesh, floorA, floorD, floorC, [0, 1, 0], floorColor);
    for (let step = -26; step <= 26; step++) {
      const value = step * .25;
      const color = step % 4 === 0 ? [.22, .39, .60] : [.11, .20, .32];
      this.line(lines, [sharedRoot[0] + value, .002, sharedRoot[2] - floorRadius], [sharedRoot[0] + value, .002, sharedRoot[2] + floorRadius], color);
      this.line(lines, [sharedRoot[0] - floorRadius, .002, sharedRoot[2] + value], [sharedRoot[0] + floorRadius, .002, sharedRoot[2] + value], color);
    }
    this.groundRing(mesh, [sharedRoot[0], .010, sharedRoot[2]], .078, .112, [1, .16, .72]);
    this.groundPoint(mesh, [sharedRoot[0], .012, sharedRoot[2]], .032, [1, .66, .90]);
    this.addBody(mesh, data);

    const headSpec = this.headFrame(data);
    if (headSpec) {
      const gazeStart = this.headSurface(headSpec, 0, 0, .012);
      const gazeEnd = add(gazeStart, mul(headSpec.forward, 3.0));
      this.line(lines, gazeStart, gazeEnd, [.10, 1.0, .86]);
      this.controllerAxis(mesh, gazeStart, headSpec.forward, [.10, 1.0, .86], .42);
    }
    const neck2 = nameToIndex.get("neck_02");
    if (neck2 !== undefined) {
      const origin = posAt(data, neck2);
      const semanticAxes = [axisAt(data, neck2, 0), mul(axisAt(data, neck2, 1), -1), axisAt(data, neck2, 2)];
      const colors = [[1.0, .18, .12], [.20, .92, .30], [.20, .46, 1.0]];
      for (let axis = 0; axis < 3; axis++) this.controllerAxis(mesh, origin, semanticAxes[axis], colors[axis], .20);
    }
    this.bindAndDraw(this.meshBuffer, mesh, gl.TRIANGLES);
    this.bindAndDraw(this.lineBuffer, lines, gl.LINES);
  }
}
