// Reusable vertex storage; geometry, tessellation and draw order stay unchanged.
class LabVertexStream {
  constructor(capacity){this.data=new Float32Array(capacity);this.length=0;}
  push(a,b,c,d,e,f,g,h,i){
    const end=this.length+9;
    if(end>this.data.length){const next=new Float32Array(Math.max(end,this.data.length*2));next.set(this.data);this.data=next;}
    const v=this.data,n=this.length;v[n]=a;v[n+1]=b;v[n+2]=c;v[n+3]=d;v[n+4]=e;v[n+5]=f;v[n+6]=g;v[n+7]=h;v[n+8]=i;this.length=end;
  }
  view(){return this.data.subarray(0,this.length);}
}
const labCapsuleTemplates=new Map();
function labCapsuleTemplate(segments,steps,half=false){
 const key=segments+':'+steps+':'+half;if(labCapsuleTemplates.has(key))return labCapsuleTemplates.get(key);
 const coefficients=[],indices=[];
 const columns=segments+(half?1:0);
 const ring=(end,phi)=>{for(let j=0;j<columns;j++){const theta=half?-Math.PI*.5+j*Math.PI/segments:j*Math.PI*2/segments;coefficients.push(end,Math.sin(phi),Math.cos(phi),Math.cos(theta),Math.sin(theta));}};
 for(let i=0;i<=steps;i++)ring(0,-Math.PI*.5+Math.PI*.5*i/steps);
 ring(1,0);for(let i=1;i<=steps;i++)ring(1,Math.PI*.5*i/steps);
 for(let i=0;i<2*steps+1;i++)for(let j=0;j<segments;j++){const next=half?j+1:(j+1)%segments,a=i*columns+j,b=(i+1)*columns+j,c=(i+1)*columns+next,d=i*columns+next;indices.push(a,b,c,a,c,d);}
 const template={coefficients:new Float64Array(coefficients),indices:new Uint32Array(indices),vertices:new Float64Array(coefficients.length/5*6)};
 labCapsuleTemplates.set(key,template);return template;
}
"use strict";

