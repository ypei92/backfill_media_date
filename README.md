# Backfill Empty Media Date with File Create Date
This repository provides scripts to backfill `Date Taken` for photos and `Media Created` for videos with file creation date or file modification date, whichever is earlier.
**Please make backups (e.g. add to archive) before trying this repository to avoid unexpected modifications!**

Supported formats
- [x] JPG / JPEG
- [x] PNG / BMP (convert to PNG)
- [x] GIF
- [x] MP4 / M4V

Skipped formats: MOV, TIF, HEIC

## Motivation
During my attempt of migrating photos/videos from iCloud to [Immich](https://immich.app/) (self-hosted photo app),
I realize that many photos and few videos do not have proper `Date Taken` or `Media Create` dates via Windows explorer.
Most of those images are PS'ed images, screenshots or from specific apps such as insta360, snapseeds, _etc_.
When uploading those "empty-date" media to Immich, all of them appear on the date of upload,
which really doesn't make sense and degrades the experience of using a photo app.
Therefore, I created those scripts to **assign a legit date to those media**.
The date I'm using is file creation date or file modification date, whichever is earlier.

## Setup
1. **This script is only tested on Windows.** Why? Linux by default does not store the file creation time. MacOS seems to store `birth time`, but I have not explored MacOS yet
2. Create a Python environment, e.g. [miniconda](https://docs.anaconda.com/miniconda/miniconda-install/)
3. `git clone https://github.com/ypei92/backfill_media_date.git && cd backfill_media_date`
4. Setup Python dependencies via `pip install -r requirements.txt`

## Execution
1. Check formats (see if there are unsuppoted formats, skip or add functionality)
```
python .\get_suffix_set.py path\to\your\folder
```
2. Dry run to check breakages
```
python .\backfill_media_date.py -m path\to\your\folder -v INFO
```
3. Real run
```
python .\backfill_media_date.py -m path\to\your\folder -v INFO --real-run
```
