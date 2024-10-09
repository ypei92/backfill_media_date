import os
import copy
import argparse
import logging
import shutil
import subprocess
import piexif
import ffmpeg

from PIL import Image, PngImagePlugin
from datetime import datetime

# Constants
REQUIRED_OS_NAME = "nt"
BACKUP_DIR_NAME = "backup_original"
FFMPEG_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
EXIFTOOL_EXE = "F:\Exiftool\exiftool.exe"  # exiftool path on Windows
EXIFTOOL_BACKUP_SUFFIX = '_original'  # Default backup file suffix by exiftool
EXIF_TIME_FORMAT = "%Y:%m:%d %H:%M:%S"
DEFAULT_EXIF = {"0th": {}, "Exif": {}, "1st": {}, "thumbnail": None, "GPS": {}}


def main():
  # This script needs to run on windows
  if os.name != REQUIRED_OS_NAME:
    raise Exception("This Python has to run on Windows, e.g. powershell.")

  # Get command line options
  args = cmdline_parser()

  # Set up logger
  logger.setLevel(getattr(logging, args.verbosity))
  logger.debug(args)

  # Create backup directory
  backup_dir = os.path.join(args.media_dir, BACKUP_DIR_NAME)
  if not os.path.exists(backup_dir):
    logger.debug(f"Create backup directory: {backup_dir}")
    os.mkdir(backup_dir)

  # Iterate over the media directory expect the backup directory
  all_media_names = os.listdir(args.media_dir)
  all_media_names.remove(BACKUP_DIR_NAME)
  for media_name in all_media_names:
    # Switch case
    logger.debug('-' * 20 + f" [Processing] {media_name} " + '-' * 20)
    media_path = os.path.join(args.media_dir, media_name)
    sfx = media_name.rsplit('.', 1)[-1]
    match sfx.lower():
      case "jpg" | "jpeg":
        process_jpg(args.real_run, media_path)

      case "png":
        datetime_str = get_earliest_date_str(media_path, EXIF_TIME_FORMAT)
        process_png(args.real_run, media_path, datetime_str)

      case "gif":
        process_gif(args.real_run, media_path, backup_dir, sfx)

      case "bmp":
        datetime_str = get_earliest_date_str(media_path, EXIF_TIME_FORMAT)
        process_bmp(args.real_run, media_path, datetime_str, backup_dir, sfx)

      case "mp4" | "m4v":
        process_mp4(args.real_run, media_path, backup_dir, sfx)

      case "mov" | "tif" | "heic" | "webp":
        logger.debug(f"Suffix .{sfx} seems fine: {media_name}")

      case _:
        raise Exception(f"Suffix .{sfx} is not supported: {media_name}")


def process_jpg(real_run: bool, media_path: str) -> None:
  """
  Process a jpg image.
  If exif data not present, assign a default one and re-open image.
  If piexif.ExifIFD.DateTimeOriginal in exif_dict["Exif"], assign datetime string
  Save image with the new exif metadata.
  """
  img = Image.open(media_path)

  # Skip images already with the "Date taken" field: DateTimeOriginal
  try:
    exif_dict = piexif.load(img.info["exif"])

  except Exception as e:
    logger.info("[No Exif metadata or corrupted] %s" % media_path)
    exif_dict = copy.deepcopy(DEFAULT_EXIF)

  if piexif.ExifIFD.DateTimeOriginal in exif_dict["Exif"]:
    logger.debug("[Date Taken is already present (JPG)] %s" % media_path)
    return

  # Assign creation date to data taken
  datetime_str = get_earliest_date_str(media_path, EXIF_TIME_FORMAT)
  exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime_str
  logger.info("[Assign Date Taken (JPG)] %s %s" % (media_path, datetime_str))

  # Save image with new exif metadata
  exif_bytes = piexif.dump(exif_dict)
  if real_run:
    try:
      img.save(media_path, exif=exif_bytes, quality="keep", optimize=True)
    except ValueError as e:
      logger.error(f"[Error] {e}")
      input("Press Enter to acknownledge and continue ...")
      img.save(media_path, exif=exif_bytes, quality=95, optimize=True)  # 95 highest


def process_png(real_run: bool, media_path: str, datetime_str: str) -> None:
  """
  Process a png image.
  Assign Creation Time -> Only help Windows property display
  Assign Date Time Original (What Immich use)
  """
  img = Image.open(media_path)

  # Skip if "Creation Time" is already present
  if "Creation Time" in img.info:
    logger.debug("[Date Taken is already present (PNG)] %s" % media_path)
    return

  # Set metadata: Creation Time
  metadata = PngImagePlugin.PngInfo()
  metadata.add_text("Creation Time", datetime_str)  # Windows Date Taken field
  metadata.add_text("Date Time Original", datetime_str)  # Immich
  logger.info("[Assign Date Taken (PNG)] %s %s" % (media_path, datetime_str))
  if real_run:
    img.save(media_path, pnginfo=metadata, quality="keep", optimize=True)