class WebGLMotionRenderer {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.gl = canvas.getContext("webgl2", {
      alpha: false, preserveDrawingBuffer: true,
      antialias: true,
      depth: true,
      premultipliedAlpha: false,
    }) || canvas.getContext("webgl", {
      alpha: false, preserveDrawingBuffer: true,
      antialias: true,
      depth: true,
      premultipliedAlpha: false,
    });
    if (!this.gl) throw new Error("The dataset viewer requires WebGL with a depth buffer");
    this.drag = null;
    this.initProgram();
    this.pixelRatio=options.pixelRatio;
    this.rect=options.rect||canvas.getBoundingClientRect();
    if(options.interactive===false)return;
    this.bindCamera();
    new ResizeObserver(entries => {
      const rect=entries[0].contentRect;
      if(rect.width===this.rect.width&&rect.height===this.rect.height)return;
      this.rect=rect;drawAll();
    }).observe(canvas);
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
      uniform bool uUnlit;
      uniform float uOpacity;
      void main() {
        if (uUnlit) { gl_FragColor = vec4(vColor, uOpacity); return; }
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
        gl_FragColor = vec4(mix(lit, uFogColor, fog * 0.28), uOpacity);
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
      unlit: gl.getUniformLocation(this.program, "uUnlit"),
      opacity: gl.getUniformLocation(this.program, "uOpacity"),
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

  capsule(target, pointA, pointB, radius, color, segments = 18, hemisphereSteps = 6, tangentOverride = null, half = false) {
    let axis = normalize(sub(pointB, pointA));
    if (norm(axis) < 1e-6) axis = [0, 1, 0];
    const reference = Math.abs(axis[1]) < .88 ? [0, 1, 0] : [1, 0, 0];
    const tangent = tangentOverride || normalize(cross(axis, reference));
    const bitangent = normalize(cross(axis, tangent));
    const {coefficients:c,indices,vertices:v}=labCapsuleTemplate(segments,hemisphereSteps,half);
    for(let k=0,n=0;k<c.length;k+=5,n+=6){
      const center=c[k]?pointB:pointA,s=c[k+1],co=c[k+2],ct=c[k+3],st=c[k+4];
      let nx=axis[0]*s+(tangent[0]*ct+bitangent[0]*st)*co;
      let ny=axis[1]*s+(tangent[1]*ct+bitangent[1]*st)*co;
      let nz=axis[2]*s+(tangent[2]*ct+bitangent[2]*st)*co;
      const inv=1/(Math.hypot(nx,ny,nz)||1);nx*=inv;ny*=inv;nz*=inv;
      v[n]=center[0]+nx*radius;v[n+1]=center[1]+ny*radius;v[n+2]=center[2]+nz*radius;
      v[n+3]=nx;v[n+4]=ny;v[n+5]=nz;
    }
    for(let i=0;i<indices.length;i++){const n=indices[i]*6;target.push(v[n],v[n+1],v[n+2],v[n+3],v[n+4],v[n+5],color[0],color[1],color[2]);}
  }

  limbTintAxis(data,start,end){
    const axis=normalize(sub(data.points[end],data.points[start]));
    let outward=sub(data.axes[start][1],mul(axis,dot(data.axes[start][1],axis)));
    if(norm(outward)<1e-7)outward=sub(data.axes[start][2],mul(axis,dot(data.axes[start][2],axis)));
    return normalize(cross(axis,normalize(outward)));
  }

  // Reused from Parry/Defense Harness: bone-relative cyan half, 0.8 mm offset.
  limbLongAxisHalf(mesh,solution,start,end,radius,outwardSign){
  const pointA=solution.points[start],pointB=solution.points[end];let axis=normalize(sub(pointB,pointA));if(norm(axis)<1e-7)return;
  let outward=mul(solution.axes[start][1],outwardSign);outward=sub(outward,mul(axis,dot(outward,axis)));if(norm(outward)<1e-7){outward=mul(solution.axes[start][2],outwardSign);outward=sub(outward,mul(axis,dot(outward,axis)))}if(norm(outward)<1e-7)return;
  outward=normalize(cross(axis,normalize(outward)));
  this.capsule(mesh,pointA,pointB,radius+.0008,[.08,.86,.94],10,5,outward,true);
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

  box(target, box, color, palmColor = null, faceTarget = null) {
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
      [[0,3,2,1], mul(axisZ, -1), box.palmFace < 0 ? palmColor || color : color],
      [[4,5,6,7], axisZ, box.palmFace < 0 ? color : palmColor || color],
      [[0,1,5,4], mul(axisY, -1)], [[1,2,6,5], axisX],
      [[2,3,7,6], axisY], [[3,0,4,7], mul(axisX, -1)],
    ];
    for (const [indices, normal, faceColor = color] of faces) {
      const [a, b, c, d] = indices.map(index => corners[index]);
      const output=faceTarget?faceTarget([a,b,c,d],normal,faceColor):target;
      if(!output)continue;
      this.triangle(output, a, b, c, normal, faceColor);
      this.triangle(output, a, c, d, normal, faceColor);
    }
  }

  platformBox(opaque,transparent,surface,color,opacity){
    const camera=this.viewCamera;
    this.box(opaque,surface.box,color,null,(points,normal,faceColor)=>{
      const center=mul(add(points[0],points[2]),.5);
      // The walkable top is opaque only from its front. Its back must not
      // become an invisible opaque lid when looking through the underside.
      if(dot(normal,sub(camera.eye,center))<=0)return null;
      if(dot(normal,surface.normal)>.999||opacity>=1)return opaque;
      if(opacity>0)transparent.push({points,normal,color:faceColor,depth:dot(sub(center,camera.eye),camera.forward)});
      return null;
    });
  }

  drawPlatformSides(faces,opacity){
    if(!faces.length||opacity<=0)return;
    faces.sort((a,b)=>b.depth-a.depth);
    const mesh=this.platformSideMesh||(this.platformSideMesh=new LabVertexStream(4096));mesh.length=0;
    for(const face of faces){const [a,b,c,d]=face.points;this.triangle(mesh,a,b,c,face.normal,face.color);this.triangle(mesh,a,c,d,face.normal,face.color);}
    const gl=this.gl;gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);gl.uniform1f(this.locations.opacity,opacity);
    try{this.bindAndDraw(this.meshBuffer,mesh,gl.TRIANGLES);}
    finally{gl.uniform1f(this.locations.opacity,1);gl.depthMask(true);gl.disable(gl.BLEND);}
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
    return { center, forward, side, palmNormal, dims, palmFace: spec.side === 1 ? -1 : 1 };
  }

