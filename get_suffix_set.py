"""
Print the set of suffixes of a folder
"""

import os
import sys


def main():
  directory = sys.argv[1]

  suffix_set = set()
  for img_name in os.listdir(directory):
    sfx = img_name.rsplit('.', 1)[-1]
    suffix_set.add(sfx.lower())

  print(suffix_set)


if __name__ == "__main__":
  main()
