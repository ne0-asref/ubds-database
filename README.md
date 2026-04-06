# UBDS Database

The **Universal Board Description Standard** (UBDS) is an open, human-readable YAML format for describing development boards. It covers hardware specs, software ecosystem, and getting-started resources in a single file — from "what's on this PCB" to "how do I write my first program."

This repo is the source of truth for [DevBoardFinder](https://devboardfinder.com), a PCPartPicker-style directory for embedded development boards.

## What's in here

```
spec/ubds-v1.schema.json       JSON Schema for UBDS v1.0
boards/*.ubds.yaml              Board description files (one per board)
cli/                            Python CLI for validation, search, and import
templates/                      Starter templates for new board submissions
```

## Quick Start

### Browse boards

```bash
pip install -e cli/
dbf search --wifi --rust         # find boards with WiFi that support Rust
dbf info esp32-s3-devkitc-1      # show details for a specific board
```

### Add a board

```bash
cp templates/minimal.ubds.yaml boards/your-board.ubds.yaml
# Edit the file with your board's data
dbf validate boards/your-board.ubds.yaml
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

### Validate all boards

```bash
dbf validate boards/
```

## UBDS at a Glance

Every board is a single `.ubds.yaml` file. Required fields:

```yaml
ubds_version: "1.0"
name: "ESP32-S3-DevKitC-1"
slug: "esp32-s3-devkitc-1"
manufacturer: "Espressif"
board_type:
  - MCU
```

Beyond that, the spec covers: processing elements, wired/wireless interfaces, pin headers, power, thermal, boot, software support, community metrics, resources, libraries, pricing, and more. All optional — fill in what you can.

## Templates

| Template | Use case |
|----------|----------|
| [minimal](templates/minimal.ubds.yaml) | Start here. Required fields + processing + software (~45 lines) |
| [full](templates/full.ubds.yaml) | All common sections with comments (~230 lines) |
| [reference](templates/reference.ubds.yaml) | Fully-populated Jetson Orin Nano — every field filled in |

## Board Count

This database currently includes **15 boards** across ESP32, STM32, nRF, RP2040/RP2350, SAMD, i.MX, RISC-V, Raspberry Pi, Jetson, and Arduino families.

## Contributing

We welcome contributions from everyone — hobbyists, engineers, and manufacturers. See [CONTRIBUTING.md](CONTRIBUTING.md) for ground rules, the step-by-step guide, and the confidence standard.

## License

- **Code** (CLI, scripts): [Apache-2.0](LICENSE)
- **Board data** (YAML files): [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)