  footBoxes(data, spec) {
    const footDims = [.175, .120, .051];
    const toeDims = [.048, .120, .049];
    const ankle = posAt(data, spec.ankle);
    const toe = posAt(data, spec.toe);
    const frame=BodyflipSupport.footFrame(data,spec.ankle,spec.toe,spec.side===0?'L':'R');
    const footForward=frame.forward,footUp=frame.up,footSide=frame.side;
    const footCenter=add(add(toe,mul(footForward,-footDims[0]*.5)),mul(footUp,-.006));
    const toeForward=frame.toeForward,toeUp=frame.toeUp,toeSide=frame.toeSide;
    const toeCenter=add(add(toe,mul(toeForward,toeDims[0]*.5)),mul(toeUp,-.006));
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
    if (!swordMesh || data.hideSword) return;
    const hand = nameToIndex.get(swordMesh.hand_node || "hand_r");
    if (hand === undefined) return;
    const handPosition = posAt(data, hand);
    const handAxes = [axisAt(data, hand, 0), axisAt(data, hand, 1), axisAt(data, hand, 2)];
    // Fixed sword topology/materials are prepared once; transform each unique vertex once.
    if(!this.swordCache){
      const local=new Float32Array(swordMesh.vertices.length),normal=new Float32Array(swordMesh.triangles.length),colors=new Float32Array(swordMesh.triangles.length);
      for(let i=0;i<local.length/3;i++)local.set(this.swordLocalToWorld(this.swordVertex(i),[0,0,0],[[1,0,0],[0,1,0],[0,0,1]]),i*3);
      const vertex=i=>Array.from(local.subarray(i*3,i*3+3));
      for(let t=0;t<swordMesh.triangles.length;t+=3){const ids=[swordMesh.triangles[t],swordMesh.triangles[t+1],swordMesh.triangles[t+2]],p=ids.map(vertex);normal.set(normalize(cross(sub(p[1],p[0]),sub(p[2],p[0]))),t);colors.set(ids.some(i=>swordMesh.bladeMask[i])?[.86,.93,.98]:[.52,.24,.07],t);}
      this.swordCache={local,normal,colors,world:new Float32Array(local.length)};
    }
    const {local,normal,colors,world}=this.swordCache,[x,y,z]=handAxes;
    for(let i=0;i<local.length;i+=3)for(let k=0;k<3;k++)world[i+k]=handPosition[k]+x[k]*local[i]+y[k]*local[i+1]+z[k]*local[i+2];
    for(let t=0;t<swordMesh.triangles.length;t+=3){
      const nx=x[0]*normal[t]+y[0]*normal[t+1]+z[0]*normal[t+2],ny=x[1]*normal[t]+y[1]*normal[t+1]+z[1]*normal[t+2],nz=x[2]*normal[t]+y[2]*normal[t+1]+z[2]*normal[t+2];
      for(let k=0;k<3;k++){const i=swordMesh.triangles[t+k]*3;target.push(world[i],world[i+1],world[i+2],nx,ny,nz,colors[t],colors[t+1],colors[t+2]);}
    }
  }

  legSegments() {
    return ['l','r'].flatMap(side=>[[`thigh_${side}`,`calf_${side}`,.083],[`calf_${side}`,`foot_${side}`,.062]]);
  }

  addLeg(mesh, data, side, color) {
    const suffix=side.toLowerCase();
    for(const [a,b,radius] of this.legSegments().filter(([a])=>a.endsWith('_'+suffix))){
      this.capsule(mesh,posAt(data,nameToIndex.get(a)),posAt(data,nameToIndex.get(b)),radius,color,18,6);
    }
    const boxes=this.footBoxes(data,{ankle:nameToIndex.get('foot_'+suffix),toe:nameToIndex.get('ball_'+suffix),side:side==='L'?0:1});
    this.box(mesh,boxes.foot,color);this.box(mesh,boxes.toe,color);
  }

