#!/usr/bin/env python3
"""
RenderDoc CLI - Command-line interface for RenderDoc graphics debugger.

Provides headless access to RenderDoc capture analysis:
  - Inspect capture metadata and sections
  - List and search draw calls / actions
  - Inspect pipeline state at any event
  - List, inspect, and export textures
  - Read buffer and mesh data
  - Query GPU performance counters
  - Pick pixel values

Usage:
    renderdoc-cli [OPTIONS] COMMAND [ARGS]...

All commands support --json for machine-readable output.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click

# ---------------------------------------------------------------------------
# Lazy import helpers – we don't want to import renderdoc at CLI parse time
# ---------------------------------------------------------------------------

_capture_handle = None  # type: ignore


def _get_handle(ctx: click.Context):
    """Return the active CaptureHandle, opening it if needed."""
    global _capture_handle
    if _capture_handle is not None:
        return _capture_handle
    path = ctx.obj.get("capture_path")
    if not path:
        click.echo("Error: No capture file specified. Use --capture <path>", err=True)
        ctx.exit(1)
    from cli_anything.renderdoc.core.capture import CaptureHandle

    _capture_handle = CaptureHandle(path)
    return _capture_handle


def _output(ctx: click.Context, data, human_fn=None):
    """Output data as JSON or human-readable."""
    if ctx.obj.get("json_mode"):
        from cli_anything.renderdoc.utils.output import output_json

        output_json(data)
    elif human_fn:
        human_fn(data)
    else:
        from cli_anything.renderdoc.utils.output import output_json

        output_json(data)


# ===========================================================================
# Root group
# ===========================================================================


@click.group()
@click.option(
    "--capture", "-c",
    type=click.Path(exists=False),
    envvar="RENDERDOC_CAPTURE",
    help="Path to .rdc capture file.",
)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format.")
@click.option("--debug", is_flag=True, help="Show debug tracebacks on errors.")
@click.version_option(package_name="cli-anything-renderdoc")
@click.pass_context
def cli(ctx, capture, json_mode, debug):
    """RenderDoc CLI – headless capture analysis tool."""
    ctx.ensure_object(dict)
    ctx.obj["capture_path"] = capture
    ctx.obj["json_mode"] = json_mode
    ctx.obj["debug"] = debug


# ===========================================================================
# capture commands
# ===========================================================================


@cli.group("capture")
def capture_group():
    """Capture file operations."""
    pass


@capture_group.command("info")
@click.pass_context
def capture_info(ctx):
    """Show capture file metadata and sections."""
    handle = _get_handle(ctx)
    meta = handle.metadata()
    meta["sections"] = handle.list_sections()

    def _human(data):
        click.echo(f"Capture: {data['path']}")
        click.echo(f"API:     {data['api']}")
        click.echo(f"Replay:  {'yes' if data['replay_supported'] else 'no'}")
        click.echo(f"\nSections ({len(data['sections'])}):")
        for s in data["sections"]:
            click.echo(f"  [{s['index']}] {s['name']} ({s['type']}) - {s['uncompressed_size']} bytes")

    _output(ctx, meta, _human)


@capture_group.command("thumb")
@click.option("--output", "-o", required=True, type=click.Path(), help="Output image path.")
@click.option("--max-dim", default=0, type=int, help="Max thumbnail dimension (0 = original).")
@click.pass_context
def capture_thumb(ctx, output, max_dim):
    """Extract capture thumbnail to an image file."""
    handle = _get_handle(ctx)
    result = handle.thumbnail(output, max_dim)
    _output(ctx, result)


@capture_group.command("convert")
@click.option("--output", "-o", required=True, type=click.Path(), help="Output file path.")
@click.option("--format", "fmt", default="", help="Target format (default: rdc).")
@click.pass_context
def capture_convert(ctx, output, fmt):
    """Convert capture to a different format."""
    handle = _get_handle(ctx)
    result = handle.convert(output, fmt)
    _output(ctx, result)


# ===========================================================================
# action commands
# ===========================================================================


@cli.group("actions")
def actions_group():
    """Draw call / action inspection."""
    pass


@actions_group.command("list")
@click.option("--flat/--no-flat", default=True, help="Flat list vs root-only.")
@click.option("--draws-only", is_flag=True, help="Only show actual draw calls.")
@click.pass_context
def actions_list(ctx, flat, draws_only):
    """List all actions (draw calls, clears, etc.) in the capture."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.actions import list_actions, get_drawcalls_only

    if draws_only:
        data = get_drawcalls_only(handle.controller)
    else:
        data = list_actions(handle.controller, flat=flat)

    def _human(actions):
        click.echo(f"Total actions: {len(actions)}")
        for a in actions:
            indent = "  " * a.get("depth", 0)
            flags = ",".join(a["flags"]) if a["flags"] else ""
            click.echo(f"{indent}[{a['eventId']:>5}] {a['name']:<50} {flags}")

    _output(ctx, data, _human)


