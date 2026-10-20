"""Build an editable Houdini 21 jellyfish; run with Houdini's hython.

No external assets or HDAs are required. The saved HIP embeds all VEX code.
"""
from pathlib import Path
import hou
import json
import math

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / 'scenes' / 'Luma_Jellyfish.hipnc'
for folder in ('scenes', 'cache/tentacles', 'work/preview', 'assets'):
    (ROOT / folder).mkdir(parents=True, exist_ok=True)
hou.hipFile.clear(suppress_save_prompt=True)
hou.setFps(24)
hou.playbar.setFrameRange(1, 144)
hou.playbar.setPlaybackRange(1, 144)
hou.setFrame(1)
geo = hou.node('/obj').createNode('geo', 'JELLYFISH')
for n in geo.children(): n.destroy()

COLORS = {'bell':(.23,.62,.65), 'arms':(.78,.40,.51), 'veins':(.97,.69,.36),
          'organs':(.75,.52,.78), 'tentacles':(.30,.67,.75), 'control':(.95,.80,.42)}

def node(kind, name, inputs=(), parms=None, color=None, comment=None):
    n=geo.createNode(kind,name)
    for i,inp in enumerate(inputs):
        if inp is not None: n.setInput(i,inp)
    if parms: n.setParms(parms)
    if color: n.setColor(hou.Color(COLORS.get(color,color)))
    if comment:
        n.setComment(comment)
        n.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    return n

def wrangle(name, code, inputs=(), detail=False, color=None, comment=None):
    return node('attribwrangle',name,inputs,{'class':2 if not detail else 0,'snippet':code},color,comment)

def out(name, source, color): return node('null',name,(source,),color=color)

def group_material(source, part, mat):
    return wrangle('LOOK_'+part, f's@shop_materialpath="/mat/{mat}"; setprimgroup(0,"{part}",@primnum,1);',
                   (source,),color=part)

def set_primitive(n): n.parm('class').set(1); return n

ctrl=node('null','CONTROLS',color='control',comment='START HERE | Shape / pulse / tentacles / display\nRecache tentacles after changing animation or shape.')
templates=hou.ParmTemplateGroup()
def add_float(name,label,value,lo,hi):
    templates.append(hou.FloatParmTemplate(name,label,1,default_value=(value,),min=lo,max=hi))
def add_int(name,label,value,lo,hi):
    templates.append(hou.IntParmTemplate(name,label,1,default_value=(value,),min=lo,max=hi))
add_float('radius','Bell Radius',2.05,1,4)
add_float('height','Bell Height',1.38,.5,3)
add_int('bell_segments','Bell Around Segments',144,48,192)
add_int('bell_rings','Bell Profile Rings',44,16,64)
add_int('scallops','Rim Lobes',12,4,24)
add_float('scallop_depth','Scalloped Rim Depth',.075,0,.2)
add_float('pulse','Contraction Amount',.105,0,.25)
add_float('period','Pulse Period (Seconds)',2.8,1,6)
add_float('heave','Vertical Swim Motion',.12,0,.4)
add_int('arm_count','Oral Arms',6,3,10)
add_float('arm_length','Oral Arm Length',3.2,1.5,5)
add_float('arm_width','Oral Arm Half Width',.27,.08,.5)
add_int('tentacle_count','Tentacle Count',60,12,100)
add_float('tentacle_length','Tentacle Length',2.65,1,5)
add_float('current','Water Current Strength',.22,0,1)
add_float('vein_radius','Vein Radius',.011,.004,.035)
templates.append(hou.ToggleParmTemplate('use_cache','Use Saved Tentacle Cache',default_value=False))
templates.append(hou.MenuParmTemplate('show_part','Display Part',
    ('all','bell','arms','veins','organs','tentacles'),
    ('Full Jellyfish','Bell','Oral Arms','Veins','Organs','Tentacles'),default_value=0))
ctrl.setParmTemplateGroup(templates)