  addBody(mesh, data) {
    const bodyColor = data.tint || [.91, .49, .25];
    if (data.skeleton) {
      for (let j = 1; j < parents.length; j++) {
        const parent = parents[j];
        if (parent < 0 || (data.upperOnly && (!data.upper[j] || !data.upper[parent]))) continue;
        this.capsule(mesh, posAt(data, parent), posAt(data, j), .008, bodyColor, 8, 2);
        this.capsule(mesh, posAt(data, j), posAt(data, j), .014, bodyColor, 8, 2);
      }
      this.addSword(mesh, data);
      return;
    }
    // Center the hip volume on the two thigh sockets; keep the pelvis orientation.
    const pelvis = nameToIndex.get("pelvis");
    if (pelvis !== undefined) {
      const up = axisAt(data, pelvis, 0);
      this.box(mesh, {
        center: nameToIndex.has("thigh_l") && nameToIndex.has("thigh_r")
          ? mul(add(posAt(data, nameToIndex.get("thigh_l")), posAt(data, nameToIndex.get("thigh_r"))), .5)
          : posAt(data, pelvis),
        forward: axisAt(data, pelvis, 1), side: axisAt(data, pelvis, 2), up,
        dims: [.170, .280, .130],
      }, bodyColor.map(v => v * .82));
    }
    const defs = [
      ["pelvis", "spine_01", .125], ["spine_01", "spine_02", .135], ["spine_02", "spine_03", .145],
      ["spine_03", "spine_04", .145], ["spine_04", "spine_05", .135], ["spine_05", "neck_01", .085],
      ["neck_02", "head", .100],
      ["clavicle_l", "upperarm_l", .055], ["upperarm_l", "lowerarm_l", .058], ["lowerarm_l", "hand_l", .048],
      ["clavicle_r", "upperarm_r", .055], ["upperarm_r", "lowerarm_r", .058], ["lowerarm_r", "hand_r", .048],
      ["pelvis", "thigh_l", .095], ["pelvis", "thigh_r", .095], ...this.legSegments(),
    ].map(([a, b, r]) => ({ a: nameToIndex.get(a), b: nameToIndex.get(b), aName: a, bName: b, r }))
      .filter(item => item.a !== undefined && item.b !== undefined);
    const spineNames = new Set(["pelvis", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05", "neck_01"]);
    for (const volume of defs) {
      if (data.upperOnly && (!data.upper[volume.a] || !data.upper[volume.b])) continue;
      const isHipBridge = volume.aName === "pelvis" && (volume.bName === "thigh_l" || volume.bName === "thigh_r");
      const isHead = volume.aName === "neck_02" && volume.bName === "head";
      const isSpine = spineNames.has(volume.aName) && spineNames.has(volume.bName);
      if (isHipBridge || isHead || isSpine) continue;
      const marked=data.bicolor&&/^(upperarm|lowerarm|thigh|calf)_[lr]$/.test(volume.aName);
      // Match the underlying tessellation/frame to the reused half-shell so its
      // 0.8 mm offset stays outside every facet, including the rounded caps.
      this.capsule(mesh, posAt(data, volume.a), posAt(data, volume.b), volume.r, bodyColor,marked?20:18,marked?5:6,marked?this.limbTintAxis(data,volume.a,volume.b):null);
      if(marked)this.limbLongAxisHalf(mesh,data,volume.a,volume.b,volume.r,1);
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
        forward: mul(axisAt(data, neck1, 1), -1),
        side: axisAt(data, neck1, 2),
        up: axisAt(data, neck1, 0),
      }, bodyColor);
    }
    if (headSpec) this.capsule(mesh, headSpec.lower, headSpec.upper, headSpec.radius, bodyColor, 16, 5);

    const handSpecs = [
      { hand: nameToIndex.get("hand_l"), lower: nameToIndex.get("lowerarm_l"), side: 0 },
      { hand: nameToIndex.get("hand_r"), lower: nameToIndex.get("lowerarm_r"), side: 1 },
    ].filter(spec => spec.hand !== undefined && spec.lower !== undefined);
    for (const spec of handSpecs) this.box(mesh, this.handBox(data, spec), bodyColor, data.bicolor ? [1, .82, .06] : null);

    const footSpecs = [
      { ankle: nameToIndex.get("foot_l"), toe: nameToIndex.get("ball_l"), side: 0 },
      { ankle: nameToIndex.get("foot_r"), toe: nameToIndex.get("ball_r"), side: 1 },
    ].filter(spec => spec.ankle !== undefined && spec.toe !== undefined);
    for (const spec of data.upperOnly ? [] : footSpecs) {
      const boxes = this.footBoxes(data, spec);
      const color = bodyColor;
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
    this.bufferCapacity ||= new Map();const bytes=values.length*4;
    if((this.bufferCapacity.get(buffer)||0)<bytes){const capacity=Math.max(bytes, (this.bufferCapacity.get(buffer)||0)*2);gl.bufferData(gl.ARRAY_BUFFER,capacity,gl.DYNAMIC_DRAW);this.bufferCapacity.set(buffer,capacity);}
    gl.bufferSubData(gl.ARRAY_BUFFER,0,values.view());
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
    const rect = this.rect;
    const dpr = this.pixelRatio || globalThis.devicePixelRatio || 1;
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

    const {eye,target,forward,right,up,targetDepth,focalCss}=BodyflipCamera.view(cameraState,sharedRoot,rect.height);
    const view = this.lookAt(eye, target, [0, 1, 0]);
    const projection = this.perspective(45 * Math.PI / 180, width / height, Math.max(.02,targetDepth/10000), Math.max(60,targetDepth*4));
    const viewProjection = this.matrixMultiply(projection, view);
    this.viewProjection = viewProjection;
    this.viewCamera = {eye, target, forward, right, up, focalCss, targetDepth};

    gl.useProgram(this.program);
    gl.uniformMatrix4fv(this.locations.viewProjection, false, viewProjection);
    gl.uniform3fv(this.locations.camera, eye);
    gl.uniform1f(this.locations.opacity, 1);
    gl.uniform3fv(this.locations.lightDirection, [-.58, .78, -.24]);
    gl.uniform3fv(this.locations.fogColor, [.078, .096, .128]);
    gl.uniform1f(this.locations.fogNear, Math.max(1.2, targetDepth * .68));
    gl.uniform1f(this.locations.fogFar, targetDepth * 1.55 + 3.5);

    const mesh = this.meshStream || (this.meshStream = new LabVertexStream(524288));
    const lines = this.lineStream || (this.lineStream = new LabVertexStream(4096));
    mesh.length = 0; lines.length = 0;
    if (!data.voidScene) {
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
    }
    if (data.ghost) this.addBody(mesh, data.ghost);
    this.addBody(mesh, data);
    // Same final displayed XYZ basis, arrow geometry and depth as Final Harness.
    for (const [enabled, joints, length] of [
      [data.handGizmos, ['hand_l', 'hand_r'], .18],
      [data.lowerarmGizmos, ['lowerarm_l', 'lowerarm_r'], .21],
      [data.upperarmGizmos, ['upperarm_l', 'upperarm_r'], .24]
    ]) {
      if (!enabled) continue;
      for (const name of joints) {
        if (!name.endsWith(data.gizmoSide === 'l' ? '_l' : '_r')) continue;
        const joint = nameToIndex.get(name);
        if (joint === undefined) continue;
        const origin = posAt(data, joint);
        this.capsule(mesh, origin, origin, .018, [1, .92, .28], 12, 5);
        const colors = [[1, .22, .18], [.20, .95, .32], [.22, .48, 1]];
        for (let axis = 0; axis < 3; axis++) this.controllerAxis(mesh, origin, axisAt(data, joint, axis), colors[axis], length);
      }
    }
    this.bindAndDraw(this.meshBuffer, mesh, gl.TRIANGLES);
    this.bindAndDraw(this.lineBuffer, lines, gl.LINES);
  }
}
