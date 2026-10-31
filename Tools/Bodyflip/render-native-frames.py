"""Offline PHAT collider sheets from the isolated Unreal agent test.

Uses the captured native shape descriptors and completed physical poses. Does
not touch a viewer, desktop, saved scene, or Unreal asset.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def matrix(q):
    x, y, z, w = np.asarray(q) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def multiply(a, b):
    av, bv = np.asarray(a[:3]), np.asarray(b[:3])
    return np.r_[a[3]*bv+b[3]*av+np.cross(av, bv), a[3]*b[3]-av@bv]


def shape_mesh(shape, body, trim):
    local = shape['local']
    centre = np.array(local['position_cm'], dtype=float)
    rotation = matrix(local['rotation_xyzw'])
    if shape['kind'] == 'box':
        half = np.array(shape['half_extent_cm'], dtype=float)
        if body['name'].startswith('foot_') and trim:
            direction = rotation.T @ body['toe_direction']
            axis = np.argmax(np.abs(direction))
            delta = np.zeros(3)
            delta[axis] = -np.sign(direction[axis])*trim/2
            centre += rotation@delta
            half[axis] -= trim/2
        vertices = np.array([[x, y, z] for x in [-1, 1]
                             for y in [-1, 1] for z in [-1, 1]])*half
        faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5),
                 (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
                 (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    else:
        radius = shape['radius_cm']
        half = shape.get('cylinder_length_cm', 0)/2 if shape['kind'] == 'capsule' else 0
        vertices, faces = [], []
        sectors = 16
        latitudes = [(angle, -half) for angle in np.linspace(-math.pi/2, 0, 6)]
        latitudes += [(angle, half) for angle in np.linspace(0, math.pi/2, 6)]
        for latitude, offset in latitudes:
            for k in range(sectors):
                angle = 2*math.pi*k/sectors
                vertices.append([radius*math.cos(latitude)*math.cos(angle),
                                 radius*math.cos(latitude)*math.sin(angle),
                                 radius*math.sin(latitude)+offset])
        for j in range(len(latitudes)-1):
            for k in range(sectors):
                a = j*sectors+k
                b = j*sectors+(k+1)%sectors
                faces.extend([(a, b, a+sectors), (b, b+sectors, a+sectors)])
        vertices = np.array(vertices)
    return vertices@rotation.T+centre, np.array(faces)


def target_pose(frame, space):
    pose = frame['canonical']['pose']
    turn = np.array([math.sqrt(.5), 0, 0, math.sqrt(.5)])
    rotation = matrix(space['q'])
    points = np.asarray(pose['points'])[:, [0, 2, 1]]*100
    points = (points*np.asarray(space['scale']))@rotation.T+space['p']
    quaternions = []
    for q in pose['q']:
        native = multiply(turn, q)*[-1, 1, -1, 1]
        quaternions.append(multiply(space['q'], native))
    return {'points': points, 'q': quaternions}


def main():
    args = argparse.ArgumentParser()
    args.add_argument('report', type=Path)
    args.add_argument('--frames', type=int, default=8)
    args.add_argument('--indices', help='Comma-separated capture indices for a dense boundary review')
    args.add_argument('--target-only', action='store_true', help='Render planned colliders without implying a physical capture')
    options = args.parse_args()
    data = json.loads(options.report.read_text(encoding='utf-8-sig'))
    profile, frames = data['nativeRigProfile'], data['frames']
    geometry = []
    for body in profile['bodies']:
        index = data['names'].index(body['name'])
        colour = np.array([.10, .76, .82] if body['name'].endswith('_l') else [.91, .46, .19])
        for shape in body['shapes']:
            mesh, faces = shape_mesh(shape, body, profile.get('foot_front_trim_cm', 0))
            geometry.append((index, mesh, faces, colour))
    selected = ([int(x) for x in options.indices.split(',')] if options.indices else
                np.linspace(0, len(frames)-1, min(len(frames), options.frames)).round().astype(int))
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 15)
    small = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 12)
    width, height = 250, 310
    views = [((4, 6, 2), 'target'), ((6, 0, 1.5), 'target')] if options.target_only else [
        ((4, 6, 2), 'target'), ((4, 6, 2), 'actual'), ((6, 0, 1.5), 'target'), ((6, 0, 1.5), 'actual')]
    sheet = Image.new('RGB', (width*len(selected), height*len(views)+35), '#101722')
    draw = ImageDraw.Draw(sheet)
    label = 'Planned native PHAT colliders (no physics capture)' if options.target_only else 'Actual native PHAT colliders | target / completed body pose | fixed scale'
    draw.text((10, 7), label, font=font, fill='white')
    for row, (view, kind) in enumerate(views):
        towards = np.array(view, dtype=float); towards /= np.linalg.norm(towards)
        right = np.cross([0, 0, 1], towards); right /= np.linalg.norm(right)
        up = np.cross(towards, right)
        for col, index in enumerate(selected):
            frame = frames[index]
            pose = frame['actualPose'] if kind == 'actual' else target_pose(frame, data['worldSpace'])
            origin = np.asarray(frame['carrierRoot'])+[0, 0, 90]
            triangles, colours = [], []
            for bone, mesh, faces, colour in geometry:
                world = mesh@matrix(pose['q'][bone]).T+pose['points'][bone]
                triangles.extend(world[faces]); colours.extend([colour]*len(faces))
            triangles = np.array(triangles); colours = np.array(colours)
            normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
            normals /= np.maximum(1e-10, np.linalg.norm(normals, axis=1))[:, None]
            light = np.array([-.3, .4, .85]); light /= np.linalg.norm(light)
            shades = .36+.64*np.maximum(0, normals@light)
            colours = (np.clip(colours*shades[:, None], 0, 1)*255).astype(np.uint8)
            local = triangles-origin
            xy = np.stack((local@right, -local@up), axis=-1)*.94+[width/2, height*.52]
            depth = (local@towards).mean(axis=1)
            cell = Image.new('RGB', (width, height), '#151e2b'); pen = ImageDraw.Draw(cell)
            floor = data['floor']; floor_rotation = matrix(floor['q'])
            half = np.asarray(floor['scale'])*50
            def screen(world):
                delta = world-origin
                return tuple(np.array([delta@right, -delta@up])*.94+[width/2, height*.52])
            for axis in (0, 1):
                other = 1-axis
                for value in np.arange(-half[axis], half[axis]+1, 100):
                    ends = []
                    for sign in (-1, 1):
                        point = np.array([0., 0., half[2]])
                        point[axis], point[other] = value, sign*half[other]
                        ends.append(screen(floor_rotation@point+floor['p']))
                    pen.line(ends, fill='#30465e')
            for triangle in np.argsort(depth):
                pen.polygon([tuple(v) for v in xy[triangle]], fill=tuple(colours[triangle]))
            pen.text((7, 7), f"{kind} F{round(frame['time']*60)} {frame['canonical']['phase']}", font=small, fill='white')
            sheet.paste(cell, (col*width, 35+row*height))
    output = options.report.with_suffix('.png'); sheet.save(output)
    print(output)


if __name__ == '__main__':
    main()
