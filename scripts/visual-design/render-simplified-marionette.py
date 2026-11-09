"""Build and render the simplified character locally with Blender's Python.

See docs/visual-design/experiments/simplified-marionette.md. No add-ons needed.
"""

import argparse
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'data/visual-design/simplified-marionette')
parser.add_argument('--resolution', type=int, default=1600, help='Portrait render width')
parser.add_argument('--samples', type=int, default=64)
parser.add_argument('--preview', action='store_true')
parser.add_argument('--views', action='store_true', help='Also render front, side and back')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if args.resolution < 64 or args.samples < 1:
    parser.error('Resolution must be at least 64 and samples must be positive')
args.output = args.output.resolve()
args.output.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.resolution
scene.render.resolution_y = round(args.resolution * 1.25)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = -.25
scene.world = bpy.data.worlds.new('Neutral studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.63, .56, .52, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35


def material(name, color, rough=.32, metal=0, coat=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = .2
    return mat


ivory = material('Warm glazed porcelain', (.88, .67, .49), .24, coat=.32)
rose = material('Painted lips and nails', (.64, .012, .09), .28, coat=.23)
pink = material('Hot pink satin', (.66, .012, .095), .32, coat=.18)
brown = material('Chestnut hair', (.075, .023, .015), .43, coat=.07)
brown.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = .28
bodice = material('Chocolate corset', (.065, .019, .014), .44)
cream = material('Warm ivory satin skirt', (.88, .64, .43), .4, coat=.08)
gold = material('Gold buttons', (.70, .40, .09), .26, metal=.65)
white = material('Eye ivory', (.94, .91, .80), .2, coat=.3)
black = material('Pupils and eyeliner', (.009, .005, .004), .28)
iris = material('Olive gold iris', (.27, .23, .032), .24, coat=.4)
iris_edge = material('Iris dark edge', (.054, .044, .009), .3)
iris_streak = material('Iris amber flecks', (.47, .31, .057), .3)
shadow = material('Joint recess', (.17, .072, .04), .4)
blush = material('Ear blush', (.70, .29, .22), .4)
floor_mat = material('Warm studio backdrop', (.64, .55, .48), .78)
base_mat = material('Ivory plinth', (.76, .65, .54), .36)

# Smooth pink tips are a material gradient, not separate hair strands.
hair_tip = brown.copy()
hair_tip.name = 'Chestnut to raspberry hair tips'
nt = hair_tip.node_tree
geo = nt.nodes.new('ShaderNodeNewGeometry')
sep = nt.nodes.new('ShaderNodeSeparateXYZ')
remap = nt.nodes.new('ShaderNodeMapRange')
remap.inputs['From Min'].default_value = 4.38
remap.inputs['From Max'].default_value = 5.98
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = .1
ramp.color_ramp.elements[0].color = (.66, .012, .095, 1)
ramp.color_ramp.elements[1].position = .82
ramp.color_ramp.elements[1].color = (.075, .023, .015, 1)
nt.links.new(geo.outputs['Position'], sep.inputs[0])
nt.links.new(sep.outputs['Z'], remap.inputs[0])
nt.links.new(remap.outputs[0], ramp.inputs[0])
nt.links.new(ramp.outputs[0], nt.nodes['Principled BSDF'].inputs['Base Color'])

face_mat = ivory.copy()
face_mat.name = 'Porcelain with soft painted cheeks'
nt = face_mat.node_tree
geo = nt.nodes.new('ShaderNodeNewGeometry')
near = nt.nodes.new('ShaderNodeMath'); near.operation = 'MINIMUM'
for i, sign in enumerate((-1, 1)):
    dist = nt.nodes.new('ShaderNodeVectorMath'); dist.operation = 'DISTANCE'
    dist.inputs[1].default_value = (sign*.43, -.48, 5.07)
    nt.links.new(geo.outputs['Position'], dist.inputs[0])
    nt.links.new(dist.outputs['Value'], near.inputs[i])
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = .025
ramp.color_ramp.elements[0].color = (.77, .35, .28, 1)
ramp.color_ramp.elements[1].position = .22
ramp.color_ramp.elements[1].color = (*ivory.diffuse_color[:3], 1)
ramp.color_ramp.interpolation = 'EASE'
nt.links.new(near.outputs[0], ramp.inputs[0])
nt.links.new(ramp.outputs[0], nt.nodes['Principled BSDF'].inputs['Base Color'])


def collection(name):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


body = collection('01 Porcelain body and ball joints')
face = collection('02 Face and eyes')
hair = collection('03 Broad hair clumps and bows')
clothes = collection('04 Simple corset and two skirt tiers')
studio = collection('05 Studio and cameras')
active = body


def put(obj, name, mat):
    obj.name = name
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    active.objects.link(obj)
    obj.data.materials.append(mat)
    if obj.type == 'MESH':
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def sphere(name, pos, scale, mat, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=24, location=pos)
    obj = put(bpy.context.object, name, mat)
    obj.scale = scale
    return obj


def mesh(name, verts, faces, mat, sub=1):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    active.objects.link(obj)
    data.materials.append(mat)
    for poly in data.polygons:
        poly.use_smooth = True
    if sub:
        mod = obj.modifiers.new('Smooth silhouette', 'SUBSURF')
        mod.levels = sub
        mod.render_levels = sub
    return obj


def tube(name, points, radius, mat, cyclic=False):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.bevel_depth = radius
    data.bevel_resolution = 3
    spline = data.splines.new('POLY')
    spline.points.add(len(points)-1)
    for point, co in zip(spline.points, points):
        point.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, data)
    active.objects.link(obj)
    data.materials.append(mat)
    return obj


def cubic(points, t):
    a, b, c, d = map(Vector, points)
    return (1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d


def lock(name, controls, radius, mat, depth=.7):
    """One broad, tapered low-resolution sweep; editable subdivision cage."""
    verts, faces = [], []
    steps, sides = 24, 12
    for j in range(steps+1):
        t = j/steps
        p = cubic(controls, t)
        tangent = cubic(controls, min(1, t+.001))-cubic(controls, max(0, t-.001))
        tangent.normalize()
        u = tangent.cross(Vector((0, 1, 0))).normalized()
        v = tangent.cross(u).normalized()
        width = radius*(.33+.85*math.sin(math.pi*t)**.72)*(1-.99*t**5)
        for i in range(sides):
            a = math.tau*i/sides
            verts.append(p+u*width*math.cos(a)+v*width*depth*math.sin(a))
    for j in range(steps):
        for i in range(sides):
            a=j*sides+i; b=j*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces += [tuple(reversed(range(sides))), tuple(steps*sides+i for i in range(sides))]
    return mesh(name, verts, faces, mat, 2)


def segment(name, start, end, widths, mat):
    a, b = Vector(start), Vector(end)
    direction = (b-a).normalized()
    a -= direction*.035
    b += direction*.035
    rotation = Vector((0, 0, 1)).rotation_difference((b-a).normalized())
    verts, faces = [], []
    n = 24
    profile = [(0, widths[0]), (.035, widths[0])]
    profile += [(j/(len(widths)-1), r) for j,r in enumerate(widths) if 0<j<len(widths)-1]
    profile += [(.965, widths[-1]), (1, widths[-1])]
    for t, radius in profile:
        center = a+(b-a)*t
        for i in range(n):
            t = math.tau*i/n
            verts.append(center+rotation@Vector((radius*math.cos(t), radius*math.sin(t), 0)))
    for j in range(len(profile)-1):
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n
            faces.append((a,b,b+n,a+n))
    faces += [tuple(reversed(range(n))), tuple((len(profile)-1)*n+i for i in range(n))]
    return mesh(name, verts, faces, mat, 2)


def joint(name, pos, radius):
    sphere(name, pos, (radius,)*3, ivory)
    pts = [(pos[0]+radius*.97*math.cos(t), pos[1]+.025, pos[2]+radius*.97*math.sin(t))
           for t in [i*math.tau/64 for i in range(64)]]
    tube(name+' seam', pts, .006, shadow, True)


def fuse(name, parts, voxel):
    """Unite hand/foot forms so fingers are continuous with the palm."""
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new('Unified porcelain surface', 'REMESH')
    mod.mode = 'VOXEL'; mod.voxel_size = voxel
    bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = obj.modifiers.new('Soften joins', 'SMOOTH'); mod.factor=.8; mod.iterations=5
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons:
        poly.use_smooth=True
    mod = obj.modifiers.new('Surface finish', 'SUBSURF'); mod.levels=1
    return obj


# Slim body, large head, neutral A-pose. Exposed joints are separate parts.
sphere('Torso', (0, 0, 3.79), (.34, .21, .49), ivory)
sphere('Shoulder chest', (0, 0, 4.10), (.47, .23, .19), ivory)
segment('Neck', (0, 0, 4.12), (0, 0, 4.62), [.20,.17,.145,.16,.21], ivory)
for sign, label in ((-1, 'L'), (1, 'R')):
    x=sign*.29
    joint(label+' hip', (x, 0, 2.40), .19)
    segment(label+' thigh', (x, 0, 2.40), (x, 0, 1.40), [.17,.22,.23,.18,.13], ivory)
    joint(label+' knee', (x, -.015, 1.32), .145)
    segment(label+' shin', (x, 0, 1.23), (x, 0, .47), [.125,.17,.155,.10,.089], ivory)
    joint(label+' ankle', (x, 0, .42), .105)
    parts=[sphere('Foot blank', (x, -.12, .21), (.15,.26,.145), ivory)]
    for i in range(5):
        tx=x+sign*(-.102+i*.05)
        ty=-.36+.012*i
        parts.append(sphere('Toe', (tx, ty, .15), (.043-i*.003,.075-i*.005,.053), ivory, 24))
    fuse(label+' continuous foot', parts, .011)
    for i in range(5):
        sphere(label+' toenail', (x+sign*(-.102+i*.05), -.385+.012*i, .187), (.025-i*.002,.028,.009), rose, 20)
    shoulder=(sign*.58,0,4.08); elbow=(sign*.87,-.02,3.52); wrist=(sign*1.18,-.08,3.03)
    joint(label+' shoulder', shoulder, .16)
    segment(label+' upper arm', (sign*.63,0,3.99), (sign*.83,-.02,3.61), [.13,.142,.116,.097], ivory)
    joint(label+' elbow', elbow, .112)
    segment(label+' forearm', (sign*.91,-.03,3.44), (sign*1.14,-.075,3.10), [.098,.112,.085,.064], ivory)
    joint(label+' wrist', wrist, .079)
    palm=sphere('Palm blank', (sign*1.235,-.09,2.89), (.102,.062,.15), ivory)
    palm.rotation_euler.y=-sign*.25
    parts=[palm]
    for i in range(4):
        start=Vector((sign*(1.17+i*.054),-.09,2.82))
        end=Vector((sign*(1.19+i*.060),-.12,2.60+.037*abs(i-1)))
        finger=sphere('Finger blank', (start+end)/2, (.025,.028,(start-end).length/2+.02), ivory,24)
        finger.rotation_euler=(end-start).to_track_quat('Z','Y').to_euler()
        parts.append(finger)
    thumb=sphere('Thumb blank',(sign*1.135,-.12,2.84),(.04,.042,.10),ivory,24)
    thumb.rotation_euler.y=sign*.42
    parts.append(thumb)
    fuse(label+' hand, continuous fingers',parts,.008)
    for i in range(4):
        sphere(label+' fingernail',(sign*(1.19+i*.060),-.144,2.63+.037*abs(i-1)),(.017,.008,.024),rose,20)

# A shaped head and conforming eye patches avoid detached sphere-like eyes.
active=face

def jaw_width(z):
    nz=(z-5.28)/.82
    return .77*(1 if nz>-.2 else 1-.12*((-nz-.2)/.8))


def face_y(x,z):
    return -.60*math.sqrt(max(.001,1-(x/jaw_width(z))**2-((z-5.28)/.82)**2))


verts=[]; faces=[]
for j in range(49):
    theta=math.pi*j/48
    z=5.28+.82*math.cos(theta)
    for i in range(96):
        phi=math.tau*i/96
        verts.append((jaw_width(z)*math.sin(theta)*math.cos(phi),.60*math.sin(theta)*math.sin(phi),z))
for j in range(48):
    for i in range(96):
        a=j*96+i; b=j*96+(i+1)%96
        faces.append((a,b,b+96,a+96))
mesh('Porcelain face',verts,faces,face_mat)
for sign,label in ((-1,'L'),(1,'R')):
    sphere(label+' ear',(sign*.71,.015,5.12),(.13,.09,.18),ivory)
    sphere(label+' inner ear',(sign*.758,-.05,5.12),(.055,.026,.103),blush)
    cx=sign*.31; cz=5.37
    verts=[]; faces=[]
    for j in range(13):
        r=j/12
        for i in range(64):
            a=i*math.tau/64
            x=cx+.237*r*math.cos(a)
            z=cz+.183*r*math.sin(a)*(.83+.17*abs(math.sin(a)))
            verts.append((x,face_y(x,z)-.014-.045*(1-r*r),z))
    for j in range(12):
        for i in range(64):
            a=j*64+i; b=j*64+(i+1)%64
            faces.append((a,b,b+64,a+64))
    mesh(label+' almond eye',verts,faces,white)
    ey=face_y(cx,cz)-.067
    sphere(label+' iris edge',(cx,ey,cz),(.167,.020,.173),iris_edge)
    sphere(label+' olive iris',(cx,ey-.014,cz),(.156,.018,.162),iris)
    for i in range(32):
        a=i*math.tau/32
        pts=[]
        for k in range(5):
            r=.070+k*.019
            pts.append((cx+r*math.cos(a),ey-.031+.009*(r/.13)**2,cz+1.06*r*math.sin(a)))
        tube(label+' iris pigment',pts,.0025,iris_streak)
    sphere(label+' pupil',(cx,ey-.033,cz),(.076,.012,.086),black)
    sphere(label+' catchlight',(cx-.040,ey-.046,cz+.055),(.026,.007,.029),white,24)
    pts=[]
    for i in range(49):
        a=i*math.pi/48
        x=cx+.237*math.cos(a); z=cz+.183*math.sin(a)*(.83+.17*math.sin(a))
        pts.append((x,face_y(x,z)-.022,z))
    tube(label+' upper liner',pts,.013,black)
    for i in range(4):
        a=.25+i*.24 if sign==1 else math.pi-.25-i*.24
        x=cx+.236*math.cos(a); z=cz+.183*math.sin(a)
        pts=[(x,face_y(x,z)-.03,z),(x+sign*.026,face_y(x,z)-.044,z+.035),(x+sign*.038,face_y(x,z)-.04,z+.055)]
        tube(label+' lash',pts,.007,black)
    pts=[]
    for i in range(33):
        t=i/32; x=cx-.18+.36*t; z=5.64+.047*math.sin(math.pi*t)
        pts.append((x,face_y(x,z)-.021,z))
    tube(label+' brow',pts,.018,brown)
sphere('Small nose bridge',(0,-.584,5.19),(.058,.035,.105),ivory)
sphere('Button nose',(0,-.628,5.105),(.068,.057,.054),ivory)
for sign in (-1,1):
    sphere('Nostril',(sign*.035,-.666,5.084),(.012,.008,.008),blush,20)
    lip=sphere('Cupid bow',(sign*.034,-.552,4.96),(.057,.025,.023),rose)
    lip.rotation_euler.y=sign*.20
sphere('Lower lip',(0,-.55,4.925),(.074,.027,.027),rose)
tube('Lip seam',[(-.075,-.56,4.943),(0,-.579,4.940),(.075,-.56,4.943)],.004,shadow)

# Smooth scalp, six broad fringe sections, three clumps per pigtail.
active=hair
verts=[]; faces=[]
for j in range(25):
    for i in range(96):
        phi=i*math.tau/96
        theta=j/24*(1.78+.65*math.sin(phi))
        verts.append((.795*math.sin(theta)*math.cos(phi),.63*math.sin(theta)*math.sin(phi),5.30+.87*math.cos(theta)))
for j in range(24):
    for i in range(96):
        a=j*96+i; b=j*96+(i+1)%96
        faces.append((a,b,b+96,a+96))
mesh('Smooth hair cap',verts,faces,brown)
for sign,label in ((-1,'L'),(1,'R')):
    for i in range(3):
        # Broad curved panels sit over the scalp; a colored region is part
        # of each panel's material assignment, not floating strand geometry.
        verts=[]; faces=[]
        center_phi=-math.pi/2+sign*(.17+i*.38)
        for j in range(25):
            t=j/24
            theta=.15+(1.12+i*.06)*t
            sweep=-sign*.19*math.sin(math.pi*t)
            for k in range(9):
                u=k/8*2-1
                halfwidth=.23*(1-.75*t**9)
                phi=center_phi+sweep+u*halfwidth
                lift=.022+.025*math.cos(u*math.pi/2)
                x=(.795+lift)*math.sin(theta)*math.cos(phi)
                y=(.63+lift)*math.sin(theta)*math.sin(phi)
                z=5.30+(.87+lift)*math.cos(theta)+.045*u*u*t**4
                verts.append((x,y,z))
        for j in range(24):
            for k in range(8):
                a=j*9+k
                faces.append((a,a+1,a+10,a+9))
        obj=mesh(label+' swept fringe panel '+str(i+1),verts,faces,brown,2)
        obj.data.materials.append(pink)
        for poly in obj.data.polygons:
            j,k=divmod(poly.index,8)
            if k in (2,3) and j>6:
                poly.material_index=1
        obj.modifiers.new('Rounded panel edge','SOLIDIFY').thickness=.025
    clumps=[
        [(sign*.79,.16,5.94),(sign*1.60,.20,6.04),(sign*1.55,.16,4.95),(sign*1.24,.05,4.71)],
        [(sign*.82,-.01,5.96),(sign*1.30,-.13,5.71),(sign*.99,-.28,4.68),(sign*1.39,-.16,4.45)],
        [(sign*.88,.34,5.93),(sign*1.70,.43,5.60),(sign*1.72,.37,4.69),(sign*1.48,.22,4.84)],
    ]
    for i,controls in enumerate(clumps):
        lock(label+' pigtail clump '+str(i+1),controls,.265,hair_tip,.75)
    center=(sign*.77,-.12,6.00)
    sphere(label+' bow knot',center,(.095,.09,.095),pink)
    for k in (-1,1):
        loop=sphere(label+' bow loop',(center[0]+k*.16,center[1]+.012,center[2]+.12),(.20,.075,.112),pink)
        loop.rotation_euler.y=-k*.65
    lock(label+' bow tail',[(center[0],-.14,5.99),(center[0]+sign*.12,-.23,5.90),(center[0]+sign*.20,-.20,5.85),(center[0]+sign*.24,-.17,5.80)],.12,pink,.33)

active=clothes

def corset(t,a,offset=0):
    r=.33+.15*(2*t-1)**2+.025*t
    z=3.20+.80*t-.105*(1-t)**7*max(0,-math.sin(a))**6
    z+=.06*t**6*abs(math.sin(2*a))
    return ((r+offset)*math.cos(a),(r*.64+offset)*math.sin(a),z)


def surface(name,fn,mat,rings=16,sides=96):
    verts=[fn(j/rings,i*math.tau/sides) for j in range(rings+1) for i in range(sides)]
    faces=[]
    for j in range(rings):
        for i in range(sides):
            a=j*sides+i; b=j*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    obj=mesh(name,verts,faces,mat,2)
    obj.modifiers.new('Fabric shell thickness','SOLIDIFY').thickness=.018
    return obj


surface('Smooth corset shell',corset,bodice)
for t in (0,1):
    tube('Pink corset edge',[corset(t,i*math.tau/128,.014) for i in range(128)],.023,pink,True)
for sign in (-1,1):
    tube('Front pink seam',[corset(i/48,-math.pi/2+sign*.48,.018) for i in range(49)],.022,pink)
for t in (.22,.50,.78):
    x,y,z=corset(t,-math.pi/2,.025)
    sphere('Gold button',(x,y-.014,z),(.055,.027,.055),gold)
# Three broad, shallow crossed strips follow the back of the shell.
for i in range(3):
    for sign in (-1,1):
        tube('Back pink crossing',[corset(.16+i*.23+.23*j/24, math.pi/2+sign*.40*(1-2*j/24),.018) for j in range(25)],.018,pink)


def skirt(t,a,layer):
    top,bottom,rt,rb=(3.22,2.62,.37,.88) if layer==0 else (2.91,2.23,.50,1.00)
    r=rt+(rb-rt)*t**1.5+.046*t*math.cos(10*a)
    return (r*math.cos(a),r*.78*math.sin(a),top+(bottom-top)*t+.018*t*t*math.cos(10*a))


for layer in (1,0):
    surface('Lower clean skirt tier' if layer else 'Upper clean skirt tier',lambda t,a:skirt(t,a,layer),cream)

# Quiet neutral studio, high enough contrast to show the porcelain silhouette.
active=studio
bpy.ops.mesh.primitive_cylinder_add(vertices=128,radius=1.79,depth=.14,location=(0,0,0))
obj=put(bpy.context.object,'Display base',base_mat)
mod=obj.modifiers.new('Rounded base rim','BEVEL'); mod.width=.04; mod.segments=4
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.06))
put(bpy.context.object,'Studio floor',floor_mat)


