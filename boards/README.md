# UBDS Seed Boards (v1.1)

15 hand-curated UBDS v1.1 board files. Each was sourced from PlatformIO's
official platform JSON plus the manufacturer's product page. All boards
include `meta.product_url` pointing to the manufacturer's own page and
`meta.image_url` / `meta.pinout_image_url` pointing to stable URLs in
the `ubds-images` repository.

All files validate against `spec/ubds-v1.schema.json` via
`boards/tests/`. Run:

```bash
cd boards && python3 -m venv /tmp/c2venv \
  && /tmp/c2venv/bin/pip install -r tests/requirements.txt \
  && /tmp/c2venv/bin/pytest tests/ -v
```

## Board index

| Slug | Name | Manufacturer | Source 1 (PIO `url`) | Source 2 |
|---|---|---|---|---|
| `esp32-s3-devkitc-1` | Espressif ESP32-S3-DevKitC-1-N8 | Espressif Systems | https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/hw-reference/esp32s3/user-guide-devkitc-1.html | https://www.adafruit.com/product/5312 |
| `xiao-esp32-c3` | Seeed Studio XIAO ESP32C3 | Seeed Studio | https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/ | https://www.seeedstudio.com/seeed-xiao-esp32c3-p-5431.html |
| `rp2040-pico` | Raspberry Pi Pico | Raspberry Pi Ltd | https://www.raspberrypi.org/products/raspberry-pi-pico/ | https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf |
| `nrf52840-dk` | Nordic nRF52840-DK | Nordic Semiconductor | https://os.mbed.com/platforms/Nordic-nRF52840-DK/ | https://www.nordicsemi.com/Products/Development-hardware/nRF52840-DK |
| `nucleo-f446re` | ST Nucleo F446RE | STMicroelectronics | https://os.mbed.com/platforms/ST-Nucleo-F446RE/ | https://www.st.com/en/evaluation-tools/nucleo-f446re.html |
| `nucleo-h743zi` | ST Nucleo H743ZI | STMicroelectronics | https://www.st.com/en/evaluation-tools/nucleo-h743zi.html | https://os.mbed.com/platforms/ST-Nucleo-H743ZI/ |
| `feather-m0` | Adafruit Feather M0 | Adafruit Industries | https://www.adafruit.com/product/2772 | https://learn.adafruit.com/adafruit-feather-m0-basic-proto/ |
| `feather-m4-express` | Adafruit Feather M4 Express | Adafruit Industries | https://www.adafruit.com/product/3857 | https://learn.adafruit.com/adafruit-feather-m4-express-atsamd51 |
| `mimxrt1060-evk` | NXP i.MX RT1060 Evaluation Kit | NXP Semiconductors | https://www.nxp.com/design/development-boards/i.mx-evaluation-and-development-boards/mimxrt1060-evk-i.mx-rt1060-evaluation-kit:MIMXRT1060-EVK | https://www.nxp.com/products/processors-and-microcontrollers/arm-microcontrollers/i-mx-rt-crossover-mcus/i-mx-rt1060-crossover-mcu-with-arm-cortex-m7-core:i.MX-RT1060 |
| `arduino-uno-r4-wifi` | Arduino Uno R4 WiFi | Arduino | https://docs.arduino.cc/hardware/uno-r4-wifi | https://store-usa.arduino.cc/products/uno-r4-wifi |
| `seeed-wio-terminal` | Seeeduino Wio Terminal | Seeed Studio | https://www.seeedstudio.com/Wio-Terminal-p-4509.html | https://wiki.seeedstudio.com/Wio-Terminal-Getting-Started/ |
| `blackpill-f411ce` | WeAct Studio BlackPill V2.0 (STM32F411CE) | WeAct Studio | https://github.com/WeActStudio/WeActStudio.MiniSTM32F4x1 | https://github.com/WeActStudio/MiniSTM32F4x1 |
| `particle-boron` | Particle Boron | Particle Industries | https://docs.particle.io/boron | https://docs.particle.io/reference/datasheets/b-series/boron-datasheet/ |
| `adafruit-itsybitsy-m4` | Adafruit ItsyBitsy M4 Express | Adafruit Industries | https://www.adafruit.com/product/3800 | https://learn.adafruit.com/introducing-adafruit-itsybitsy-m4 |
| `adafruit-feather-nrf52840-sense` | Adafruit Feather Bluefruit Sense | Adafruit Industries | https://www.adafruit.com/product/4516 | https://learn.adafruit.com/adafruit-feather-sense |
