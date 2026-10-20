"""Simulate and validate the actual Vellum curves, then render the cached scene."""
from pathlib import Path
import argparse, json, math, time
import hou

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--frames',type=int,default=144)
parser.add_argument('--render',action='store_true')
parser.add_argument('--cache-only',action='store_true')
args=parser.parse_args()
hou.hipFile.load(str(ROOT/'scenes/Luma_Jellyfish.hipnc'),suppress_save_prompt=True)
ctrl=hou.node('/obj/JELLYFISH/CONTROLS')
solver=hou.node('/obj/JELLYFISH/VELLUM_TENTACLE_SIM')
targets=hou.node('/obj/JELLYFISH/animated_tentacle_targets')
ctrl.parm('use_cache').set(0)
report={'frames':args.frames,'fps':hou.fps(),'validation':[]}
packed=hou.Geometry()
packed.addAttrib(hou.attribType.Prim,'cacheframe',0)
first_root=None
start=time.time()
for f in range(1,args.frames+1):
    hou.setFrame(f)
    g=solver.geometry()
    if solver.errors(): raise RuntimeError(str(solver.errors()))
    if len(g.points())==0: raise RuntimeError('Empty simulation')
    vals=g.pointFloatAttribValues('P')
    if not all(math.isfinite(x) for x in vals): raise RuntimeError('Nonfinite simulation positions')
    g.saveToFile(str(ROOT/f'cache/tentacles/tentacles.{f:04d}.bgeo.sc'))
    # Only render attributes belong in the portable bake. Solver state is much larger.
    clean=g.freeze()
    keep={'P','v','Cd','Alpha','pscale','curveu','id','strand'}
    for a in tuple(clean.pointAttribs()):
        if a.name() not in keep: a.destroy()
    for a in tuple(clean.primAttribs()): a.destroy()
    for a in tuple(clean.globalAttribs()): a.destroy()
    for a in tuple(clean.vertexAttribs()): a.destroy()
    frameprim=packed.createPackedGeometry(clean)
    frameprim.setAttribValue('cacheframe',f)
    if f in [1,12,36,72,108,args.frames]:
        tg=targets.geometry()
        errors=[(p.position()-tg.point(p.number()).position()).length() for p in g.findPointGroup('roots').points()]
        # Quantify whether dynamics moved the unpinned tips relative to target curves.
        tips=[p for p in g.points() if p.floatAttribValue('curveu')>.999]
        tip_motion=sum((p.position()-tg.point(p.number()).position()).length() for p in tips)/len(tips)
        current_root=g.findPointGroup('roots').points()[0].position()
        if first_root is None: first_root=hou.Vector3(current_root)
        sample={'frame':f,'points':len(g.points()),'root_max_error':max(errors),
                'first_root_displacement_since_frame_1':(current_root-first_root).length(),
                'mean_tip_displacement_from_targets':tip_motion,'bounds':str(g.boundingBox())}
        if max(errors)>.002: raise RuntimeError('Pinned roots detached from animated targets')
        report['validation'].append(sample)
        print(json.dumps(sample),flush=True)
    if f%12==0: print(f'CACHED {f}/{args.frames} elapsed {time.time()-start:.1f}s',flush=True)
if max(x['first_root_displacement_since_frame_1'] for x in report['validation']) < .05:
    raise RuntimeError('Roots did not follow the swimming bell')
hou.node('/obj/JELLYFISH/EMBEDDED_TENTACLE_CACHE').parm('stash').set(packed)
ctrl.parm('use_cache').set(1)
for f in (1,args.frames//2,args.frames):
    hou.setFrame(f)
    embedded=hou.node('/obj/JELLYFISH/UNPACK_CACHED_CURVES').geometry()
    if len(embedded.points()) != 2580 and len(embedded.points()) != ctrl.evalParm('tentacle_count')*43:
        raise RuntimeError('Embedded cache point count mismatch')
hou.setFrame(1)
hou.hipFile.save()
report['elapsed_seconds']=time.time()-start
(ROOT/'work/simulation_report.json').write_text(json.dumps(report,indent=2))
print('CACHE COMPLETE',flush=True)
if args.render:
    rop=hou.node('/out/VIEWPORT_PREVIEW')
    for f in range(1,args.frames+1):
        rop.render(frame_range=(f,f))
        if f%12==0: print(f'RENDERED {f}/{args.frames}',flush=True)
    print('RENDER COMPLETE',flush=True)
