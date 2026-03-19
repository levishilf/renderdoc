---
name: cli-anything-renderdoc
description: CLI harness for RenderDoc graphics debugger capture analysis
version: 0.1.0
command: cli-anything-renderdoc
install: pip install cli-anything-renderdoc
requires:
  - renderdoc (Python bindings from RenderDoc installation)
  - click>=8.0
categories:
  - graphics
  - debugging
  - gpu
  - rendering
---

# RenderDoc CLI Skill

Headless command-line analysis of RenderDoc GPU frame captures (`.rdc` files).

## Capabilities

- **Capture inspection**: metadata, sections, thumbnails, format conversion
- **Action tree**: list/search/filter draw calls, clears, dispatches, markers
- **Texture operations**: list, inspect, export (PNG/JPG/DDS/HDR/EXR), pixel picking
- **Pipeline state**: full shader/RT/viewport state at any event
- **Shader analysis**: disassembly, constant buffer readback
- **Resource inspection**: buffer/texture enumeration, raw data reading
- **Mesh data**: vertex shader input/output decoding
- **GPU counters**: enumerate and fetch hardware performance counters

## Command Groups

### capture
```bash
cli-anything-renderdoc -c frame.rdc capture info          # Metadata + sections
cli-anything-renderdoc -c frame.rdc capture thumb -o t.png # Extract thumbnail
cli-anything-renderdoc -c frame.rdc capture convert -o out.rdc --format rdc
```

### actions
```bash
cli-anything-renderdoc -c frame.rdc actions list           # All actions
cli-anything-renderdoc -c frame.rdc actions list --draws-only  # Draw calls only
cli-anything-renderdoc -c frame.rdc actions summary        # Counts by type
cli-anything-renderdoc -c frame.rdc actions find "Shadow"  # Search by name
cli-anything-renderdoc -c frame.rdc actions get 42         # Single action
```

### textures
```bash
cli-anything-renderdoc -c frame.rdc textures list
cli-anything-renderdoc -c frame.rdc textures get <id>
cli-anything-renderdoc -c frame.rdc textures save <id> -o out.png --format png
cli-anything-renderdoc -c frame.rdc textures save-outputs 42 -o ./renders/
cli-anything-renderdoc -c frame.rdc textures pick <id> 100 200
```

### pipeline
```bash
cli-anything-renderdoc -c frame.rdc pipeline state 42
cli-anything-renderdoc -c frame.rdc pipeline disasm 42 --stage Fragment
cli-anything-renderdoc -c frame.rdc pipeline cbuffer 42 --stage Vertex --index 0
```

### resources
```bash
cli-anything-renderdoc -c frame.rdc resources list
cli-anything-renderdoc -c frame.rdc resources buffers
cli-anything-renderdoc -c frame.rdc resources read-buffer <id> --format float32
```

### mesh
```bash
cli-anything-renderdoc -c frame.rdc mesh inputs 42 --max-vertices 10
cli-anything-renderdoc -c frame.rdc mesh outputs 42
```

### counters
```bash
cli-anything-renderdoc -c frame.rdc counters list
cli-anything-renderdoc -c frame.rdc counters fetch --ids 1,2,3
```

## JSON Mode

All commands support `--json` for machine-readable output:
```bash
cli-anything-renderdoc -c frame.rdc --json actions summary
```

## Environment Variables

| Variable              | Description                  |
|----------------------|------------------------------|
| `RENDERDOC_CAPTURE`  | Default capture file path   |
| `PYTHONPATH`         | Must include RenderDoc path |

## Agent Usage Notes

- Always specify `--json` for programmatic consumption
- Use `actions summary` first to understand capture complexity
- Use `actions list --draws-only` to focus on actual rendering
- Pipeline state requires an event ID from the action list
- Texture save supports: png, jpg, bmp, tga, hdr, exr, dds
- Buffer data can be decoded as hex, float32, uint32, or raw bytes