def process_bmp(real_run: bool, media_path: str, datetime_str: str,
                backup_dir: str, suffix: str) -> None:
  """
  Process a bmp image: convert to PNG to follow the PNG procedure
  """
  new_media_path = media_path.replace('.' + suffix, "_bmp.png")  # new path
  logger.info("[Convert BMP to PNG)] %s %s" % (media_path, new_media_path))
  if real_run:
    Image.open(media_path).save(new_media_path, quality="keep", optimize=True)
    shutil.move(media_path, backup_dir)  # backup
    process_png(real_run, new_media_path, datetime_str)


def process_gif(real_run: bool, media_path: str, backup_dir: str, suffix: str) -> None:
  """
  Process a gif image: assign -XMP with exiftool
  """
  if media_path.endswith("_immich." + suffix):
    logger.info("[Skip already-processed (GIF)] %s" % (media_path))
    return

  datetime_str = get_earliest_date_str(media_path, EXIF_TIME_FORMAT)
  new_media_path = media_path.replace('.' + suffix, "_immich." + suffix)
  logger.info("[Assign XMP:DateTimeOriginal to GIF)] %s %s" % (new_media_path, datetime_str))
  if real_run:
    set_xmp_exiftool(media_path, datetime_str)
    os.rename(media_path, new_media_path)
    shutil.move(media_path + EXIFTOOL_BACKUP_SUFFIX, backup_dir)


def process_mp4(real_run: bool, media_path: str, backup_dir: str, suffix: str) -> None:
  """
  Process a mp4 or m4v video.
  If any "tags" is missing or "creation_time" not in "tags" keys, use ffmpeg to
  add creation_time metadata via ffmpeg-python. Then save video with ffmpeg.exe.
  """
  # Go through the "streams" list and check tags
  vid = ffmpeg.probe(media_path)  # ffmpeg actual installed with Conda
  has_creation_time = True
  for section in vid["streams"]:
    if "tags" not in section or "creation_time" not in section["tags"]:
      has_creation_time = False
      break

  if not has_creation_time:
    new_media_path = media_path.replace('.' + suffix, "_immich." + suffix)
    datetime_str = get_earliest_date_str(media_path, FFMPEG_TIME_FORMAT)
    metadata = {"metadata": "creation_time=" + datetime_str}
    logger.info("[Assign Media Created (MP4)] %s %s", new_media_path, datetime_str)

    if real_run:
      (
          ffmpeg
          .input(media_path)
          .output(new_media_path,
                  **{'vcodec': 'copy', 'acodec': 'aac'},
                  **metadata)
          .overwrite_output()
          .run()
      )  # ffmpeg-python specifc format
      shutil.move(media_path, backup_dir)


def get_earliest_date_str(media_path: str, time_format: str) -> str:
  """Return datetime string for metadata: Date Created"""
  date_c = os.path.getctime(media_path)
  date_m = os.path.getmtime(media_path)
  date_approx = date_c if date_c < date_m else date_m
  datetime_str = datetime.fromtimestamp(date_approx).strftime(time_format)

  return datetime_str


def set_xmp_exiftool(image_path: str, datetime_str: str) -> None:
  """Use exiftool to set DateTimeOriginal for GIFs."""
  command = [
      EXIFTOOL_EXE,
      f"-XMP:DateTimeOriginal={datetime_str}",
      image_path
  ]

  subprocess.run(command, check=True)  # Run the command


def init_logger() -> logging.Logger:
  """Initialize a logger, logging to console."""
  # Get root logger
  logger = logging.getLogger(__name__)

  # Define an output style
  console_log_fmt = ("%(filename)s:%(funcName)s | [%(levelname)s] %(message)s")

  # Define a console logger
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(logging.Formatter(console_log_fmt))
  logger.addHandler(console_handler)

  return logger


def cmdline_parser() -> dict:
  """Command line parser for the media date convertor."""
  parser = argparse.ArgumentParser()
  parser.add_argument("-m", "--media-dir",
                      type=str,
                      required=True,
                      help="Full path of the target media directory.")

  parser.add_argument("--real-run",
                      action="store_true",
                      default=False,
                      help="Dry run is the default mode to avoid accident.")

  parser.add_argument("-v", "--verbosity",
                      type=str,
                      default="INFO",
                      choices=["DEBUG", "INFO", "ERROR"],
                      help="Specify the run time verbosity level")

  return parser.parse_args()


if __name__ == "__main__":
  logger = init_logger()  # Global logger
  main()
