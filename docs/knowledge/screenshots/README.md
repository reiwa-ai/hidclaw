# Knowledge Screenshots

This directory keeps only screenshots that are useful as long-term implementation knowledge.

Rules:

- Do not put screenshots in the project root.
- Keep routine E2E artifacts on the Raspberry Pi under `/home/nama/pi/captures/`.
- When a screenshot must be brought back to the repository for documentation, place it under `docs/knowledge/screenshots/<stage>/`.
- Keep only representative evidence that explains a hardware, layout, UART, or capture issue. Delete one-off investigation images after the lesson is written in `docs/KNOWLEDGE.md`.

Current retained Stage01 screenshots:

```text
stage01/jis_layout_check_path_crop.png       JIS layout path rendering probe
stage01/step10_uart_wait_clean_crop2.png     UART wait / KEY ENTER mixing probe
stage01/step11_chunked_text_check.png        Chunked long TEXT verification
stage01/step12_backslash_notepad_check.png   Backslash/Yen key input verification
stage01/step12_dir_test_png_check.png        Windows path resolution with dir
```
