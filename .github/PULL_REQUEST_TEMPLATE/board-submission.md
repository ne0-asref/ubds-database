## Board Submission

**Board name:** <!-- e.g. ESP32-S3-DevKitC-1 -->
**Manufacturer:** <!-- e.g. Espressif -->
**Board type:** <!-- MCU / SBC / SoM / FPGA / etc. -->

## Checklist

- [ ] File is named `boards/{slug}.ubds.yaml` and slug matches the `slug` field inside
- [ ] `ubds_version: "1.0"` is set
- [ ] Required fields filled: `name`, `slug`, `manufacturer`, `board_type`
- [ ] At least one processing element with `role: primary`
- [ ] `meta.sources[]` has at least one verifiable public URL
- [ ] `meta.data_completeness` is set (`full` / `partial` / `stub`)
- [ ] `meta.confidence` ratings are set for populated sections
- [ ] `dbf validate` passes (paste output below)

## Validation output

```
<!-- Paste the output of: dbf validate boards/your-board.ubds.yaml -->
```

## Data sources

<!-- List the URLs you used to fill in this board's data -->

- 

## Confidence notes

<!-- Optional: explain any low-confidence sections or fields you're unsure about -->

## Image

- [ ] I submitted a top-view image to [ubds-images](https://github.com/ne0-asref/ubds-images) (or will submit separately)
- [ ] No image available yet