@actions_group.command("summary")
@click.pass_context
def actions_summary(ctx):
    """Show action count summary by type."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.actions import action_summary

    data = action_summary(handle.controller)

    def _human(d):
        click.echo("Action Summary:")
        for k, v in d.items():
            click.echo(f"  {k}: {v}")

    _output(ctx, data, _human)


@actions_group.command("find")
@click.argument("pattern")
@click.pass_context
def actions_find(ctx, pattern):
    """Find actions by name pattern (case-insensitive)."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.actions import find_actions_by_name

    data = find_actions_by_name(handle.controller, pattern)
    _output(ctx, data)


@actions_group.command("get")
@click.argument("event_id", type=int)
@click.pass_context
def actions_get(ctx, event_id):
    """Get details of a single action by eventId."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.actions import find_action_by_event

    data = find_action_by_event(handle.controller, event_id)
    if data is None:
        data = {"error": f"No action found with eventId={event_id}"}
    _output(ctx, data)


# ===========================================================================
# texture commands
# ===========================================================================


@cli.group("textures")
def textures_group():
    """Texture inspection and export."""
    pass


@textures_group.command("list")
@click.pass_context
def textures_list(ctx):
    """List all textures in the capture."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.textures import list_textures

    data = list_textures(handle.controller)

    def _human(textures):
        click.echo(f"Total textures: {len(textures)}")
        for t in textures:
            click.echo(
                f"  [{t['resourceId']}] {t['width']}x{t['height']} "
                f"mips={t['mips']} fmt={t['format']}"
            )

    _output(ctx, data, _human)


@textures_group.command("get")
@click.argument("resource_id")
@click.pass_context
def textures_get(ctx, resource_id):
    """Get details of a single texture by resource ID."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.textures import get_texture

    data = get_texture(handle.controller, resource_id)
    if data is None:
        data = {"error": f"Texture {resource_id} not found"}
    _output(ctx, data)


@textures_group.command("save")
@click.argument("resource_id")
@click.option("--output", "-o", required=True, type=click.Path(), help="Output file path.")
@click.option("--format", "fmt", default="png", help="Image format: png, jpg, bmp, tga, hdr, exr, dds.")
@click.option("--mip", default=0, type=int, help="Mip level (-1 for all, DDS only).")
@click.option("--slice", "slice_idx", default=0, type=int, help="Array slice (-1 for all, DDS only).")
@click.option("--alpha", default="preserve", help="Alpha: preserve, discard, blend_checkerboard.")
@click.pass_context
def textures_save(ctx, resource_id, output, fmt, mip, slice_idx, alpha):
    """Save a texture to an image file."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.textures import save_texture

    data = save_texture(handle.controller, resource_id, output, fmt, mip, slice_idx, alpha)
    _output(ctx, data)


@textures_group.command("save-outputs")
@click.argument("event_id", type=int)
@click.option("--output-dir", "-o", required=True, type=click.Path(), help="Output directory.")
@click.option("--format", "fmt", default="png", help="Image format.")
@click.pass_context
def textures_save_outputs(ctx, event_id, output_dir, fmt):
    """Save all render target outputs at a specific event."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.textures import save_action_outputs

    data = save_action_outputs(handle.controller, event_id, output_dir, fmt)
    _output(ctx, data)


@textures_group.command("pick")
@click.argument("resource_id")
@click.argument("x", type=int)
@click.argument("y", type=int)
@click.option("--mip", default=0, type=int)
@click.option("--slice", "slice_idx", default=0, type=int)
@click.pass_context
def textures_pick(ctx, resource_id, x, y, mip, slice_idx):
    """Pick a pixel value from a texture."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.textures import pick_pixel

    data = pick_pixel(handle.controller, resource_id, x, y, mip, slice_idx)
    _output(ctx, data)


# ===========================================================================
# pipeline commands
# ===========================================================================


@cli.group("pipeline")
def pipeline_group():
    """Pipeline state inspection."""
    pass


@pipeline_group.command("state")
@click.argument("event_id", type=int)
@click.pass_context
def pipeline_state(ctx, event_id):
    """Show full pipeline state at a specific event."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.pipeline import get_pipeline_state

    data = get_pipeline_state(handle.controller, event_id)
    _output(ctx, data)


@pipeline_group.command("disasm")
@click.argument("event_id", type=int)
@click.option("--stage", default="Fragment", help="Shader stage: Vertex, Fragment, Compute, etc.")
@click.option("--target", "target_index", default=0, type=int, help="Disassembly target index.")
@click.pass_context
def pipeline_disasm(ctx, event_id, stage, target_index):
    """Get shader disassembly at a specific event."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.pipeline import get_shader_disassembly

    data = get_shader_disassembly(handle.controller, event_id, stage, target_index)
    _output(ctx, data)


