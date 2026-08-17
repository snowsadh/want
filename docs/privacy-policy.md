# WANT! Privacy Policy

Effective date: August 17, 2026

WANT! processes data only to provide the outfit-search and virtual try-on
features requested by the user. It does not sell data, serve advertising, or
collect analytics or telemetry.

## Data processed

- The user-selected portion of a webpage or an image the user uploads.
- The source page URL for a captured look.
- A full-body photo the user deliberately uploads for virtual try-on.
- Selected product information and the resulting saved look.

These categories correspond to Firefox's website content, browsing activity,
and personally identifying information disclosures. WANT! does not passively
collect browsing history or page content.

## How data is used

The extension sends data to the user-operated WANT! API only after a deliberate
action. The API sends the selected look to OpenAI to identify visible apparel
and find current products. When the user selects **Try this look**, the API sends
the uploaded full-body photo and supported selected garment images to Perfect
Corp.'s YouCam Clothes V3 API to create the preview.

## Storage and deletion

The default installation runs the WANT! API on the user's computer. Profile
metadata and saved looks are stored in local SQLite, and photos, captures,
validated product images, and generated images are stored in local private media
directories. Users can delete saved looks in WANT! and can delete all retained
data by removing the configured private data directories.

OpenAI and Perfect Corp. process submitted data under their respective privacy
terms. Retailer links open on the retailer's website and are then governed by
that retailer's policies.

## Security

Provider API keys remain in the local server environment. They are never
included in the Firefox extension, logs, fixtures, or committed source files.

Questions or privacy requests can be submitted at
https://github.com/snowsadh/want/issues.