# Shared, deterministic rest profile. All parts are authored in object space, Y up.
PROFILE=r'''
vector bellpos(float u; float a; float R; float H; int lobes; float scallop) {
    float theta=u*1.70;
    float edge=pow(smooth(.62,1.,u),2.);
    float r=R*sin(theta)*(1.+scallop*.45*cos(lobes*a)*edge);
    float y=H*cos(theta)+scallop*cos(lobes*a)*edge;
    return set(r*cos(a),y,r*sin(a));
}
'''
BELL_SETTINGS=r'''
float R=ch("../CONTROLS/radius"); float H=ch("../CONTROLS/height");
int lobes=chi("../CONTROLS/scallops"); float scallop=ch("../CONTROLS/scallop_depth");
'''
ANIM_FUNCTION=r'''
vector animatebell(vector restpos; float u; float t; float period; float amp; float heave) {
    vector p=restpos;
    float phase=2.*M_PI*t/period;
    float wave=sin(phase-.45*u);
    float radial=1.-amp*wave*(.22+.78*pow(u,1.8));
    p.x*=radial; p.z*=radial;
    p.y+=amp*.8*sin(phase-.4)*pow(u,3.0)+heave*sin(phase-.55);
    return p;
}
'''
ANIM_SETTINGS=r'''
float period=ch("../CONTROLS/period"); float amp=ch("../CONTROLS/pulse");
float heave=ch("../CONTROLS/heave");
'''

bell=wrangle('bell_profile_surface',PROFILE+BELL_SETTINGS+r'''
int na=chi("../CONTROLS/bell_segments"); int nr=chi("../CONTROLS/bell_rings");
int tip=addpoint(0,set(0,H,0)); setpointattrib(0,"bell_u",tip,0.);
for(int j=1;j<=nr;j++) {
    float u=float(j)/nr;
    for(int i=0;i<na;i++) {
        float a=2.*M_PI*i/na;
        int p=addpoint(0,bellpos(u,a,R,H,lobes,scallop));
        setpointattrib(0,"bell_u",p,u);
        setpointattrib(0,"angle",p,a);
        if(j==nr) setpointgroup(0,"rim",p,1);
    }
}
for(int i=0;i<na;i++) addprim(0,"poly",tip,1+(i+1)%na,1+i);
for(int j=0;j<nr-1;j++) for(int i=0;i<na;i++) {
    int a=1+j*na+i, b=1+j*na+(i+1)%na;
    addprim(0,"poly",a,b,b+na,a+na);
}
''',detail=True,color='bell',comment='Revolved bell profile with 12 scalloped lobes. Stable point ordering.')
bellrest=out('BELL_REST',bell,'bell')
bellanim=wrangle('bell_swimming_pulse',ANIM_FUNCTION+ANIM_SETTINGS+r'''
@P=animatebell(@P,f@bell_u,@Time,period,amp,heave);
''',(bellrest,),color='bell',comment='Spatially varying pulse: the rim contracts more than the crown.')
bellanim=out('BELL_ANIM',bellanim,'bell')
bellthick=node('polyextrude','bell_shell_thickness',(bellanim,),
               {'dist':.022,'outputback':1,'outputfront':1,'outputside':1},color='bell')
bellcolor=wrangle('bell_opalescent_color',r'''
float u=f@bell_u;
float stripe=pow(.5+.5*cos(f@angle*12.+u*2.),9.);
@Cd=lerp(set(.20,.58,.66),set(.42,.84,.78),smooth(.55,1.,u));
@Cd=lerp(@Cd,set(.65,.49,.79),stripe*.2);
f@Alpha=.34+.12*pow(u,4.);
''',(bellthick,),color='bell')
bellnorm=node('normal','bell_normals',(bellcolor,),color='bell')
bellout=out('OUT_BELL',set_primitive(group_material(bellnorm,'bell','opal_bell')),'bell')

# The decorative lip uses the exact same rest profile and the same pulse.
rim=wrangle('scalloped_rim_curve',PROFILE+BELL_SETTINGS+r'''
int n=chi("../CONTROLS/bell_segments"); int pr=addprim(0,"polyline");
for(int i=0;i<=n;i++) {
    int p=addpoint(0,bellpos(1.,2.*M_PI*i/n,R,H,lobes,scallop));
    setpointattrib(0,"bell_u",p,1.); addvertex(0,pr,p);
}
''',detail=True,color='bell')
rimanim=wrangle('rim_follow_pulse',ANIM_FUNCTION+ANIM_SETTINGS+r'''
@P=animatebell(@P,1.,@Time,period,amp,heave);
@Cd=set(.44,.92,.83); f@Alpha=1.;
''',(rim,),color='bell')
rimsweep=node('sweep','rim_round_sweep',(rimanim,),{'surfaceshape':1,'radius':.027,'cols':8},color='bell')
rimlook=set_primitive(group_material(rimsweep,'bell','luminous_veins'))

