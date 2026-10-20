"""Embedded hou.session source: set a useful camera and network view after load."""
import hou

def setup_jellyfish_view():
    if not hou.isUIAvailable():
        return
    geo=hou.node('/obj/JELLYFISH')
    camera=hou.node('/obj/SHOWCASE_CAMERA')
    if geo is None or camera is None:
        return
    scene=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if scene is not None:
        scene.setPwd(hou.node('/obj'))
        viewport=scene.curViewport()
        viewport.changeType(hou.geometryViewportType.Perspective)
        viewport.setCamera(camera)
        viewport.lockCameraToView(False)
        settings=viewport.settings()
        settings.setLighting(hou.viewportLighting.Headlight)
        settings.setHeadlightIntensity(1.35)
        settings.setSceneGamma(2.2)
        settings.setColorScheme(hou.viewportColorScheme.Dark)
        settings.showGeometryColor(True)
        for ds in (hou.displaySetType.DisplayModel,hou.displaySetType.SceneObject,hou.displaySetType.CurrentModel):
            settings.displaySet(ds).setShadedMode(hou.glShadingType.Smooth)
            settings.displaySet(ds).useLighting(True)
        for guide in (hou.viewportGuide.XZPlane,hou.viewportGuide.XYPlane,hou.viewportGuide.YZPlane,hou.viewportGuide.NodeGuides):
            settings.enableGuide(guide,False)
    network=hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if network is not None:
        network.setPwd(geo)
        network.setVisibleBounds(hou.BoundingRect(-10,-34,44,7))
    geo.node('CONTROLS').setCurrent(True,clear_all_selected=True)

if hou.isUIAvailable():
    import hdefereval
    hdefereval.executeDeferred(setup_jellyfish_view)
