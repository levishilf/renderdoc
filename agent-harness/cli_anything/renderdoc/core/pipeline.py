"""
Pipeline state inspection.

Inspect the full graphics/compute pipeline state at any event:
shader stages, bound resources, viewports, blend state, depth/stencil, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import renderdoc as rd

    HAS_RD = True
except ImportError:
    rd = None  # type: ignore[assignment]
    HAS_RD = False


# ---------------------------------------------------------------------------
# Pipeline state at a given event
# ---------------------------------------------------------------------------

def get_pipeline_state(controller, event_id: int) -> Dict[str, Any]:
    """Return a comprehensive pipeline state dict at the given event."""
    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()

    result: Dict[str, Any] = {
        "eventId": event_id,
        "pipeline_type": str(controller.GetAPIProperties().pipelineType),
    }

    # Shader stages
    stages = [
        ("Vertex", rd.ShaderStage.Vertex),
        ("TessControl", rd.ShaderStage.Tess_Control),
        ("TessEval", rd.ShaderStage.Tess_Eval),
        ("Geometry", rd.ShaderStage.Geometry),
        ("Fragment", rd.ShaderStage.Fragment),
        ("Compute", rd.ShaderStage.Compute),
    ]
    shaders = {}
    for name, stage in stages:
        refl = pipe.GetShaderReflection(stage)
        if refl is not None:
            shaders[name] = {
                "bound": True,
                "resourceId": str(refl.resourceId),
                "entryPoint": str(refl.entryPoint),
                "debugInfo": str(refl.debugInfo.debuggable) if refl.debugInfo else "N/A",
                "numInputs": len(refl.inputSignature),
                "numOutputs": len(refl.outputSignature),
                "numCBuffers": len(refl.constantBlocks),
                "numReadOnly": len(refl.readOnlyResources),
                "numReadWrite": len(refl.readWriteResources),
            }
        else:
            shaders[name] = {"bound": False}
    result["shaders"] = shaders

    # Vertex inputs
    try:
        vinputs = pipe.GetVertexInputs()
        result["vertexInputs"] = [
            {
                "name": str(v.name),
                "vertexBuffer": v.vertexBuffer,
                "byteOffset": v.byteOffset,
                "perInstance": v.perInstance,
                "instanceRate": v.instanceRate,
                "format": str(v.format),
            }
            for v in vinputs
        ]
    except Exception:
        result["vertexInputs"] = []

    # Render targets
    try:
        targets = pipe.GetOutputTargets()
        result["renderTargets"] = [
            {"resourceId": str(t.resourceId), "index": i}
            for i, t in enumerate(targets)
            if t.resourceId != rd.ResourceId.Null()
        ]
    except Exception:
        result["renderTargets"] = []

    # Depth target
    try:
        depth = pipe.GetDepthTarget()
        if depth.resourceId != rd.ResourceId.Null():
            result["depthTarget"] = {"resourceId": str(depth.resourceId)}
        else:
            result["depthTarget"] = None
    except Exception:
        result["depthTarget"] = None

    # Viewports
    try:
        vp = pipe.GetViewport(0)
        result["viewport"] = {
            "x": vp.x,
            "y": vp.y,
            "width": vp.width,
            "height": vp.height,
            "minDepth": vp.minDepth,
            "maxDepth": vp.maxDepth,
        }
    except Exception:
        result["viewport"] = None

    return result


# ---------------------------------------------------------------------------
# Shader disassembly
# ---------------------------------------------------------------------------

def get_shader_disassembly(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    target_index: int = 0,
) -> Dict[str, Any]:
    """Get shader disassembly at a specific event.

    Parameters
    ----------
    stage_name : str
        One of: Vertex, TessControl, TessEval, Geometry, Fragment, Compute
    target_index : int
        Index into available disassembly targets (0 = first/default).
    """
    stage_map = {
        "vertex": rd.ShaderStage.Vertex,
        "tesscontrol": rd.ShaderStage.Tess_Control,
        "tesseval": rd.ShaderStage.Tess_Eval,
        "geometry": rd.ShaderStage.Geometry,
        "fragment": rd.ShaderStage.Fragment,
        "pixel": rd.ShaderStage.Fragment,
        "compute": rd.ShaderStage.Compute,
    }
    stage = stage_map.get(stage_name.lower())
    if stage is None:
        return {"error": f"Unknown stage: {stage_name}. Use: {list(stage_map.keys())}"}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": f"No shader bound at stage {stage_name} for event {event_id}"}

    targets = controller.GetDisassemblyTargets(True)
    if not targets:
        return {"error": "No disassembly targets available"}
    if target_index >= len(targets):
        target_index = 0

    pso = pipe.GetGraphicsPipelineObject()
    disasm = controller.DisassembleShader(pso, refl, targets[target_index])

    return {
        "eventId": event_id,
        "stage": stage_name,
        "target": targets[target_index],
        "disassembly": disasm,
    }


# ---------------------------------------------------------------------------
# Constant buffer contents
# ---------------------------------------------------------------------------

def get_cbuffer_contents(
    controller,
    event_id: int,
    stage_name: str = "Fragment",
    cbuffer_index: int = 0,
) -> Dict[str, Any]:
    """Get constant buffer variable contents at a specific event."""
    stage_map = {
        "vertex": rd.ShaderStage.Vertex,
        "tesscontrol": rd.ShaderStage.Tess_Control,
        "tesseval": rd.ShaderStage.Tess_Eval,
        "geometry": rd.ShaderStage.Geometry,
        "fragment": rd.ShaderStage.Fragment,
        "pixel": rd.ShaderStage.Fragment,
        "compute": rd.ShaderStage.Compute,
    }
    stage = stage_map.get(stage_name.lower())
    if stage is None:
        return {"error": f"Unknown stage: {stage_name}"}

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    refl = pipe.GetShaderReflection(stage)
    if refl is None:
        return {"error": f"No shader bound at stage {stage_name}"}

    if cbuffer_index >= len(refl.constantBlocks):
        return {"error": f"CBuffer index {cbuffer_index} out of range (max {len(refl.constantBlocks) - 1})"}

    pso = pipe.GetGraphicsPipelineObject()
    entry = pipe.GetShaderEntryPoint(stage)
    cb = pipe.GetConstantBlock(stage, cbuffer_index, 0)

    variables = controller.GetCBufferVariableContents(
        pso, refl.resourceId, stage, entry,
        cbuffer_index, cb.descriptor.resource, 0, 0
    )

    def _var_to_dict(v):
        d = {"name": v.name, "rows": v.rows, "columns": v.columns}
        if len(v.members) == 0:
            vals = []
            for r in range(v.rows):
                for c in range(v.columns):
                    vals.append(v.value.f32v[r * v.columns + c])
            d["values"] = vals
        else:
            d["members"] = [_var_to_dict(m) for m in v.members]
        return d

    return {
        "eventId": event_id,
        "stage": stage_name,
        "cbuffer_index": cbuffer_index,
        "variables": [_var_to_dict(v) for v in variables],
    }