# Veins: course-prescribed Remesh -> Find Shortest Path -> Fuse/Resample/Smooth -> Sweep -> Point Deform.
remesh=node('remesh','triangulate_bell_for_veins',(bellrest,),{'targetsize':.075,'iterations':2},color='veins',
            comment='REST ONLY. Remeshing the animated bell each frame would break correspondence.')
seeds=wrangle('vein_start_and_end_points',PROFILE+BELL_SETTINGS+r'''
int roots=6;
for(int i=0;i<roots;i++) {
    float a=2.*M_PI*i/roots;
    int p=addpoint(0,bellpos(.22,a,R,H,lobes,scallop)); setpointgroup(0,"starts",p,1);
}
for(int i=0;i<60;i++) {
    float a=2.*M_PI*(i+.23*rand(i+7))/60;
    float u=lerp(.80,.98,rand(i+47));
    int p=addpoint(0,bellpos(u,a,R,H,lobes,scallop)); setpointgroup(0,"ends",p,1);
}
''',detail=True,color='veins')
shortest=node('findshortestpath','branching_shortest_paths',(remesh,seeds),
              {'startpts':'starts','endpts':'ends','multiplicity':2,'keep':0},color='veins')
fuse=node('fuse','merge_shared_vein_points',(shortest,),{'tol3d':.0005},color='veins')
# Remove overlapping graph edges before resampling; keep each unique branch segment once.
unique=wrangle('unique_vein_edges',r'''
int edges[]; string keys[]; int old=nprimitives(0);
for(int pr=0;pr<old;pr++) {
    int pts[]=primpoints(0,pr);
    for(int i=0;i<len(pts)-1;i++) {
        int a=pts[i],b=pts[i+1]; string key=sprintf("%d_%d",min(a,b),max(a,b));
        if(find(keys,key)<0) { append(keys,key); append(edges,a); append(edges,b); }
    }
}
for(int pr=old-1;pr>=0;pr--) removeprim(0,pr,0);
for(int i=0;i<len(edges);i+=2) addprim(0,"polyline",edges[i],edges[i+1]);
''',(fuse,),detail=True,color='veins')
# PolyPath joins degree-2 chains but preserves branch junctions.
paths=node('polypath','join_vein_branches',(unique,),color='veins')
resample=node('resample','resample_veins',(paths,),{'length':.035},color='veins')
smooth=node('smooth','smooth_vein_paths',(resample,),{'strength':2,'filterquality':3},color='veins')
reproject=wrangle('project_veins_back_to_rest_bell',r'''
int pr; vector uv; xyzdist(1,@P,pr,uv);
@P=primuv(1,"P",pr,uv);
vector nn=prim_normal(1,pr,uv.x,uv.y);
@P+=normalize(nn)*.028;
float u=primuv(1,"bell_u",pr,uv);
f@pscale=lerp(1.65,.55,u);
@Cd=lerp(set(1.,.68,.38),set(.60,1.,.91),u); f@Alpha=1.;
''',(smooth,bellrest),color='veins')
veinsweep=node('sweep','sweep_vein_tubes',(reproject,),{'surfaceshape':1,'cols':6,'endcaptype':1},color='veins')
veinsweep.parm('radius').setExpression('ch("../CONTROLS/vein_radius")')
veindeform=node('pointdeform','veins_follow_bell',(veinsweep,bellrest,bellanim),
                 {'radius':.35},color='veins',comment='Input 1: veins / Input 2: bell rest / Input 3: bell animation')
veinout=out('OUT_VEINS',set_primitive(group_material(veindeform,'veins','luminous_veins')),'veins')

