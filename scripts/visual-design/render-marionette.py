"""Build a local, editable interpretation of the porcelain marionette reference.

Run with Blender's bundled Python; no add-ons, downloads, or external services.
See docs/visual-design/experiments/porcelain-marionette.md.
"""

import argparse
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'data/visual-design')
parser.add_argument('--resolution', type=int, default=1400)
parser.add_argument('--samples', type=int, default=64)
parser.add_argument('--preview', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
args.output.mkdir(parents=True, exist_ok=True)
random.seed(16)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.resolution
scene.render.resolution_y = round(args.resolution * 1.2)
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = -.35
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new('Warm studio atmosphere')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.32, .24, .25, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = .24


def material(name, color, rough=.3, metal=0, coat=0, subsurface=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = .19
    p.inputs['Subsurface Weight'].default_value = subsurface
    return m


ivory = material('Glazed warm porcelain', (.91, .66, .46), .22, coat=.4, subsurface=.035)
blush = material('Painted rose cheeks', (.73, .30, .23), .38, coat=.22)
face_paint = material('Porcelain with painted cheek blush', (.91, .66, .46), .22, coat=.4, subsurface=.035)
nodes = face_paint.node_tree.nodes
links = face_paint.node_tree.links
coords = nodes.new('ShaderNodeNewGeometry')
distances = []
for side in (-1, 1):
    distance = nodes.new('ShaderNodeVectorMath'); distance.operation = 'DISTANCE'
    distance.inputs[1].default_value = (side*.43, -.49, 5.04)
    links.new(coords.outputs['Position'], distance.inputs[0])
    distances.append(distance)
nearest = nodes.new('ShaderNodeMath'); nearest.operation = 'MINIMUM'
for i, distance in enumerate(distances):
    links.new(distance.outputs['Value'], nearest.inputs[i])
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.interpolation = 'EASE'
ramp.color_ramp.elements[0].color = (.78, .34, .27, 1)
ramp.color_ramp.elements[0].position = .025
ramp.color_ramp.elements[1].position = .20
ramp.color_ramp.elements[1].color = (.91, .66, .46, 1)
links.new(nearest.outputs[0], ramp.inputs[0])
links.new(ramp.outputs['Color'], nodes['Principled BSDF'].inputs['Base Color'])
seam = material('Recessed joint shadow', (.10, .041, .026), .32)
chocolate = material('Chestnut hair', (.045, .012, .007), .36, coat=.12)
highlight = material('Chestnut silk highlights', (.105, .032, .015), .38, coat=.12)
for hair_material in (chocolate, highlight):
    hair_material.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = .22
pink = material('Raspberry lacquer', (.48, .003, .045), .33, coat=.18)
pink_light = material('Rose silk highlights', (.72, .013, .11), .32, coat=.18)
bodice = material('Chocolate brocade', (.052, .018, .015), .48)
pattern = material('Raised brocade embroidery', (.16, .071, .041), .52)
cream = material('Peach silk', (.83, .47, .26), .42)
lace = material('Ivory lace thread', (.99, .78, .52), .57)
gold = material('Antique gold', (.66, .37, .075), .25, metal=.72)
white = material('Warm glass eye whites', (.91, .85, .65), .15, coat=.45)
iris = material('Olive amber irises', (.22, .25, .034), .22, coat=.4)
iris_gold = material('Iris amber filaments', (.53, .32, .043), .31)
iris_dark = material('Iris outer ring', (.048, .055, .009), .23)
black = material('Lashes and pupils', (.009, .004, .003), .21, coat=.3)
stage = material('Studio rose limestone', (.19, .10, .11), .66)
pedestal = material('Porcelain display base', (.40, .25, .22), .33, coat=.2)


def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c


body_col = collection('01 • Porcelain & articulated joints')
face_col = collection('02 • Painted face & glass eyes')
hair_col = collection('03 • Sculpted curls & ribbons')
dress_col = collection('04 • Corset, embroidery & lace')
stage_col = collection('05 • Studio, cameras & lighting')
active_col = body_col


def put(obj, mat=None):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    active_col.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    if obj.type == 'MESH':
        for p in obj.data.polygons:
            p.use_smooth = True
    return obj


def sphere(name, pos, scale, mat, segments=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=20, location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    return put(obj, mat)


def mesh(name, verts, faces, mat, subdiv=0):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    active_col.objects.link(obj)
    data.materials.append(mat)
    for p in data.polygons:
        p.use_smooth = True
    if subdiv:
        mod = obj.modifiers.new('Silhouette smoothing', 'SUBSURF')
        mod.levels = subdiv
    return obj


def curve(name, pts, radius, mat, taper=None, cyclic=False):
    d = bpy.data.curves.new(name, 'CURVE')
    d.dimensions = '3D'
    d.resolution_u = 2
    d.bevel_depth = radius
    d.bevel_resolution = 3
    s = d.splines.new('POLY')
    s.points.add(len(pts) - 1)
    for i, (p, co) in enumerate(zip(s.points, pts)):
        p.co = (*co, 1)
        if taper:
            p.radius = taper(i / (len(pts) - 1))
    s.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, d)
    active_col.objects.link(o)
    d.materials.append(mat)
    return o


def bezier(name, points, radius, mat, taper=None):
    a, b, c, d = map(Vector, points)
    pts = [(1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d for t in [i/48 for i in range(49)]]
    return curve(name, pts, radius, mat, taper)


def ring(name, center, radius, tube, mat, normal=(0, 0, 1), aspect=1):
    q = Vector((0, 0, 1)).rotation_difference(Vector(normal).normalized())
    pts = [Vector(center) + q @ Vector((radius*math.cos(t), radius*aspect*math.sin(t), 0)) for t in [i*math.tau/64 for i in range(64)]]
    return curve(name, pts, tube, mat, cyclic=True)


def segment(name, a, b, widths, mat):
    a, b = Vector(a), Vector(b)
    axis = b-a
    q = Vector((0, 0, 1)).rotation_difference(axis.normalized())
    verts, faces = [], []
    for j, r in enumerate(widths):
        center = a + axis * j / (len(widths)-1)
        for i in range(32):
            t = i*math.tau/32
            verts.append(center + q @ Vector((r*math.cos(t), r*math.sin(t), 0)))
    for j in range(len(widths)-1):
        for i in range(32):
            k = j*32+i
            faces.append((k, j*32+(i+1)%32, (j+1)*32+(i+1)%32, k+32))
    faces.extend([tuple(reversed(range(32))), tuple((len(widths)-1)*32+i for i in range(32))])
    return mesh(name, verts, faces, mat, 1)


def joint(name, p, r):
    sphere(name+' • porcelain ball', p, (r, r, r), ivory)
    ring(name+' • fine joint seam', p, r*.995, r*.025, seam, normal=(0, 1, 0))


# Distinct pieces preserve the ball-jointed construction of the reference.
sphere('Torso under clothing', (0, 0, 3.78), (.32, .18, .46), ivory)
sphere('Porcelain shoulders and chest', (0, 0, 4.10), (.49, .255, .20), ivory)
segment('Neck', (0, 0, 4.13), (0, 0, 4.64), [.22, .18, .15, .17, .23], ivory)
for side in (-1, 1):
    x = side*.29
    joint('Hip', (x, 0, 2.39), .22)
    segment('Upper leg', (x, 0, 2.4), (x, -.02, 1.37), [.18, .23, .24, .19, .13], ivory)
    joint('Knee', (x, -.02, 1.31), .145)
    segment('Shin', (x, 0, 1.21), (x, 0, .47), [.137, .17, .14, .11, .095], ivory)
    joint('Ankle', (x, 0, .41), .102)
    sphere('Instep', (x, -.08, .235), (.145, .23, .19), ivory)
    sphere('Foot', (x, -.16, .14), (.17, .22, .105), ivory)
    for i in range(5):
        tx = x + side*(-.107 + i*.052)
        ty = -.41 + .018*i
        sphere('Porcelain toe', (tx, ty, .125), (.039-i*.003, .075-i*.006, .055), ivory, 20)
        sphere('Pink toenail', (tx, ty-.033, .167), (.024-i*.002, .028, .009), pink, 16)
    shoulder = (side*.61, 0, 4.08)
    elbow = (side*.91, -.02, 3.48)
    wrist = (side*1.28, -.08, 2.95)
    joint('Shoulder', shoulder, .17)
    segment('Upper arm', (side*.65, 0, 3.98), (side*.88, -.02, 3.58), [.145, .15, .13, .105], ivory)
    joint('Elbow', elbow, .117)
    segment('Forearm', (side*.95, -.03, 3.40), (side*1.24, -.07, 3.02), [.105, .12, .09, .068], ivory)
    joint('Wrist', wrist, .075)
    palm = sphere('Hand palm', (side*1.34, -.09, 2.80), (.105, .058, .16), ivory)
    palm.rotation_euler.y = side*-.3
    for i in range(4):
        x = side*(1.26+i*.059)
        start = (x, -.095, 2.71 + .02*abs(i-1))
        mid = (x+side*.036, -.12, start[2]-.11)
        end = (x+side*.047, -.15, mid[2]-.10 + .022*abs(i-1))
        segment('Finger proximal', start, mid, [.026, .029, .024], ivory)
        joint('Finger knuckle', mid, .025)
        segment('Finger distal', mid, end, [.023, .024, .014], ivory)
        sphere('Manicure', (end[0], end[1]-.016, end[2]+.022), (.018, .01, .035), pink, 16)
    bezier('Thumb', [(side*1.26, -.11, 2.86), (side*1.15, -.14, 2.81), (side*1.16, -.17, 2.72), (side*1.18, -.18, 2.69)], .035, ivory, lambda t: 1-.45*t)

# Head: a continuous custom surface, with a narrowed jaw and full cheeks.
active_col = face_col
verts, faces = [], []
for j in range(49):
    theta = math.pi*j/48
    nz = math.cos(theta)
    width = 1 if nz > -.2 else 1-.26*((-nz-.2)/.8)
    for i in range(96):
        phi = math.tau*i/96
        x = .75*math.sin(theta)*math.cos(phi)*width
        y = .59*math.sin(theta)*math.sin(phi)
        z = 5.28+.82*nz
        verts.append((x, y, z))
for j in range(48):
    for i in range(96):
        a = j*96+i
        faces.append((a, j*96+(i+1)%96, (j+1)*96+(i+1)%96, a+96))
mesh('Sculpted porcelain head', verts, faces, face_paint, 1)
for side in (-1, 1):
    sphere('Ear', (side*.70, 0, 5.12), (.14, .095, .20), ivory)
    sphere('Ear inset', (side*.76, -.071, 5.13), (.066, .024, .12), blush)
    x = side*.325
    sphere('Porcelain eyelid surround', (x, -.495, 5.34), (.273, .112, .229), ivory)
    sphere('Glass eye', (x, -.523, 5.34), (.247, .137, .212), white)
    sphere('Iris dark rim', (x, -.655, 5.34), (.184, .027, .193), iris_dark)
    sphere('Olive glass iris', (x, -.676, 5.34), (.169, .025, .178), iris)
    for i in range(56):
        t = i*math.tau/56
        pts = []
        for j in range(6):
            r = .075+j*.015
            a = t + .04*math.sin(j+i)
            pts.append((x+r*math.cos(a), -.702+.018*(r/.17)**2, 5.34+1.08*r*math.sin(a)))
        curve('Radial iris pigment', pts, .0035, iris_gold if i%3 else iris_dark)
    sphere('Pupil', (x, -.705, 5.34), (.071, .015, .105), black)
    sphere('Eye catchlight', (x-.055, -.723, 5.42), (.034, .008, .039), white, 20)
    sphere('Tiny eye catchlight', (x+.052, -.708, 5.28), (.014, .008, .016), white, 16)
    # Upper eyelid arc and individual tapered lashes.
    pts = [(x+.248*math.cos(t), -.552-.045*math.sin(t), 5.34+.209*math.sin(t)) for t in [i*math.pi/60 for i in range(61)]]
    curve('Upper eyeliner', pts, .017, black)
    for i in range(12):
        t = .16+i*2.8/11
        px, pz = x+.245*math.cos(t), 5.34+.209*math.sin(t)
        bezier('Painted silk lash', [(px, -.557-.048*math.sin(t), pz), (px+.036*math.cos(t), -.65, pz+.032), (px+.055*math.cos(t), -.66, pz+.075), (px+.07*math.cos(t), -.64, pz+.08)], .009, black, lambda u: 1-u*.96)
    bezier('Chestnut eyebrow', [(x-side*.22, -.52, 5.66), (x-side*.07, -.61, 5.74), (x+side*.09, -.54, 5.76), (x+side*.23, -.43, 5.66)], .024, chocolate, lambda t: .5+.5*math.sin(math.pi*t))
    for i in range(5):
        sphere('Painted freckle', (side*(.37+i*.032), -.519+i*.006, 5.07+.015*math.sin(i*3)), (.006, .003, .006), highlight, 12)
sphere('Nose bridge', (0, -.586, 5.19), (.07, .047, .11), ivory)
sphere('Button nose', (0, -.637, 5.10), (.074, .057, .055), ivory)
for side in (-1, 1):
    sphere('Nostril', (side*.039, -.677, 5.077), (.013, .009, .009), blush, 16)
bezier('Cupid bow left', [(-.115, -.542, 4.92), (-.08, -.59, 4.948), (-.037, -.623, 4.98), (0, -.607, 4.947)], .024, pink)
bezier('Cupid bow right', [(0, -.607, 4.947), (.037, -.623, 4.98), (.08, -.59, 4.948), (.115, -.542, 4.92)], .024, pink)
bezier('Lower lip', [(-.105, -.55, 4.916), (-.06, -.625, 4.86), (.06, -.625, 4.86), (.105, -.55, 4.916)], .029, pink_light, lambda t: .3+.7*math.sin(math.pi*t))
bezier('Mouth seam', [(-.091, -.571, 4.916), (-.035, -.628, 4.916), (.035, -.628, 4.916), (.091, -.571, 4.916)], .007, seam)

# Hair cap and swept strands; the forehead remains readable under the fringe.
active_col = hair_col
def cap_point(theta, phi, lift=0):
    return ((.78+lift)*math.sin(theta)*math.cos(phi), (.63+lift)*math.sin(theta)*math.sin(phi), 5.30+(.87+lift)*math.cos(theta))

verts, faces = [], []
for j in range(25):
    for i in range(128):
        phi = i*math.tau/128
        end = 1.67+.43*math.sin(phi)
        verts.append(cap_point(j/24*end, phi))
for j in range(24):
    for i in range(128):
        a = j*128+i
        faces.append((a, j*128+(i+1)%128, (j+1)*128+(i+1)%128, a+128))
mesh('Chestnut scalp', verts, faces, chocolate, 1)
for i in range(100):
    phi = i*math.tau/100
    end = 1.68+.43*math.sin(phi)
    pts = [cap_point(.05+(end-.05)*t, phi+.22*math.sin(math.pi*t), .013) for t in [j/60 for j in range(61)]]
    curve('Combed crown strand', pts, .023 if i%4 else .033, pink if i%9==0 else highlight if i%3==0 else chocolate, lambda t: .35+.65*math.sin(math.pi*t)**.5)
for side in (-1, 1):
    for i in range(10):
        dx = i*.047
        bezier('Swept fringe', [(side*(.015+dx*.4), -.19-dx*.35, 6.13-dx*.1), (side*(.27+dx), -.63, 6.0), (side*(.05+dx), -.73, 5.70), (side*(.04+dx), -.66+dx*.2, 5.59+.13*i/9)], .042, pink if i%4==0 else highlight if i%3==0 else chocolate, lambda t: (1-.93*t)**.6)
    for i in range(5):
        dx = i*.063
        bezier('Loose tapered fringe', [(side*(.11+dx), -.40, 6.05), (side*(.36+dx), -.67, 5.91), (side*(.25+dx), -.70, 5.63), (side*(.12+dx), -.65, 5.52+.027*i)], .029, pink if i%2==0 else chocolate, lambda t: (1-.98*t)**.7)
    for i in range(26):
        angle = i*2.39996
        depth = .32*math.sin(angle)
        startx = .81+.13*math.cos(angle)
        length = 1.25+.53*random.random()
        phase = random.random()*math.tau
        width = .145+.075*random.random()
        pts = []
        for j in range(121):
            t = j/120
            a = phase+t*math.tau*(1.8+length*.5)
            cx = startx+.34*math.sin(math.pi*t*.85)
            x = side*(cx+width*math.sin(a))
            y = .07+depth+.12*math.cos(a)
            z = 6.02-length*t+.11*math.sin(a)
            pts.append((x, y, z))
        mat = pink if i%3==0 else pink_light if i%7==0 else highlight if i%4==0 else chocolate
        curve('Pigtail ringlet', pts, .042+random.random()*.019, mat, lambda t: (.55+.45*math.sin(math.pi*t)**.3)*(1-.87*t**7))
        if i%2==0:
            curve('Fine curl highlight', [(x+side*.024, y-.038, z+.007) for x,y,z in pts], .009, pink_light if mat in (pink, pink_light) else highlight, lambda t: 1-.97*t**4)
    for i in range(3):
        bezier('Crown flyaway curl', [(side*.78, .04, 5.98), (side*(1.18+i*.035), -.1, 6.58+i*.035), (side*(.54+i*.10), .12, 6.54+i*.02), (side*.91, .15, 6.01)], .024+i*.003, pink if i%2 else highlight)

def ribbon_bow(center, scale=1):
    cx, cy, cz = center
    for side in (-1, 1):
        verts, faces = [], []
        for j in range(25):
            t = j/24
            width = (.035+.19*math.sin(math.pi*t))*scale
            for k in range(7):
                v = k/6*2-1
                verts.append((cx+side*.42*scale*math.sin(math.pi*t*.87), cy-.14*scale*math.sin(math.pi*t)+.045*math.cos(v*math.pi)*scale, cz+.14*scale*math.sin(math.pi*t*1.5)+v*width))
        for j in range(24):
            for k in range(6):
                a=j*7+k
                faces.append((a,a+1,a+8,a+7))
        o=mesh('Folded satin bow loop', verts, faces, pink, 2)
        o.modifiers.new('Ribbon thickness','SOLIDIFY').thickness=.009
        for edge in (0,6):
            curve('Bow stitched edge', [verts[j*7+edge] for j in range(25)], .009*scale, pink_light)
        verts, faces = [], []
        for j in range(26):
            t=j/25
            for k in range(7):
                v=k/6*2-1
                verts.append((cx+side*(.06+.18*t)*scale+v*.105*scale, cy+.04*math.sin(t*math.tau)-.01, cz-(.06+.52*t)*scale+.045*math.sin(t*10+v)))
        for j in range(25):
            for k in range(6):
                a=j*7+k
                faces.append((a,a+1,a+8,a+7))
        mesh('Ribbon tail',verts,faces,pink,1)
    sphere('Bow knot', (cx,cy-.04,cz), (.095*scale,.09*scale,.105*scale), pink_light)

for side in (-1,1):
    ribbon_bow((side*.81,-.28,5.99),.73)

# Tailored corset surface and piping.
active_col = dress_col
def corset_point(t, a, offset=0):
    r = .36+.16*(2*t-1)**2+.025*t
    z = 3.15+1.00*t-.11*(1-t)**7*max(0,-math.sin(a))**6
    z += .055*t**6*abs(math.cos(a))
    return ((r+offset)*math.cos(a), (r*.63+offset)*math.sin(a), z)

verts=[corset_point(j/24,i*math.tau/128) for j in range(25) for i in range(128)]
faces=[]
for j in range(24):
    for i in range(128):
        faces.append((j*128+i,j*128+(i+1)%128,(j+1)*128+(i+1)%128,(j+1)*128+i))
mesh('Fitted brocade corset',verts,faces,bodice,1)
for t in (0,1):
    curve('Corset raspberry binding',[corset_point(t,i*math.tau/180,.014) for i in range(180)],.021,pink,cyclic=True)
for i in range(12):
    a=i*math.tau/12
    curve('Corset boning',[corset_point(j/60,a,.012) for j in range(61)],.013,pink)
for i in range(32):
    a=i*math.tau/32
    for j in range(5):
        t=.1+j*.18
        pts=[corset_point(t+.045*math.sin(q),a+.065*math.cos(q),.009) for q in [k*math.tau/32 for k in range(32)]]
        curve('Brocade leaf embroidery',pts,.0045,pattern,cyclic=True)
for i in range(6):
    t=.12+i*.145
    _,y,z=corset_point(t,-math.pi/2,.02)
    for side in (-1,1):
        sphere('Gold corset clasp',(side*.043,y-.012,z),(.03,.017,.025),gold,16)
    curve('Clasp bridge',[(-.04,y-.015,z),(.04,y-.015,z)],.012,gold)
for i in range(8):
    t=.08+i*.11
    for side in (-1,1):
        a=math.pi/2+side*.24
        x,y,z=corset_point(t,a,.025)
        ring('Back lacing eyelet',(x,y,z),.024,.008,gold,normal=(0,1,0))
    if i<7:
        for side in (-1,1):
            p1=corset_point(t,math.pi/2+side*.24,.044)
            p2=corset_point(t+.11,math.pi/2-side*.24,.044)
            curve('Crossed back lacing',[p1,p2],.018,pink)

# Two layers of silk with real scallops, thread loops and daisy lace.
def skirt_point(t,a,layer,offset=0):
    top,bottom,rtop,rbot = (3.17,2.39,.48,1.04) if layer==0 else (2.94,2.05,.57,1.13)
    r=rtop+(rbot-rtop)*t**.8
    r += (.012+.045*t)*math.cos(a*40)+.018*t*math.cos(a*80)
    z=top+(bottom-top)*t+.042*t**6*math.cos(a*20)
    return ((r+offset)*math.cos(a),(r*.77+offset)*math.sin(a),z)

for layer in (1,0):
    verts=[skirt_point(j/32,i*math.tau/240,layer) for j in range(33) for i in range(240)]
    faces=[]
    for j in range(32):
        for i in range(240):
            faces.append((j*240+i,j*240+(i+1)%240,(j+1)*240+(i+1)%240,(j+1)*240+i))
    obj=mesh('Lower silk flounce' if layer else 'Upper silk flounce',verts,faces,cream,1)
    obj.modifiers.new('Silk thickness','SOLIDIFY').thickness=.012
    for t in (.78,.96,1):
        curve('Scalloped lace hem',[skirt_point(t,i*math.tau/400,layer,.008) for i in range(400)],.012 if t==1 else .007,lace,cyclic=True)
    for i in range(120):
        a=i*math.tau/120
        pts=[skirt_point(.91+.075*math.cos(q),a+.022*math.sin(q),layer,.015) for q in [k*math.tau/24 for k in range(24)]]
        curve('Openwork lace loop',pts,.005,lace,cyclic=True)
    for i in range(40):
        a=i*math.tau/40
        t=.71
        center=skirt_point(t,a,layer,.019)
        sphere('Lace flower center',center,(.018,.018,.018),lace,12)
        for petal in range(5):
            angle=petal*math.tau/5
            pts=[]
            for k in range(21):
                q=k*math.tau/20
                da=.030*math.cos(angle)+.024*math.cos(q)
                dt=.041*math.sin(angle)+.032*math.sin(q)
                pts.append(skirt_point(t+dt,a+da,layer,.02))
            curve('Five petal lace flower',pts,.006,lace,cyclic=True)
        for j in range(3):
            p=skirt_point(.18+j*.14,a,layer,.01)
            sphere('Seed pearl embroidery',p,(.011,.011,.011),lace,12)
for i in range(88):
    a=i*math.tau/88
    pts=[corset_point(1,a+.023*math.cos(t),.009) for t in [j*math.tau/24 for j in range(25)]]
    pts=[(x,y,z+.028+.023*math.sin(j*math.tau/24)) for j,(x,y,z) in enumerate(pts)]
    curve('Bodice lace edge',pts,.006,bodice)

# Studio scene: all illumination and geometry remain editable.
active_col=stage_col
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=1.90, depth=.16, location=(0,0,-.04))
base=put(bpy.context.object,pedestal)
base.name='Round display plinth'
bev=base.modifiers.new('Soft edge','BEVEL'); bev.width=.045; bev.segments=3
ring('Gold plinth inlay',(0,0,.03),1.83,.012,gold)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.14))
put(bpy.context.object,stage).name='Seamless studio floor'


