"""Reference geometry inspection; no dynamics or policy implied by these images."""
from pathlib import Path
import json
import mujoco
from PIL import Image,ImageDraw

OUT=Path(__file__).resolve().parents[2]/"Saved/Robotics"
def main():
    m=mujoco.MjModel.from_xml_path(str(OUT/"uefn.xml")); d=mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m,d,0); mujoco.mj_forward(m,d)
    panels=[]
    with mujoco.Renderer(m,640,640) as renderer:
        for title,azimuth,elevation in (("Reference · front",90,-8),("Reference · side",0,-8),("Reference · oblique",125,-15)):
            cam=mujoco.MjvCamera(); cam.lookat[:]=[0,0,.95]; cam.distance=2.8
            cam.azimuth=azimuth; cam.elevation=elevation
            renderer.update_scene(d,camera=cam)
            im=Image.fromarray(renderer.render().copy())
            ImageDraw.Draw(im).text((15,15),title,fill="white")
            panels.append(im)
    canvas=Image.new("RGB",(1920,690),(20,25,32))
    for i,im in enumerate(panels): canvas.paste(im,(i*640,0))
    ImageDraw.Draw(canvas).text((15,653),"Original PHAT geometry / effective Jolt mass and inertia · 23 bodies, 22 joints · limits extension pending; not a trained motion",fill="white")
    canvas.save(OUT/"rig-reference.png")
    print(OUT/"rig-reference.png")
if __name__=="__main__": main()
