"""Make a compact portable HIP, configure the preview, and render its animation."""
from pathlib import Path
import hou, json, math, time, argparse

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--render',action='store_true')
args=parser.parse_args()
hou.hipFile.load(str(ROOT/'scenes/Luma_Jellyfish.hipnc'),suppress_save_prompt=True)
geo=hou.node('/obj/JELLYFISH')
obsolete_reader=geo.node('READ_TENTACLE_CACHE')
if obsolete_reader is not None:
    obsolete_reader.destroy()
packed=hou.Geometry(); packed.addAttrib(hou.attribType.Prim,'cacheframe',0)
for f in range(1,145):
    clean=hou.Geometry(); clean.loadFromFile(str(ROOT/f'cache/tentacles/tentacles.{f:04d}.bgeo.sc'))
    keep={'P','v','Cd','Alpha','pscale','curveu','id','strand'}
    for a in tuple(clean.pointAttribs()):
        if a.name() not in keep: a.destroy()
    for a in tuple(clean.primAttribs()): a.destroy()
    for a in tuple(clean.globalAttribs()): a.destroy()
    for a in tuple(clean.vertexAttribs()): a.destroy()
    p=packed.createPackedGeometry(clean); p.setAttribValue('cacheframe',f)
geo.node('EMBEDDED_TENTACLE_CACHE').parm('stash').set(packed)
geo.node('CONTROLS').parm('use_cache').set(1)
rop=hou.node('/out/VIEWPORT_PREVIEW')
rop.setParms({'hqlighting':0,'alights':'','picture':'$HIP/../work/preview/jellyfish.$F4.png'})
# Save node names as output markers for easy navigation.
geo.node('OUT_JELLYFISH').setDisplayFlag(True)
geo.node('OUT_JELLYFISH').setRenderFlag(True)
geo.node('CONTROLS').setSelected(True,clear_all_selected=True)
hou.setFrame(1)
hou.setSessionModuleSource((ROOT/'scripts/scene_ui.py').read_text())
hou.hipFile.save()
print('SAVED PORTABLE HIP',flush=True)
report={'fps':24,'frames':144,'all_frames_valid':True,'samples':[],'node_errors':{}}
start=time.time()
for f in range(1,145):
    hou.setFrame(f)
    g=geo.node('OUT_JELLYFISH').geometry()
    assert len(g.points())>50000
    assert all(math.isfinite(x) for x in g.pointFloatAttribValues('P'))
    if f in [1,24,48,72,96,120,144]:
        report['samples'].append({'frame':f,'points':len(g.points()),'primitives':len(g.prims()),'bounds':str(g.boundingBox())})
    if args.render: rop.render(frame_range=(f,f))
    if f%12==0: print(f'VALIDATED / RENDERED {f}/144 | {time.time()-start:.1f}s',flush=True)
for n in geo.children():
    if n.errors(): report['node_errors'][n.name()]=list(n.errors())
report['elapsed_seconds']=time.time()-start
(ROOT/'work/final_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
hou.setFrame(1)
print('DONE',flush=True)