def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def area(name,pos,energy,color,size,target):
    d=bpy.data.lights.new(name,'AREA'); d.energy=energy; d.color=color; d.shape='DISK'; d.size=size
    o=bpy.data.objects.new(name,d); stage_col.objects.link(o); o.location=pos; aim(o,target)


area('Key • large warm softbox',(-4,-6,9),950,(1,.82,.68),5,(0,0,3.6))
area('Fill • cool silk',(4,-3,5.7),650,(.73,.83,1),4,(0,0,3.9))
area('Rim • rose hair light',(2,3,7.7),1100,(1,.39,.42),3,(0,0,4.6))
area('Top porcelain sheen',(-2,1,9),750,(1,.87,.65),3,(0,0,3))
area('Face softbox',(-.5,-5,5.5),90,(1,.91,.83),2,(0,0,5.1))


def camera(name,pos,target,ortho):
    d=bpy.data.cameras.new(name); d.type='ORTHO'; d.ortho_scale=ortho; d.lens=65
    o=bpy.data.objects.new(name,d); stage_col.objects.link(o); o.location=pos; aim(o,target)
    return o


scene.camera=camera('Hero camera',(8,-22,10),(0,0,3.18),7.9)
camera('Front inspection camera',(0,-24,6.7),(0,0,3.2),7.5)
camera('Back inspection camera',(0,24,7),(0,0,3.2),7.5)
camera('Face detail camera',(3,-15,7.5),(0,-.05,5.25),3.4)
scene['Reference']='visual design/character sheet.png; user-provided porcelain marionette sheet'
scene['Scope']='Procedural stylized interpretation; separate objects; no armature, animation or printability validation.'
scene['Rebuild']='blender -b --factory-startup --python scripts/visual-design/render-marionette.py'
scene.render.filepath=str(args.output/'porcelain-marionette.png')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(args.output/'porcelain-marionette.blend'),compress=True)
if args.preview:
    scene.render.resolution_percentage=45
    scene.cycles.samples=16
    scene.render.filepath=str(args.output/'porcelain-marionette-preview.png')
bpy.ops.render.render(write_still=True)
print('MARIONETTE_RENDER_COMPLETE',scene.render.filepath)
