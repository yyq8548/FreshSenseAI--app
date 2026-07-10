# Development Log: Private Local Scan History

**Date:** July 10, 2026

## Goal

Add useful desktop memory without introducing accounts, cloud storage, or photo
retention.

## Completed

- Added a versioned local history format with validation and atomic writes.
- Limited retention to the 200 newest scan records.
- Stored only result metadata and the image's base file name.
- Excluded full image paths, image bytes, reasoning traces, and tentative
  uncertain classifications from history.
- Added a **View scan history** desktop dialog with recent-result viewing.
- Added user-directed CSV export.
- Added a confirmation step before clearing history.
- Added an environment override, `FRESHSENSE_HISTORY_PATH`, for tests and
  managed installations.
- Added automated coverage for round trips, retention limits, corrupt data,
  privacy, uncertain results, CSV export, clearing, and path overrides.

## Storage Location

On Windows, the default path is:

`%LOCALAPPDATA%\FreshSense\scan_history.json`

The application creates the parent directory only when the first result is
saved.

## Privacy Boundary

FreshSense does not copy or retain photos. History stays on the device unless
the user explicitly exports a CSV file. The exported CSV contains the same
metadata fields and does not contain images.
