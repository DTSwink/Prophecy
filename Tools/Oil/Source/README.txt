MilkBottle.glb — Milk Bottle by mokbulsd
https://www.fab.com/listings/adc6b678-4635-4c62-a686-7771d1e8e2ca
Downloaded October 24, 2026 under the Fab Standard License.
User explicitly approved accepting the Fab EULA for this download.
https://www.fab.com/eula
SHA256 31d030fa5a61564c2a628446ff5fe733f20049a8d48f52788945484cd50c3a73

This is third-party licensed content, not project-owned source code.
Keep its license restrictions when sharing project files. Do not publish the
source or generated assets as a standalone asset pack.

PrepareBottle.py uses this small source file to regenerate the geometry.
The exterior is normalized to 26cm high, upright and bottom-centered; the
separately exported cork is seated on the mouth. A hidden planar neck ring
is closed and an inner glass cavity is baked before fracturing into 19 closed
Voronoi pieces plus the intact cork. Original UVs are carried through the
boolean operations. Final triangle winding is converted for Unreal only after
Manifold volume/fracture operations. BottleMaterials.py supplies editable glass,
cork and liquid materials with FragmentOpacity for fading. Glass uses controlled
screen-space refraction; it is not physically ray-traced glass.
Offline dependency: numpy and manifold3d==3.5.4 (no runtime dependency).

OilStudio.hdr is a small procedural project-generated softbox environment from
MakeStudioEnvironment.py, independent of the licensed Fab source asset.
