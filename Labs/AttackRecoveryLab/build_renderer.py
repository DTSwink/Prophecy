"""Adapt a frozen Final Harness renderer; keep its WebGL depth/camera/body geometry."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Renderer anchor changed: {before[:70]}')
    return text.replace(before, after, 1)

def main():
    text = (ROOT / 'frozen/renderer.js').read_text(encoding='utf-8')
    text = text.replace('alpha: false,', 'alpha: false, preserveDrawingBuffer: true,')
    text = replace_once(text, 'if (!swordMesh) return;', 'if (!swordMesh || data.hideSword) return;')
    text = replace_once(text, '    const bodyColor = [.91, .49, .25];', '''    const bodyColor = data.tint || [.91, .49, .25];
    if (data.skeleton) {
      for (let j = 1; j < parents.length; j++) {
        const parent = parents[j];
        if (parent < 0 || (data.upperOnly && (!data.upper[j] || !data.upper[parent]))) continue;
        this.capsule(mesh, posAt(data, parent), posAt(data, j), .008, bodyColor, 8, 2);
        this.capsule(mesh, posAt(data, j), posAt(data, j), .014, bodyColor, 8, 2);
      }
      this.addSword(mesh, data);
      return;
    }''')
    text = replace_once(text, '    for (const volume of defs) {', '    for (const volume of defs) {\n      if (data.upperOnly && (!data.upper[volume.a] || !data.upper[volume.b])) continue;')
    text = replace_once(text, '["pelvis", "spine_02", .205, .215, .115, .120]', '[data.upperOnly ? "spine_01" : "pelvis", "spine_02", .205, .215, .115, .120]')
    text = replace_once(text, '    for (const spec of footSpecs) {', '    for (const spec of data.upperOnly ? [] : footSpecs) {')
    text = replace_once(text, 'spec.side === 0 ? [.20, .72, .88] : [.86, .20, .13]', 'bodyColor')
    text = replace_once(text, 'const color = spec.side === 0 ? [.88, .18, .14] : [.18, .72, .34];', 'const color = bodyColor;')
    text = replace_once(text, '    this.addBody(mesh, data);', '''    if (data.ghost) this.addBody(mesh, data.ghost);
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
    if (data.target) {
      const color = data.floorTarget ? [.97, .70, .30] : [.30, .92, .73];
      this.capsule(mesh, data.target, data.target, .045, color, 16, 4);
      this.line(lines, data.target, [data.target[0], .005, data.target[2]], color);
      this.groundRing(mesh, [data.target[0], .008, data.target[2]], .075, .083, color);
    }''')
    start = text.index('    const headSpec = this.headFrame(data);', text.index('  draw(data, sharedRoot)'))
    end = text.index('    this.bindAndDraw(this.meshBuffer', start)
    text = text[:start] + text[end:]
    # Keep the frozen geometry exactly, but reuse topology and vertex allocations.
    start = text.index('  capsule(target,')
    end = text.index('  controllerAxis(', start)
    text = text[:start] + (ROOT / 'capsule_performance.js').read_text(encoding='utf-8') + text[end:]
    text = replace_once(text, '    const mesh = [];\n    const lines = [];',
        '    const mesh = this.meshStream || (this.meshStream = new LabVertexStream(524288));\n'
        '    const lines = this.lineStream || (this.lineStream = new LabVertexStream(4096));\n'
        '    mesh.length = 0; lines.length = 0;')
    text = replace_once(text, 'new Float32Array(values), gl.DYNAMIC_DRAW', 'values.view(), gl.DYNAMIC_DRAW')
    text = (ROOT / 'renderer_performance.js').read_text(encoding='utf-8') + text
    (ROOT / 'renderer.js').write_text(text, encoding='utf-8')
    print('Built the independent renderer from its frozen source')

if __name__ == '__main__':
    main()