# Ruffled oral arms and a separate low-resolution control cage.
ARMS_COMMON=r'''
int count=chi("../CONTROLS/arm_count");
float L=ch("../CONTROLS/arm_length"); float W=ch("../CONTROLS/arm_width");
'''
arms=wrangle('ruffled_oral_arm_ribbons',ARMS_COMMON+r'''
int rows=120,cols=14;
for(int k=0;k<count;k++) {
    float a=2.*M_PI*k/count+.2; float len=L*lerp(.82,1.12,rand(k+83));
    vector radial=set(cos(a),0,sin(a)); vector tangent=set(-sin(a),0,cos(a));
    int offset=k*(rows+1)*(cols+1);
    for(int j=0;j<=rows;j++) {
        float u=float(j)/rows; float taper=pow(max(.02,sin(M_PI*(.08+.90*u))),.6);
        vector center=radial*(.53+.10*sin(u*9.+k)*u)+set(0,.35-len*u,0);
        float twist=u*5.5+k*.8;
        vector side=tangent*cos(twist)+radial*sin(twist);
        vector other=cross(set(0,1,0),side);
        for(int i=0;i<=cols;i++) {
            float v=2.*float(i)/cols-1.;
            float ruffle=sin(u*86.+k+v*3.)*.13*pow(abs(v),2.)*taper;
            vector pos=center+side*(v*W*taper*(1.+.20*sin(u*49.+k)));
            pos+=other*ruffle; pos.y+=.075*sin(u*68.+v*4.+k)*pow(abs(v),2.)*taper;
            int p=addpoint(0,pos);
            setpointattrib(0,"arm_u",p,u); setpointattrib(0,"arm_v",p,v);
            setpointattrib(0,"piece",p,k);
            vector c=lerp(set(.80,.35,.44),set(.48,.82,.83),smooth(.12,.92,u));
            c=lerp(c,set(1.,.79,.64),pow(abs(v),4.)*.65);
            setpointattrib(0,"Cd",p,c); setpointattrib(0,"Alpha",p,1.);
        }
    }
    for(int j=0;j<rows;j++) for(int i=0;i<cols;i++) {
        int p=offset+j*(cols+1)+i;
        addprim(0,"poly",p,p+1,p+cols+2,p+cols+1);
    }
}
''',detail=True,color='arms',comment='Six independently varied ribbons. Fine edge waves create oral-arm frills.')
cage=wrangle('oral_arm_rest_cages',ARMS_COMMON+r'''
int rows=16;
for(int k=0;k<count;k++) {
    float a=2.*M_PI*k/count+.2; float len=L*lerp(.82,1.12,rand(k+83));
    vector radial=set(cos(a),0,sin(a)); int offset=k*(rows+1)*4;
    for(int j=0;j<=rows;j++) {
        float u=float(j)/rows;
        vector center=radial*(.53+.10*sin(u*9.+k)*u)+set(0,.35-len*u,0);
        for(int i=0;i<4;i++) {
            float ang=2.*M_PI*i/4.+M_PI/4.;
            int p=addpoint(0,center+set(cos(ang),0,sin(ang))*(W+.16));
            setpointattrib(0,"arm_u",p,u); setpointattrib(0,"piece",p,k);
        }
    }
    for(int j=0;j<rows;j++) for(int i=0;i<4;i++) {
        int p=offset+j*4+i,q=offset+j*4+(i+1)%4;
        addprim(0,"poly",p,q,q+4,p+4);
    }
}
''',detail=True,color='arms')
cageanim=wrangle('oral_arm_traveling_wave',ANIM_SETTINGS+r'''
float u=f@arm_u; float a=2.*M_PI*i@piece/chi("../CONTROLS/arm_count")+.2;
float phase=2.*M_PI*@Time/period;
vector root=set(cos(a),0,sin(a))*.53;
float radialscale=1.-amp*.28*sin(phase-.4); @P*=set(radialscale,1.,radialscale);
@P.y+=heave*sin(phase-.55);
@P.x+=.18*pow(u,1.4)*sin(phase-3.*u+i@piece*.8);
@P.z+=.16*pow(u,1.4)*cos(phase-3.5*u+i@piece*.8);
@P.y+=.07*u*sin(phase-4.*u+i@piece);
''',(cage,),color='arms')
armdeform=node('pointdeform','pointdeform_oral_arms',(arms,cage,cageanim),
               {'radius':.55,'pieceattrib':'piece'},color='arms',comment='Coarse animated cages drive detailed ribbons; piece isolates each arm.')
armnorm=node('normal','oral_arm_normals',(armdeform,),color='arms')
armout=out('OUT_ARMS',set_primitive(group_material(armnorm,'arms','silk_arms')),'arms')