def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def light(name,pos,energy,size,color):
    data=bpy.data.lights.new(name,'AREA'); data.energy=energy; data.shape='DISK'; data.size=size; data.color=color
    obj=bpy.data.objects.new(name,data); studio.objects.link(obj); obj.location=pos; aim(obj,(0,0,3.4))


light('Large key',(-4,-6,9),850,5,(1,.87,.77))
light('Soft fill',(4,-4,6),600,4,(.85,.91,1))
light('Hair rim',(1,4,8),1000,3,(1,.80,.74))
light('Top softbox',(-3,1,9),500,3,(1,.92,.84))


def camera(name,pos,target,scale):
    data=bpy.data.cameras.new(name); data.type='ORTHO'; data.ortho_scale=scale; data.lens=65
    obj=bpy.data.objects.new(name,data); studio.objects.link(obj); obj.location=pos; aim(obj,target)
    return obj


hero=camera('Hero',(7,-24,9),(0,0,3.15),7.35)
front=camera('Front',(0,-24,3.15),(0,0,3.15),7.10)
side=camera('Side',(24,0,3.15),(0,0,3.15),7.10)
back=camera('Back',(0,24,3.15),(0,0,3.15),7.10)
camera('Face detail',(1.5,-20,6.9),(0,-.05,5.25),2.7)
scene.camera=hero
scene['Reference']='visual design/simple character sheet.png'
scene['Scope']='Editable static interpretation. No armature, animation, engineered joints or printability validation.'
scene['Rebuild']='blender -b --factory-startup --python scripts/visual-design/render-simplified-marionette.py -- --views'
scene['Design']='Six broad pigtail clumps, six fringe sections, smooth two-tier skirt and continuous fingers.'
scene.render.filepath=str(args.output/'simplified-marionette.png')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_end=300
bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'simplified-marionette.blend'),compress=True)
if args.preview:
    scene.render.resolution_percentage=40
    scene.cycles.samples=16
    scene.render.filepath=str(args.output/'simplified-marionette-preview.png')
bpy.ops.render.render(write_still=True)
if args.views:
    for cam in (front,side,back):
        scene.camera=cam
        scene.render.filepath=str(args.output/('simplified-marionette-'+cam.name.lower()+('-preview' if args.preview else '')+'.png'))
        bpy.ops.render.render(write_still=True)
print('SIMPLIFIED_MARIONETTE_COMPLETE',args.output)
