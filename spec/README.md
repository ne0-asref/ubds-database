# UBDS — Universal Board Description Standard v1.0

A portable, human-readable standard for describing development boards. UBDS bridges from "what's on this PCB" to "how do I write my first program" — covering hardware specs, software ecosystem, and getting-started resources in a single file.

## Quick Start

Board files use YAML with the `.ubds.yaml` extension:

```yaml
ubds_version: "1.0"
name: "ESP32-S3-DevKitC-1"
slug: "esp32-s3-devkitc-1"
manufacturer: "Espressif"
board_type:
  - MCU
difficulty_level: beginner
```

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `ubds_version` | string | Must be `"1.0"` |
| `name` | string | Display name |
| `slug` | string | URL-safe unique ID (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`) |
| `manufacturer` | string | Board manufacturer |
| `board_type` | string[] | At least one of: MCU, SBC, SoM, Carrier, Expansion, FPGA, AI, SDR, Industrial, DSP, Other |

When `meta` is present, `meta.sources` (array of URLs) is also required.

## Sections

All sections are optional. Omit what doesn't apply.

| Section | Description |
|---------|-------------|
| `processing` | CPU, GPU, NPU, FPGA, TPU — supports heterogeneous compute |
| `interfaces` | Physical wired connectors (USB, Ethernet, HDMI, debug) |
| `pin_headers` | Exposed pin headers with peripheral counts and pinouts |
| `wireless` | WiFi, Bluetooth, LoRa, Zigbee, Thread, NFC, UWB, Cellular |
| `inputs` / `outputs` | Buttons, switches, LEDs, displays |
| `onboard_components` | Sensors, actuators, memory, power management, audio, networking |
| `power` | Input voltage, battery, consumption profiles |
| `thermal` | TDP, operating temp range, heatsink |
| `physical` | Dimensions, form factor, mounting holes |
| `boot` | Boot media, bootloader, boot time |
| `sdr` | SDR-specific specs (frequency range, sample rate, channels) |
| `certifications` | FCC, CE, RoHS, etc. |
| `software` | Languages, frameworks, OS, AI/ML tools, IDEs, debuggers |
| `community` | GitHub repos, forums, Stack Overflow, Discord |
| `resources` | Learning resources at board, controller, and core levels |
| `libraries` | Key software libraries |
| `compatible_boards` | Cross-references to carriers, shields, HATs |
| `metadata` | Official page, images, datasheets, schematics |
| `pricing` | MSRP and vendor listings |
| `meta` | Sources, verification status, per-section confidence |

## Extensibility

Unknown fields are allowed at every level. The schema uses `additionalProperties: true` throughout, so custom fields won't break validation.

## Validation

Validate against the JSON Schema:

```bash
# With the dbf CLI
dbf validate boards/my-board.ubds.yaml

# With any JSON Schema validator
check-jsonschema --schemafile spec/ubds-v1.schema.json boards/my-board.ubds.yaml
```

## Schema

- **JSON Schema:** [`ubds-v1.schema.json`](ubds-v1.schema.json) (JSON Schema Draft 2020-12)
- **Reference board:** [`artifacts/ubds-v1-spec.yaml`](../artifacts/ubds-v1-spec.yaml) (Jetson Orin Nano, all fields populated)

## License

- Schema and spec: Apache-2.0
- Board data: CC-BY-4.0