# Four flower-like gonad organs, under the transparent bell.
organs=wrangle('four_petal_organs',r'''
int rings=80,sides=12;
for(int k=0;k<4;k++) {
    float a=2.*M_PI*k/4.+.2;
    vector center=set(.56*cos(a),.67,.56*sin(a)); int offset=k*rings*sides;
    for(int j=0;j<rings;j++) {
        float t=2.*M_PI*j/rings; float radius=.27*(1.+.23*cos(3.*t));
        vector radial=set(cos(t+a),0,sin(t+a));
        vector base=center+radial*radius;
        for(int i=0;i<sides;i++) {
            float b=2.*M_PI*i/sides;
            vector pos=base+radial*(.065*cos(b))+set(0,.045*sin(b)+.035*sin(2.*t),0);
            int p=addpoint(0,pos);
            setpointattrib(0,"Cd",p,set(.97,.49,.63));
            setpointattrib(0,"Alpha",p,1.);
        }
    }
    for(int j=0;j<rings;j++) for(int i=0;i<sides;i++) {
        int p=offset+j*sides+i,q=offset+j*sides+(i+1)%sides;
        int r=offset+((j+1)%rings)*sides+(i+1)%sides,s=offset+((j+1)%rings)*sides+i;
        addprim(0,"poly",p,q,r,s);
    }
}
''',detail=True,color='organs')
organanim=wrangle('organs_follow_swim',ANIM_SETTINGS+r'''
float phase=2.*M_PI*@Time/period;
float radialscale=1.-amp*.3*sin(phase-.4); @P*=set(radialscale,1.,radialscale);
@P.y+=heave*sin(phase-.55);
''',(organs,),color='organs')
organnorm=node('normal','organ_normals',(organanim,),color='organs')
organout=out('OUT_ORGANS',set_primitive(group_material(organnorm,'organs','rose_organs')),'organs')

# Live Vellum hair simulation. Geometry at every frame carries animated pin targets.
tent=wrangle('tentacle_rest_curves',PROFILE+BELL_SETTINGS+r'''
int count=chi("../CONTROLS/tentacle_count"); int seg=42;
float L=ch("../CONTROLS/tentacle_length");
for(int k=0;k<count;k++) {
    float a=2.*M_PI*(k+.5)/count;
    vector root=bellpos(.992,a,R,H,lobes,scallop);
    root.x*=.997; root.z*=.997;
    float len=L*lerp(.48,1.25,rand(k+731));
    int pr=addprim(0,"polyline");
    for(int j=0;j<=seg;j++) {
        float u=float(j)/seg;
        vector p=root+set(0,-len*u,0);
        p+=set(cos(a),0,sin(a))*(.14*u+.07*sin(u*8.+k)*u);
        int pt=addpoint(0,p); addvertex(0,pr,pt);
        setpointattrib(0,"rootpos",pt,root); setpointattrib(0,"curveu",pt,u);
        setpointattrib(0,"id",pt,pt); setpointattrib(0,"strand",pt,k);
        setpointattrib(0,"pscale",pt,lerp(.012,.0035,u));
        setpointattrib(0,"Cd",pt,lerp(set(.47,.92,.85),set(.41,.53,.77),u));
        setpointattrib(0,"Alpha",pt,1.);
        if(j==0) setpointgroup(0,"roots",pt,1);
    }
}
''',detail=True,color='tentacles')
tenttarget=wrangle('animated_tentacle_targets',ANIM_FUNCTION+ANIM_SETTINGS+r'''
vector delta=animatebell(v@rootpos,.992,@Time,period,amp,heave)-v@rootpos;
@P+=delta;
''',(tent,),color='tentacles',comment='Moving root targets evaluated every frame; stable strand point ids.')
vellum=node('vellumconstraints','vellum_configure_hair',(tenttarget,),{
    'constrainttype':4,'domass':1,'mass':.003,'dothickness':0,
    'stretchstiffness':1.,'stretchstiffnessexp':6,'stretchdampingratio':.03,
    'bendstiffness':1.,'bendstiffnessexp':-2,'benddampingratio':.15,
    'pingroup':'roots','pintype':0,'pinrotation':0,'matchanimation':1,
    'dragnormal':1.5,'dragtangent':.15},color='tentacles')
solver=node('vellumsolver','VELLUM_TENTACLE_SIM',color='tentacles',comment='Real hair dynamics | roots match animation | 3 substeps | reduced gravity + water drag')
solver.setInput(0,vellum,0); solver.setInput(1,vellum,1)
solver.setParms({'substeps':3,'niter':60,'gravityy':-1.1,'doselfcollisions':0,
                 'enablecollisions':1,'winddrag':1.3,'veldamping':.04})
