import os
import sys

import dateparser
import emoji
import unidecode as _unidecode
import yaml
from puz import Puzzle
from unidecode import unidecode

from html2text import html2text


# The unidecode module converts Unicode strings to plain ASCII. The puz format,
# however, can accept latin-1, which is a larger subset. By adding cached
# replacement values for these characters to unidecode, we prevent it from
# changing them.
_unidecode.Cache[0] = [chr(c) if c > 127 else "" for c in range(256)]

CONFIG_PATH = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
CONFIG_PATH = os.path.join(CONFIG_PATH, "xword-dl/xword-dl.yaml")

if not os.path.exists(CONFIG_PATH):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    open(CONFIG_PATH, "a").close()


class XWordDLException(Exception):
    pass


def save_puzzle(puzzle: Puzzle, filename: str):
    if not os.path.exists(filename):
        puzzle.save(filename)
        msg = (
            "Puzzle downloaded and saved as {}.".format(filename)
            if sys.stdout.isatty()
            else filename
        )
        print(msg)
    else:
        print(
            "Not saving: a file named {} already exists.".format(filename),
            file=sys.stderr,
        )


def join_bylines(byline_list: list[str], and_word="&"):
    return (
        ", ".join(byline_list[:-1]) + f", {and_word} " + byline_list[-1]
        if len(byline_list) > 2
        else f" {and_word} ".join(byline_list)
    )


def remove_invalid_chars_from_filename(filename: str):
    invalid_chars = r'<>:"/\|?*'

    for char in invalid_chars:
        filename = filename.replace(char, "")

    return filename


PUNCTUATION_TRANS = str.maketrans({
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "‹": "'",
    "›": "'",
    "—": "--",
    "–": "-",
    "‐": "-",
    "‑": "-",
    "−": "-",
    "…": "...",
    "\u2002": " ",
    "\u2003": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
})


def can_encode_latin1(text: str) -> bool:
    if not text:
        return True
    normalized = text.translate(PUNCTUATION_TRANS)
    try:
        normalized.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def cleanup(field: str, preserve_html=False, utf8=False):
    if not field:
        return ""
    if preserve_html:
        field = emoji.demojize(field).strip()
    else:
        field = emoji.demojize(html2text(field, bodywidth=0)).strip()
    if not utf8:
        field = unidecode(field).strip()
    return field


def sanitize_for_puzfile(puzzle: Puzzle, preserve_html=False, force_utf8=False) -> Puzzle:
    all_texts = [
        puzzle.title,
        puzzle.author,
        puzzle.copyright,
        puzzle.notes,
        getattr(puzzle, "solution", ""),
        getattr(puzzle, "fill", ""),
    ] + (puzzle.clues or [])

    needs_utf8 = force_utf8 or any(not can_encode_latin1(t) for t in all_texts if t)

    if needs_utf8:
        puzzle.set_version("2.0")
        puzzle.encoding = "UTF-8"

    puzzle.title = cleanup(puzzle.title, preserve_html, utf8=needs_utf8)
    puzzle.author = cleanup(puzzle.author, preserve_html, utf8=needs_utf8)
    puzzle.copyright = cleanup(puzzle.copyright, preserve_html, utf8=needs_utf8)

    puzzle.notes = cleanup(puzzle.notes, preserve_html, utf8=needs_utf8)

    puzzle.clues = [cleanup(clue, preserve_html, utf8=needs_utf8) for clue in puzzle.clues]

    return puzzle


def parse_date(entered_date: str):
    return dateparser.parse(entered_date, settings={"PREFER_DATES_FROM": "past"})


def parse_date_or_exit(entered_date: str):
    guessed_dt = parse_date(entered_date)

    if not guessed_dt:
        raise XWordDLException(
            'Unable to determine a date from "{}".'.format(entered_date)
        )

    return guessed_dt


def update_config_file(heading: str, new_values_dict: dict):
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f) or {}

    if heading not in config:
        config[heading] = {}

    config[heading].update(new_values_dict)

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)


def read_config_values(heading: str):
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f) or {}

    # config file keys and command line flags use '-', python uses '_', so we
    # replace '-' with '_' for the settings object
    raw_subsettings = config.get(heading) or {}
    subsettings = {k.replace("-", "_"): raw_subsettings[k] for k in raw_subsettings}

    return subsettings
