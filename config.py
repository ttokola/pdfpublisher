from configparser import ConfigParser
import configparser
from pathlib import Path
import sys

#############################################################################
# CONFIGURATION
#############################################################################
CONFIG_FILE = Path("settings.ini")
HEADER_FILE = "header"
FOOTER_FILE = "footer"

# Required mandatory configurations
REQUIRED_SETTINGS = {
	"settings": ["lecture_slides_dir","headerfile","footerfile","dividerfile"],
	"gen_ai": ["AI","API_KEY","model","batch_size","request_timeout_ms","max_requests_per_minute"],
        "titlefont": ["font","font_max_size","font_min_size","colour","maxlines"]
}

# Mandatory options for all publications
PUBLICATION_OPTIONS = set(["coursecode", 
						   "translate_to",
						   "ai_prompt",
						   "publish_dir",
						   "coursesize",
						   "lectures",
						   "coursename",
						   "filename_prefix",
						   "lectureterm",
						   "course_slides_dir"])

#############################################################################
# Load and validate
#############################################################################
def load_config():
    config = ConfigParser()

    # Read existing file (if any)
    try:
        if CONFIG_FILE.exists():
            config.read(CONFIG_FILE)
        else:
            print(f"[ERROR] Config file not found. Creating new {CONFIG_FILE}.")
            CONFIG_FILE.touch()

    except configparser.DuplicateSectionError as e:
        print("[ERROR] duplicate section found in settings.ini:", e.section)
        sys.exit(1)
    except configparser.ParsingError as e:
        print("[ERROR] parsing error in settings.ini:", e)
        sys.exit(1)
    except configparser.DuplicateOptionError as e:
        print("[ERROR] duplicate option found in settings.ini under section:", e.section, "option:", e.option)
        sys.exit(1)
    modified = False
    missing = []
    publications = []
  
    # Ensure all mandatory sections/keys exist
    for section, keys in REQUIRED_SETTINGS.items():
        if not config.has_section(section):
            config.add_section(section)
            modified = True

        for key in keys:
            if not config.has_option(section, key) or not config[section][key].strip():
                config.set(section, key, "")  # ensure entry exists but is empty
                modified = True
                missing.append(f"{section}.{key}")
              
    # Do we have publication targets?
    for section in config.sections():
      # Collect keys present in this section
      keys = set(config[section].keys())
      # Check if all required options are there
      if PUBLICATION_OPTIONS.issubset(keys):
        publications.append(section)    
    if len(publications) == 0:
      config.add_section("publication")
      for key in PUBLICATION_OPTIONS:
        config.set("publication",key, "") #add empty publication key
      modified = True
      
    # Save any modifications back to file
    if modified:
        with open(CONFIG_FILE, "w") as f:
            config.write(f)

    # If anything missing -> exit with error
    if missing:
        print("[ERROR] Missing mandatory settings:")
        for item in missing:
            print(f"  - {item}")
        print(f"\nPlease edit {CONFIG_FILE} and fill in the missing values.")
        sys.exit(1)
    if len(publications) == 0:
        print(f"[ERROR] At least one publication required! Added empty one to {CONFIG_FILE}!")
        sys.exit(1)	
    return (config,publications)