solver.parm('windx').setExpression('ch("../CONTROLS/current") * sin($T * 1.1)')
solver.parm('windz').setExpression('ch("../CONTROLS/current") * 0.65 * cos($T * 0.8)')
solver.parm('windy').set(.10)
# Embedded packed geometry makes the .hipnc self-contained for Canvas.
embedded=node('stash','EMBEDDED_TENTACLE_CACHE',color='tentacles',
              comment='144 packed simulation frames stored INSIDE the HIP. Rebuilt by cache_and_preview.py.')
pickframe=node('blast','SELECT_CACHED_FRAME',(embedded,),
               {'group':'@cacheframe=`clamp($F,1,144)`','negate':1},color='tentacles')
unpack=node('unpack','UNPACK_CACHED_CURVES',(pickframe,),color='tentacles')
switch=node('switch','LIVE_OR_CACHED_TENTACLES',(solver,unpack),color='tentacles')
switch.parm('input').setExpression('ch("../CONTROLS/use_cache")')
tentres=node('resample','smooth_render_tentacle_curves',(switch,),
             {'length':.025,'treatpolysas':2},color='tentacles')
tentsweep=node('sweep','sweep_tapered_tentacles',(tentres,),
               {'surfaceshape':1,'radius':1.,'cols':6,'endcaptype':1},color='tentacles')
tentout=out('OUT_TENTACLES',set_primitive(group_material(tentsweep,'tentacles','pearl_tentacles')),'tentacles')

full=node('merge','ASSEMBLE_FIVE_PARTS',(bellout,rimlook,armout,veinout,organout,tentout))
display=node('switch','DISPLAY_PART',(full,bellout,armout,veinout,organout,tentout))
display.parm('input').setExpression('ch("../CONTROLS/show_part")')
final=out('OUT_JELLYFISH',display,'control')
final.setDisplayFlag(True); final.setRenderFlag(True)

# Materials: viewport-friendly point colors; physically shaded Mantra materials also included.
for name,color,alpha,emit in [
    ('opal_bell',(.18,.60,.70),.42,.025),('silk_arms',(.88,.48,.56),1.,.04),
    ('luminous_veins',(.55,.95,.83),1.,.30),('rose_organs',(1.,.46,.6),1.,.13),
    ('pearl_tentacles',(.40,.68,.85),1.,.11)]:
    mat=hou.node('/mat').createNode('principledshader',name)
    mat.parmTuple('basecolor').set(color)
    mat.parm('rough').set(.28 if name=='opal_bell' else .4)
    mat.parm('ior').set(1.36)
    mat.parm('reflect').set(.25)
    mat.parm('emitint').set(emit)
    mat.parm('emitcolor_usePointColor').set(1)
    mat.parm('displayOpacity').set(alpha)
    if name=='opal_bell':
        mat.parm('transparency').set(.65)
        mat.parm('transcolor_usePointColor').set(1)
    mat.moveToGoodPosition()

# Camera looking along local -Z at the model.
cam=hou.node('/obj').createNode('cam','SHOWCASE_CAMERA')
eye=hou.Vector3((7.,3.,11.5)); target=hou.Vector3((0.,-1.,0.))
rot=(target-eye).matrixToRotateTo(hou.Vector3((0,0,-1))).inverted()
cam.setWorldTransform(rot*hou.hmath.buildTranslate(eye))
cam.parm('rz').set(0)
cam.parm('focal').set(55); cam.parm('resx').set(960); cam.parm('resy').set(720)
cam.parm('near').set(.1); cam.parm('far').set(100.)

def light(name,pos,color,intensity,scale):
    l=hou.node('/obj').createNode('hlight',name)
    l.parmTuple('t').set(pos); l.parmTuple('light_color').set(color)
    l.parm('light_intensity').set(intensity)
    # Area lights work in viewport OpenGL and Mantra.
    l.parm('light_type').set(2)
    l.parmTuple('areasize').set((scale,scale))
    direction=hou.Vector3((0,-.5,0))-hou.Vector3(pos)
    rotation=direction.matrixToRotateTo(hou.Vector3((0,0,-1))).inverted()
    l.setWorldTransform(rotation*hou.hmath.buildTranslate(pos))
    return l
