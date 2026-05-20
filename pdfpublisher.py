import argparse
from database import init_db, connect_to_db
from copy import deepcopy
import sys
import re
import io
import shutil
from utils import *
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors
from classes import Course, create_course_object
from config import load_config

BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[31m"
WHITE = "\033[37m"
GREEN = "\033[32m"

#############################################################################
# Tekstin lisäys otsikkosivulle
#############################################################################

def split_to_lines(linecount, text):
    lines = [""]*linecount
    words = text.split()
    target = len(text)/linecount
    line = 0
    try:
        while(True):
            while len(lines[line])<target:
                lines[line] = f"{lines[line]} {words.pop(0)}"
            line += 1
    except IndexError:
        pass
    return lines

def add_title(page: PageObject, lectureterm: str, lecturenum: int, lecturetitle: str,font: str,font_max_size: int,font_min_size: int,font_colour: str,maxlines: int):

    #Page and text area width
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    textwidth = width -100
    text = [f"{lectureterm} {lecturenum}",lecturetitle]

    #Font size settings
    font_size = font_max_size
    
    #Adjust font size
    while not all(stringWidth(line,font,font_size) <= textwidth for line in text):
        if font_size > font_min_size:
            font_size -= 1
        elif len(text) == maxlines:
            break
        else:
            #Lisätään rivejä
            newlinecount = len(text)
            text[1:] = split_to_lines(newlinecount,lecturetitle)
            font_size = font_max_size
    packet = io.BytesIO()
    c = canvas.Canvas(packet, (width, height))
    c.setFont(font,font_size)
    c.setFillColor(getattr(colors,font_colour, colors.white))
    lineheight = font_size * 1.2
    drawheight = height/2 + (len(text)*lineheight)/2
    for line in text:
        c.drawCentredString(width / 2.0, drawheight,line)
        drawheight -= lineheight
    c.save()
    packet.seek(0)
    page.merge_page(PdfReader(packet).pages[0])

#############################################################################
# Tiedostojen haku
#############################################################################
def load_directory(directory,lang = None):
    files = {}
    folder = Path(directory)
    if lang is None:
        dir_files = folder.glob("*.pdf")
    elif lang == "":
        dir_files = [f for f in folder.glob("*.pdf") if not re.compile(r"_\w{2}\.pdf$").search(f.name)]
    else:
        dir_files = folder.glob(f"*_{lang}.pdf")
    for f in dir_files:
        match = re.search(r'\d+', f.stem)
        num = int(match.group()) if match else None
        if isinstance(num, int):
            mtime = f.stat().st_mtime
            files[num] = {}
            files[num]["file"] = f
            files[num]["modtime"] = mtime
    for f in folder.glob("*"):
        mtime = f.stat().st_mtime
        files[f.name] = {}
        files[f.name]["file"] = f
        files[f.name]["modtime"] = mtime
    return files

def load_full_directory(directory):
    files = {}
    folder = Path(directory)
    for f in folder.glob("*"):
        mtime = f.stat().st_mtime
        files[f.name] = {}
        files[f.name]["file"] = f
        files[f.name]["modtime"] = mtime
    return files

def link_health_check(config, pub, silent):
    if not silent:
        print("Tarkistetaan linkit")
    for pub in publications:
        courseObject = create_course_object(config, pub)
        if not silent:
            print(f"Tarkistetaan kurssi {courseObject.name}")
        for n in range(1, courseObject.lectures + 1):
            matpubdir = f"{courseObject.publication_dir}/{courseObject.lectureterm} {n:02}"
            matpubpath = Path(matpubdir)
            if not matpubpath.exists():
                print(f"Skipping {matpubdir}: not found")
                continue
            materials_published = load_full_directory(matpubdir)
            # Run health check for links
            files = []
            
            for v in materials_published.values():
                files.append(v.get("file"))

            for file in files:
                dead, alive = run_health_check(file._raw_paths[0])

                if dead:
                    cur = connect_to_db()
                    add_dead_links_to_db(cur, file._raw_paths[0], dead)
                    print("Seuraavat linkit eivät toimi:")
                    for link in dead:
                        print(f"{link.get('file')} (sivu {link.get('page_number')}): {link.get('url')} virhekoodi: {link.get('error_code')}")  
                else:
                    if not silent:
                        print(f"Tiedoston {file.name} kaikki linkit toimivat oikein.")
    sys.exit(0)


def checkLinksOnFile(file, silent):
    dead, alive = run_health_check(file)
    if dead:
        cur = connect_to_db()
        add_dead_links_to_db(cur, file, dead)
        print("Seuraavat linkit eivät toimi:")
        for link in dead:
            print(f"{link.get('file')} (sivu {link.get('page_number')}): {link.get('url')} virhekoodi: {link.get('error_code')}")  
    else:
        if not silent:
            print(f"Tiedoston {file.name} kaikki linkit toimivat oikein.")
    sys.exit(0)

def publish_lectures(courseObject,config,lang):
        #Load slide update dates
        pubslides = load_directory(courseObject.course_slides_dir,lang)
        slide_updates = load_directory(config['settings']['lecture_slides_dir'])
        if not lang == "":
            suffix = f"_{lang}.pdf"
        else:
            suffix = ".pdf"
        # Load header/footer slides
        # Should be moved to courseObject class to remove need to pass config here...

        pStartingslides = Path(courseObject.course_slides_dir) / f"{config['settings']['headerfile']}{suffix}"
        pDividerslides = Path(courseObject.course_slides_dir) / f"{config['settings']['dividerfile']}{suffix}"
        pEndingslides = Path(courseObject.course_slides_dir) / f"{config['settings']['footerfile']}{suffix}"

        
        aOK = pStartingslides.exists()
        kOK = pDividerslides.exists()
        lOK = pEndingslides.exists()
        if aOK and kOK and lOK:
            Startingslides = PdfReader(Path(courseObject.course_slides_dir) / f"{config['settings']['headerfile']}{suffix}")
            Dividerslides = PdfReader(Path(courseObject.course_slides_dir) / f"{config['settings']['dividerfile']}{suffix}")
            Endingslides = PdfReader(Path(courseObject.course_slides_dir) / f"{config['settings']['footerfile']}{suffix}")
        else:
            print(f"  \\_{RED}Otsikkokalvoja ei ole vielä saatavilla! {RESET}")
            if aOK:
                print(f"    \\_{GREEN}Aloituskalvo ok{RESET}")
            else:
                print(f"    \\_{RED}Aloituskalvo puuttuu{RESET}")
            if kOK:
                print(f"    \\_{GREEN}Välikalvo ennen tehtäviä ok{RESET}")
            else:
                print(f"    \\_{RED}Välikalvo ennen tehtäviä puuttuu{RESET}")
            if lOK:
                print(f"    \\_{GREEN}Lopetuskalvo ok{RESET}")
            else:
                print(f"    \\_{RED}Lopetuskalvo puuttuu{RESET}")
            return

        # Go through all or a subset of lectures
        for n in range(1, courseObject.lectures+1):
            print(f"  \\_{config[pub]['lectureterm']} {n} ({courseObject.lecture_list[n-1].name})") 

            # Check if the publication folder exists, create if necessary, check published file
            matpubdir = f"{courseObject.publication_dir}/{courseObject.lectureterm} {n:02}"
            matpubpath = Path(matpubdir)
            if not matpubpath.exists():
                matpubpath.mkdir(parents=True, exist_ok=True)
            filename = re.sub(r'[\\/]', '', f"{n:02} - {courseObject.filename_prefix} {courseObject.lectureterm.lower()} {n} – {courseObject.lecture_list[n-1].name}{suffix}")[:200]
            published_slides = matpubpath / filename

            # First check the slides, later additional materials
            updateFlag = False
            missingSlides = False

            for topic in courseObject.lecture_list[n-1].topic_list:
                topic = f"{topic}{suffix}"
                if not topic in slide_updates:
                    print(f"    \\_{RED}Aihe {topic}: luentokalvot eivät vielä saatavilla{RESET}")
                    missingSlides = True
                elif published_slides.exists() and slide_updates[topic]["modtime"] <= published_slides.stat().st_mtime:
                    if not silent:
                        print(f"    \\_{WHITE}Aihe {topic}: ajan tasalla!{RESET}")
                else:
                    if not silent:
                        print(f"    \\_{BOLD}Aihe {topic}: luentokalvot päivitetty, voi julkaista!{RESET}")
                    updateFlag = True
            if not n in pubslides:
                print(f"    \\_{RED}Kurssikohtaiset täydentävät kalvot eivät vielä saatavilla!{RESET}")	    
                missingSlides = True
            elif published_slides.exists() and pubslides[n]["modtime"] <= published_slides.stat().st_mtime:
                if not silent:
                    print(f"    \\_{WHITE}Kurssikohtaiset täydentävät kalvot ajan tasalla!{RESET}")
            else:
                if not silent:
                    print(f"    \\_{BOLD}Kurssikohtaiset täydentävät kalvot päivitetty, voi julkaista!{RESET}")
                updateFlag = True
            if updateFlag and not missingSlides:
                if not published_slides.exists():
                    if not silent:
                        print(f"    \\_{BOLD}Ei vielä julkaistu -> julkaistaan{RESET}")
                else:
                    if not silent:
                        print(f"    \\_{BOLD}Materiaalia on päivitetty -> julkaistaan{RESET}")

                try:
                    newslides = PdfWriter()

                    # Take starting slide, update course and lecture name
                    firstslide = deepcopy(Startingslides.pages[0])
                    add_title(firstslide,courseObject.lectureterm,n,courseObject.lecture_list[n-1].name,config["titlefont"]["font"],int(config["titlefont"]["font_max_size"]),int(config["titlefont"]["font_max_size"]),config["titlefont"]["colour"],int(config["titlefont"]["maxlines"]));

                    newslides.add_page(firstslide)
                    for page in Startingslides.pages[1:]:
                        newslides.add_page(page)

                    # make lecture slides from topics
                    for topic in courseObject.lecture_list[n-1].topic_list:
                        Lectureslides = PdfReader(slide_updates[f"{topic}{suffix}"]["file"])
                        for page in Lectureslides.pages:
                            newslides.add_page(page)

                    # Insert divider slides
                    for page in Dividerslides.pages:
                        newslides.add_page(page)

                    # Insert course-specific slides into the placeholder
                    Courseslides = PdfReader(pubslides[n]["file"])
                    for page in Courseslides.pages:
                        newslides.add_page(page)

                    # Insert footer slides
                    for page in Endingslides.pages:
                        newslides.add_page(page)

                    # Write to file
                    if not silent:
                        #print("Luodaan pdf...")
                        print(f"    \\_{BOLD}Tallennetaan PDF{RESET}")
                    filename = re.sub(r'[\\/]', '', f"{n:02} - {config[pub]['filename_prefix']} {config[pub]['lectureterm']} {n}: {courseObject.lecture_list[n-1].name}{suffix}")[:200]
                    with open(published_slides,"wb") as f:
                        newslides.write(f)
                except TimeoutError:
                    print(f"    \\_{RED}❌ Error: Connection timed out while accessing '{filename}'. Network drive issue?{RESET}")        
                except FileNotFoundError:
                    print(f"    \\_{RED}❌ Error: The file '{filename}' could not be found.{RESET}")
                 

def publish_materials(courseObject,config):
    # Go through all or a subset of lectures
    for n in range(1, courseObject.lectures+1):
        # Check materials
        # Check if the publication folder exists, create if necessary, check published file
        matpubdir = f"{courseObject.publication_dir}/{courseObject.lectureterm} {n:02}"
        matpubpath = Path(matpubdir)
        if not matpubpath.exists():
            matpubpath.mkdir(parents=True, exist_ok=True)
        materials_for_all = load_full_directory(f"{config['settings']['lecture_slides_dir']}/{n:02}")
        materials_forcourse = load_full_directory(f"{courseObject.course_slides_dir}/{n:02}")
        materials_published = load_full_directory(matpubdir)
        materialcount = len(materials_for_all) + len(materials_forcourse)
        if materialcount == 0:
            print(f"  \\_{config[pub]['lectureterm']} {n}: ei materiaaleja")
        else:
            print(f"  \\_{config[pub]['lectureterm']} {n}: yhteensä {materialcount} materiaalia jaettavaksi") 
            for filename, file in materials_for_all.items():
                if filename not in materials_published:
                    if not silent:
                        print(f"    \\_{BOLD}Tiedostoa {filename} ei ole vielä julkaistu, julkaistaan.{RESET}")
                    shutil.copy2(file['file'], matpubpath / filename)
                elif file["modtime"] > materials_published[filename]["modtime"]:
                    if not silent:
                        print(f"    \\_{BOLD}Tiedostosta {filename} on uudempi versio, julkaistaan.{RESET}")
                    shutil.copy2(file['file'], materials_published[filename]["file"])
                else:
                    if not silent:
                        print(f"    \\_{WHITE}Tiedosto {filename} on ajan tasalla{RESET}")
            for filename, file in materials_forcourse.items():
                if filename not in materials_published:
                    if not silent:
                        print(f"    \\_{BOLD}Tiedostoa {filename} ei ole vielä julkaistu, julkaistaan.{RESET}")
                    shutil.copy2(file['file'], matpubpath / filename)
                elif file["modtime"] > materials_published[filename]["modtime"]:
                    if not silent:
                        print(f"    \\_{BOLD}Tiedostosta {filename} on uudempi versio, julkaistaan.{RESET}")
                    shutil.copy2(file['file'], materials_published[filename]["file"])
                else:
                    if not silent:
                        print(f"    \\_{WHITE}Tiedosto {filename} on ajan tasalla{RESET}")

    
#############################################################################
# MAIN
#############################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Publisher for Lecture Materials")
    parser.add_argument("--linkcheck", "-l", action="store_true", help="Run link health check")
    parser.add_argument("--silent", "-s", action="store_true", help="Silent mode, minimal output")
    parser.add_argument("--checkfile", "-f", type=str, help="Check links in a specific PDF file")
    args = parser.parse_args()
    
    silent = args.silent

    (config, publications) = load_config()
    if not silent:
        print("Config loaded successfully!")


    if args.checkfile:
        if not silent:
            print("Tarkistetaan linkit tiedostosta:", args.checkfile)
        checkLinksOnFile(args.checkfile, silent)
    
    #link health check
    if args.linkcheck:
        link_health_check(config, publications, silent)

    #Main program
    for pub in publications:
        if not silent:
            print(f"*****************************************\nTarkistetaan {config[pub]['coursename']}")
        courseObject = create_course_object(config, pub)
        print(f"\\_Tarkistetaan suomenkieliset luennot")
        publish_lectures(courseObject,config,"")
        if not config[pub]['translate_to'] == "":
            for lang in config[pub]['translate_to'].split(","):
                print(f"\\_Tarkistetaan käännökset fi->{lang}")
                publish_lectures(courseObject,config,lang)
        print(f"\\_Tarkistetaan materiaalikansiot")
        publish_materials(courseObject,config)