@pipeline_group.command("cbuffer")
@click.argument("event_id", type=int)
@click.option("--stage", default="Fragment", help="Shader stage.")
@click.option("--index", "cbuffer_index", default=0, type=int, help="CBuffer index.")
@click.pass_context
def pipeline_cbuffer(ctx, event_id, stage, cbuffer_index):
    """Get constant buffer contents at a specific event."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.pipeline import get_cbuffer_contents

    data = get_cbuffer_contents(handle.controller, event_id, stage, cbuffer_index)
    _output(ctx, data)


# ===========================================================================
# resource commands
# ===========================================================================


@cli.group("resources")
def resources_group():
    """Resource (buffer/texture) listing and data reading."""
    pass


@resources_group.command("list")
@click.pass_context
def resources_list(ctx):
    """List all resources in the capture."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.resources import list_resources

    data = list_resources(handle.controller)

    def _human(resources):
        click.echo(f"Total resources: {len(resources)}")
        for r in resources:
            click.echo(f"  [{r['resourceId']}] {r['type']}: {r['name']}")

    _output(ctx, data, _human)


@resources_group.command("buffers")
@click.pass_context
def resources_buffers(ctx):
    """List all buffer resources."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.resources import list_buffers

    data = list_buffers(handle.controller)
    _output(ctx, data)


@resources_group.command("read-buffer")
@click.argument("resource_id")
@click.option("--offset", default=0, type=int, help="Byte offset.")
@click.option("--length", default=256, type=int, help="Number of bytes to read.")
@click.option("--format", "fmt", default="hex", help="Output format: hex, float32, uint32, raw.")
@click.pass_context
def resources_read_buffer(ctx, resource_id, offset, length, fmt):
    """Read raw buffer data."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.resources import get_buffer_data

    data = get_buffer_data(handle.controller, resource_id, offset, length, fmt)
    _output(ctx, data)


# ===========================================================================
# mesh commands
# ===========================================================================


@cli.group("mesh")
def mesh_group():
    """Mesh data (vertex inputs/outputs) inspection."""
    pass


@mesh_group.command("inputs")
@click.argument("event_id", type=int)
@click.option("--max-vertices", default=100, type=int, help="Max vertices to decode.")
@click.pass_context
def mesh_inputs(ctx, event_id, max_vertices):
    """Get vertex shader inputs at a draw call."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.mesh import get_mesh_inputs

    data = get_mesh_inputs(handle.controller, event_id, max_vertices)
    _output(ctx, data)


@mesh_group.command("outputs")
@click.argument("event_id", type=int)
@click.option("--max-vertices", default=100, type=int, help="Max vertices to decode.")
@click.pass_context
def mesh_outputs(ctx, event_id, max_vertices):
    """Get post-vertex-shader outputs at a draw call."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.mesh import get_mesh_outputs

    data = get_mesh_outputs(handle.controller, event_id, max_vertices)
    _output(ctx, data)


# ===========================================================================
# counter commands
# ===========================================================================


@cli.group("counters")
def counters_group():
    """GPU performance counters."""
    pass


@counters_group.command("list")
@click.pass_context
def counters_list(ctx):
    """List all available GPU counters."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.counters import list_counters

    data = list_counters(handle.controller)

    def _human(counters):
        click.echo(f"Available GPU counters: {len(counters)}")
        for c in counters:
            click.echo(f"  [{c['counter']}] {c['name']}: {c['description']}")

    _output(ctx, data, _human)


@counters_group.command("fetch")
@click.option("--ids", default=None, help="Comma-separated counter IDs (default: SamplesPassed).")
@click.pass_context
def counters_fetch(ctx, ids):
    """Fetch GPU counter results."""
    handle = _get_handle(ctx)
    from cli_anything.renderdoc.core.counters import fetch_counters

    counter_ids = None
    if ids:
        counter_ids = [int(i.strip()) for i in ids.split(",")]

    data = fetch_counters(handle.controller, counter_ids)
    _output(ctx, data)


# ===========================================================================
# Cleanup hook
# ===========================================================================

@cli.result_callback()
@click.pass_context
def cleanup(ctx, *args, **kwargs):
    global _capture_handle
    if _capture_handle is not None:
        _capture_handle.close()
        _capture_handle = None


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    cli(obj={})


if __name__ == "__main__":
    main()