light('KEY_softbox',(3,5,6),(0.78,.93,1.),2.2,5.)
light('FILL_rose',(-4,1,3),(1.,.65,.66),1.1,4.)
light('RIM_aqua',(1,3,-4),(.30,.9,1.),3.,3.)
light('LOW_soft_fill',(-1,-3,5),(.65,.85,1.),1.8,5.)

rop=hou.node('/out').createNode('opengl','VIEWPORT_PREVIEW')
rop.setParms({'camera':cam.path(),'vobjects':'JELLYFISH','picture':'$HIP/../work/preview/jellyfish.$F4.png',
              'trange':1,'f1':1,'f2':144,'f3':1,'tres':1,'res1':960,'res2':720,
              'aamode':3,'shadows':0,'ambocclusion':1,'transparency':1,'transquality':3,
              'colorcorrect':1,'gamma':2.2,'hqlighting':0,'alights':'','bloom':0})

# Layout by teaching topic with notes, rather than an opaque single generator.
geo.layoutChildren(horizontal_spacing=2.,vertical_spacing=1.)
branches=[('BELL | rest + animated shell',[n for n in geo.children() if n.name().startswith(('bell_','BELL_','OUT_BELL','LOOK_bell','scalloped_','rim_'))],'bell'),
          ('VEINS | shortest paths on REST surface',[remesh,seeds,shortest,fuse,unique,paths,resample,smooth,reproject,veinsweep,veindeform,geo.node('LOOK_veins'),veinout],'veins'),
          ('ARMS | detailed ribbons + animated cages',[arms,cage,cageanim,armdeform,armnorm,geo.node('LOOK_arms'),armout],'arms'),
          ('ORGANS | four petal rings',[organs,organanim,organnorm,geo.node('LOOK_organs'),organout],'organs'),
          ('TENTACLES | actual Vellum hair + embedded cache',[tent,tenttarget,vellum,solver,embedded,pickframe,unpack,switch,tentres,tentsweep,geo.node('LOOK_tentacles'),tentout],'tentacles')]
for col,(title,nodes,c) in enumerate(branches):
    # Explicit vertical lanes. Extra side inputs are offset for readability.
    for row,n in enumerate(dict.fromkeys(nodes)):
        n.setPosition(hou.Vector2((col*9.,-row*1.7)))
    box=geo.createNetworkBox(); box.setComment(title); box.setColor(hou.Color(COLORS[c]))
    for n in nodes: box.addItem(n)
    box.fitAroundContents()
ctrl.setPosition(hou.Vector2((18,4)))
full.setPosition(hou.Vector2((18,-28))); display.setPosition(hou.Vector2((18,-30))); final.setPosition(hou.Vector2((18,-32)))
note=geo.createStickyNote('READ_ME')
note.setText('LUMA / PROCEDURAL JELLYFISH\n\n24 fps | frames 1-144\n\n1. CONTROLS exposes the main art parameters.\n2. Every colored lane is one assignment part.\n3. BELL_REST never changes with time.\n4. Veins and oral arms use Point Deform.\n5. Tentacles use a real Vellum Hair solver.\n6. Cache is optional: disable it before editing.\n7. Render /out/VIEWPORT_PREVIEW for a playblast.\n\nSave as .hipnc (Houdini Apprentice).\nHIP + cache are local/Canvas files, not GitHub assets.')
note.setPosition(hou.Vector2((-9,3))); note.setSize(hou.Vector2((7,8)))
hou.node('/obj').layoutChildren()
hou.node('/out').layoutChildren()

# Cook and record visible errors before saving. No simulation beyond the first frame here.
report={}
for n in [bellout,armout,veinout,organout,tentout,final]:
    try:
        g=n.geometry()
        report[n.name()]={'points':len(g.points()),'primitives':len(g.prims()),
                          'bounds':str(g.boundingBox()),'errors':list(n.errors())}
    except Exception as e: report[n.name()]={'exception':str(e),'errors':list(n.errors())}
for n in geo.children():
    if n.errors(): report[n.name()]={'errors':list(n.errors())}
hou.setSessionModuleSource((ROOT/'scripts/scene_ui.py').read_text())
hou.hipFile.save(str(SCENE))
(ROOT/'work/build_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
print('SAVED '+str(SCENE),flush=True)
