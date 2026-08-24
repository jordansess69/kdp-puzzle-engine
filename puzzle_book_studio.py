"""Simple, self-contained builders for non-word-search puzzle books.

This module deliberately keeps Sudoku, Cryptograms, and Scramble + Trivia
separate from the word-search engine.  They share the same print size, cover
workflow, package folder, and KDP checks without changing word placement.
"""
from __future__ import annotations
import json, math, os, random, re, shutil, subprocess, sys, threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

APP = Path(__file__).resolve().parent
OUT = APP / "out"
CONTENT_LIBRARY = APP / "word_banks" / "puzzle_content_library.json"
MASTER_WORD_BANK = APP / "word_banks" / "Guided_Builder_Master_Word_Bank.json"
CONTENT_BUFFER = 1.60  # Every ready pack keeps 60% more unique entries than one book needs.
MIN_VERIFIED_LIBRARY = 130  # A release-ready standard library never has fewer than 130 checked entries.
TARGET_VERIFIED_LIBRARY = 180  # Supports 100-puzzle Signature Editions with room for replacements.
FORMAT_PRESETS = {
    "Standard": {"count": 60, "difficulty": "Standard", "label": "A full-size, clear-format puzzle book."},
    "Large Print": {"count": 48, "difficulty": "Easy", "label": "Fewer puzzles with generous space and easy-to-read pages."},
    "Kids": {"count": 48, "difficulty": "Easy", "label": "Friendly pacing and approachable difficulty."},
    "Signature Edition": {"count": 100, "difficulty": "Mixed", "label": "A premium 100-puzzle edition; requires a 160-entry library."},
}
PAGE_W, PAGE_H = letter
MARGIN = 54
from font_utils import pdf_font_candidates, register_pdf_font

# Interior PDFs keep the same Book* aliases as always; font_utils resolves
# which actual file backs each alias on this machine.
BOOK_FONT_FAMILIES = {"BookSans": "sans", "BookBold": "sans-bold", "BookMono": "mono-bold"}
ART = {
    "Sudoku": (("puzzle_sudoku_numbers_v1.png", "puzzle_sudoku_calm_v2.png", "puzzle_sudoku_geometric_v3.png"), "starlight-indigo", "photo"),
    "Cryptogram": (("puzzle_cryptogram_cipher_v1.png", "puzzle_cryptogram_vintage_v2.png", "puzzle_cryptogram_artdeco_v3.png"), "library-burgundy", "photo"),
    "Word Scramble + Trivia": (("puzzle_scramble_trivia_v1.png", "puzzle_scramble_gamenight_v2.png", "puzzle_scramble_retroquiz_v3.png"), "tropical-pop", "photo"),
    "Mixed Brain Games": (("puzzle_scramble_gamenight_v2.png", "puzzle_sudoku_geometric_v3.png", "puzzle_cryptogram_artdeco_v3.png"), "midnight-gold", "photo"),
}
# Theme-aware artwork keeps a space book from receiving a generic game-night
# cover and lets the one-screen studio make a sound automatic choice.
THEME_ART = {
    "Space & Astronomy": (("space_astronomy.png", "space_planet_v2.png", "space_rocket_v3.png"), "starlight-indigo", "photo"),
    "Garden & Growing": (("gardening.png", "gardening_greenhouse_v2.png", "gardening_vegetables_v3.png"), "gardening", "photo"),
    "Travel & Adventure": (("travel_history.png", "travel_skyline_v3.png", "travel_suitcase_v2.png"), "retro-travel-and-landmarks", "photo"),
    "General Knowledge & Curiosity": (("puzzle_scramble_trivia_v1.png", "puzzle_scramble_gamenight_v2.png", "puzzle_scramble_retroquiz_v3.png"), "tropical-pop", "photo"),
}
DEFAULTS = {
    "Sudoku": ("Large Print Sudoku", "100 Number, Letter & Shape Logic Puzzles with Full Solutions", 100, "Mixed"),
    "Cryptogram": ("Cryptogram Challenge", "60 Clever Code-Breaking Puzzles with Solutions", 60, "Standard"),
    "Word Scramble + Trivia": ("Word Scramble & Trivia", "60 Fun Word Games and General Knowledge Challenges", 60, "Standard"),
    "Mixed Brain Games": ("The Everyday Brain Games Collection", "60 Sudoku, Cryptograms, and Word Scramble Challenges", 60, "Mixed"),
}

AVAILABLE_THEMES = ("General Starter", "General Knowledge & Curiosity", "Space & Astronomy", "Garden & Growing", "Travel & Adventure")

CRYPTOS = [
 "A QUIET MIND CAN NOTICE SMALL DETAILS", "PRACTICE MAKES PATTERNS EASIER TO SEE",
 "EVERY CLUE HAS A PLACE IN THE BIGGER PICTURE", "GOOD QUESTIONS LEAD TO BETTER ANSWERS",
 "PATIENT THINKING TURNS CONFUSION INTO PROGRESS", "A SHORT BREAK CAN REFRESH A BUSY BRAIN",
 "CURIOSITY MAKES ORDINARY DAYS MORE INTERESTING", "SMALL STEPS CAN SOLVE A LARGE PROBLEM",
 "THE BEST CLUES OFTEN HIDE IN PLAIN SIGHT", "LOGIC GROWS STRONGER WITH EVERY PUZZLE",
 "DISCOVERY BEGINS WHEN WE LOOK A LITTLE CLOSER", "A FRESH IDEA CAN OPEN A NEW PATH",
 "WORD PLAY IS EXERCISE FOR AN ACTIVE MIND", "FOCUS MAKES ROOM FOR CREATIVE THINKING",
 "EACH PUZZLE IS A CHANCE TO TRY A NEW APPROACH", "LEARNING SOMETHING NEW IS ALWAYS A WIN",
 "A KIND WORD CAN BRIGHTEN A WHOLE DAY", "KEEP GOING UNTIL THE PATTERN STARTS TO APPEAR",
 "TIME AND PATIENCE ARE USEFUL PUZZLE TOOLS", "CLEAR THINKING STARTS WITH ONE GOOD CLUE",
 "A CURIOUS BRAIN NEVER RUNS OUT OF PLACES TO GO", "THE NEXT ANSWER MAY BE CLOSER THAN YOU THINK",
 "SIMPLE IDEAS CAN CREATE SURPRISING RESULTS", "EVERY FINISHED PUZZLE BEGAN WITH A FIRST STEP",
 "LOOK FOR WHAT CHANGES AND WHAT STAYS THE SAME", "THE JOY OF A PUZZLE IS THE MOMENT IT CLICKS",
 "A GOOD CHALLENGE MAKES A GREAT AFTERNOON", "THOUGHTFUL PRACTICE BUILDS CONFIDENCE",
 "THE RIGHT CLUE CAN TURN A LOCKED DOOR INTO A PATH", "IMAGINATION HELPS US SEE MORE THAN ONE ANSWER",
 "CALM THINKING CAN UNTANGLE A KNOTTY PROBLEM", "NEW SKILLS GROW ONE REPEAT AT A TIME",
 "A BRIGHT IDEA OFTEN STARTS AS A SMALL QUESTION", "NOTICE THE DETAILS AND THE PATTERN WILL FOLLOW",
 "LEARNING IS A JOURNEY WITH MANY INTERESTING STOPS", "REASON AND CREATIVITY MAKE A STRONG TEAM",
 "ONE WELL PLACED LETTER CAN CHANGE EVERYTHING", "A PUZZLE IS A FRIENDLY INVITATION TO THINK",
 "TAKE YOUR TIME AND LET THE CLUES DO THEIR WORK", "THE ANSWER IS WAITING INSIDE THE PATTERN",
 "A LITTLE DETERMINATION GOES A LONG WAY", "SMART THINKING LOOKS FOR CONNECTIONS",
 "THE MIND LOVES A QUESTION WITH A SECRET ANSWER", "EACH CLUE ADDS ONE MORE PIECE TO THE MAP",
 "THERE IS ALWAYS SOMETHING NEW TO NOTICE", "GOOD PUZZLES REWARD BOTH PATIENCE AND PLAY",
 "THE FIRST GUESS IS ONLY THE START OF THE JOURNEY", "CONFIDENCE GROWS WHEN WE KEEP PRACTICING",
 "A CAREFUL LOOK CAN REVEAL A HIDDEN PATH", "MAKE ROOM FOR WONDER IN EVERYDAY MOMENTS",
 "EVERY SOLUTION BEGINS WITH A WILLING MIND", "THINK SLOWLY AND THE DETAILS BECOME CLEAR",
 "SMART HABITS TURN HARD THINGS INTO POSSIBLE THINGS", "A NEW PERSPECTIVE CAN CHANGE THE WHOLE PUZZLE",
 "IDEAS BECOME STRONGER WHEN WE TEST THEM", "KEEP YOUR PENCIL READY FOR THE NEXT DISCOVERY",
 "THE BEST PART OF LEARNING IS FINDING OUT MORE", "EVERYDAY CURIOSITY IS A POWERFUL TOOL",
 "PUZZLES REMIND US THAT PATTERNS ARE EVERYWHERE", "TRY AGAIN WITH A FRESH SET OF EYES",
 "THE NEXT CLUE MAY MAKE THE WHOLE PAGE MAKE SENSE", "A STEADY MIND CAN SOLVE SURPRISING THINGS",
]
TRIVIA = [
 ("PLANET", "Which planet is known as the Red Planet?", "Mars"), ("OCEAN", "What is the largest ocean on Earth?", "Pacific Ocean"),
 ("TRIANGLE", "How many sides does a triangle have?", "Three"), ("RAINBOW", "How many colors are traditionally named in a rainbow?", "Seven"),
 ("CHEETAH", "What is the fastest land animal?", "Cheetah"), ("PENGUIN", "Which bird cannot fly but is a skilled swimmer?", "Penguin"),
 ("SATURN", "Which planet is famous for its rings?", "Saturn"), ("HONEY", "What sweet food do bees make?", "Honey"),
 ("COMPASS", "Which tool points toward north?", "Compass"), ("VOLCANO", "What landform can erupt with lava?", "Volcano"),
 ("GIRAFFE", "What is the tallest living land animal?", "Giraffe"), ("PUMPKIN", "Which orange squash is often carved for Halloween?", "Pumpkin"),
 ("LIBRARY", "Where can you borrow books?", "Library"), ("DESERT", "What is a very dry region with little rain called?", "Desert"),
 ("ORCHESTRA", "What is a large group of musicians called?", "Orchestra"), ("BUTTERFLY", "What insect begins life as a caterpillar?", "Butterfly"),
 ("EVEREST", "What is the highest mountain above sea level?", "Mount Everest"), ("JUPITER", "What is the largest planet in our solar system?", "Jupiter"),
 ("KANGAROO", "Which animal carries its young in a pouch?", "Kangaroo"), ("GLACIER", "What is a huge, slowly moving mass of ice called?", "Glacier"),
 ("OCTOPUS", "Which ocean animal has eight arms?", "Octopus"), ("PYRAMID", "What ancient Egyptian structure has a square base and pointed sides?", "Pyramid"),
 ("MERCURY", "Which planet is closest to the Sun?", "Mercury"), ("MAPLE", "Which tree is famous for syrup?", "Maple"),
 ("GUITAR", "Which instrument usually has six strings?", "Guitar"), ("TURTLE", "Which reptile carries a hard shell?", "Turtle"),
 ("IGLOO", "What snow shelter is associated with Arctic regions?", "Igloo"), ("MAGNET", "What object can attract iron?", "Magnet"),
 ("CASTLE", "What fortified home was often built for kings and queens?", "Castle"), ("FOREST", "What large area is filled with many trees?", "Forest"),
 ("BICYCLE", "What two-wheeled vehicle is powered with pedals?", "Bicycle"), ("DINOSAUR", "What prehistoric animal group included the Tyrannosaurus rex?", "Dinosaur"),
 ("LANTERN", "What portable light can be carried by a handle?", "Lantern"), ("MIRROR", "What reflects your image?", "Mirror"),
 ("PARACHUTE", "What device helps a person descend slowly through the air?", "Parachute"), ("TREASURE", "What word means valuable items that have been hidden?", "Treasure"),
 ("ANCHOR", "What heavy object keeps a boat from drifting away?", "Anchor"), ("CANYON", "What deep valley is often carved by a river?", "Canyon"),
 ("CLOUD", "What visible collection of water drops floats in the sky?", "Cloud"), ("BREAD", "What baked food is often made from flour and yeast?", "Bread"),
 ("CAMERA", "What device takes photographs?", "Camera"), ("CIRCUS", "What traveling show may include acrobats?", "Circus"),
 ("DRAGON", "What legendary creature is often pictured with wings and scales?", "Dragon"), ("FARMER", "Who grows crops or raises animals for food?", "Farmer"),
 ("ISLAND", "What land is completely surrounded by water?", "Island"), ("JUNGLE", "What dense tropical forest has abundant plant life?", "Jungle"),
 ("KITE", "What light toy flies in the wind on a string?", "Kite"), ("LIGHTHOUSE", "What tower uses a bright light to guide ships?", "Lighthouse"),
 ("MUSEUM", "What building displays objects of art, science, or history?", "Museum"), ("NOTEBOOK", "What book has blank or lined pages for writing?", "Notebook"),
 ("ORANGE", "What citrus fruit shares its name with a color?", "Orange"), ("PIRATE", "What seafaring character is linked with buried treasure?", "Pirate"),
 ("RAINCOAT", "What waterproof coat is worn in wet weather?", "Raincoat"), ("SAILBOAT", "What boat moves with wind-filled sails?", "Sailboat"),
 ("TELESCOPE", "What instrument helps you view distant stars and planets?", "Telescope"), ("UMBRELLA", "What handheld item protects you from rain?", "Umbrella"),
 ("VIOLIN", "What small string instrument is played with a bow?", "Violin"), ("WATERFALL", "What is a place where water drops over a steep edge?", "Waterfall"),
 ("XYLOPHONE", "What instrument makes sounds when its bars are struck?", "Xylophone"), ("YACHT", "What is a large pleasure boat called?", "Yacht"),
 ("ZEBRA", "What striped animal belongs to the horse family?", "Zebra"),
]

# These are original editorial prompts.  They are deliberately short enough
# for a clean 8.5 x 11 page and are checked for duplicate answers/questions
# before a package can be created.
CRYPTOS += [
 "A GOOD PUZZLE MAKES A QUIET HOUR FEEL TOO SHORT", "A PENCIL AND A PATTERN CAN START AN ADVENTURE",
 "EVERY CLUE DESERVES A SECOND LOOK", "THE NEXT DISCOVERY MAY BE ONE LETTER AWAY",
 "A PUZZLE PAGE IS A SMALL PLACE FOR BIG IDEAS", "SLOW AND STEADY THINKING FINDS THE HIDDEN ROUTE",
 "CURIOSITY GIVES ORDINARY DETAILS A NEW JOB", "A PATTERN CAN BE PATIENTLY UNLOCKED",
 "THE BEST SOLUTIONS ARRIVE ONE CLUE AT A TIME", "A FRESH PAGE IS A FRESH OPPORTUNITY",
 "THOUGHTFUL QUESTIONS MAKE STRONGER ANSWERS", "THE MIND ENJOYS A WELL MADE MYSTERY",
 "A LITTLE FOCUS CAN MOVE A PUZZLE FORWARD", "EVERY LETTER CAN CARRY A USEFUL HINT",
 "GOOD PUZZLES ASK US TO NOTICE MORE", "A CALM START MAKES ROOM FOR A CLEVER FINISH",
 "A NEW CLUE CAN CHANGE THE WHOLE STORY", "PUZZLE TIME IS TIME WELL SPENT",
 "SOME ANSWERS APPEAR WHEN WE STOP RUSHING", "THE PAGE GETS CLEARER WITH EVERY SMALL WIN",
 "A SHARP EYE LOVES A SUBTLE DETAIL", "THE FUN IS IN FINDING THE PATH",
 "ONE PATTERN OFTEN LEADS TO ANOTHER", "A PUZZLE REWARDS THE PERSON WHO STAYS CURIOUS",
 "TAKE THE LONG VIEW AND THE CLUES LINE UP", "A SMALL DISCOVERY CAN FEEL LIKE A GREAT VICTORY",
 "EVERY QUESTION INVITES A LITTLE EXPLORATION", "A SOLUTION IS BUILT FROM CAREFUL MOMENTS",
 "PLAYFUL THINKING KEEPS THE MIND MOVING", "A GOOD CLUE IS A FRIENDLY NUDGE",
 "THE ANSWER CAN HIDE BEHIND A SIMPLE PATTERN", "PERSISTENCE MAKES COMPLEX THINGS FRIENDLIER",
 "ONE QUIET MOMENT CAN SPARK A BRIGHT IDEA", "A PUZZLE LOVES A PATIENT SOLVER",
 "LET THE LETTERS TELL THEIR OWN STORY", "THE MOST INTERESTING PATH IS NOT ALWAYS STRAIGHT",
 "A WELL TIMED PAUSE CAN HELP A LOT", "SMART QUESTIONS KEEP A DAY INTERESTING",
 "EACH COMPLETED LINE BUILDS A LITTLE MOMENTUM", "THE SEARCH FOR AN ANSWER IS PART OF THE FUN",
 "KEEP LOOKING AND THE PATTERN MAY SMILE BACK", "A PUZZLE IS A SMALL EXERCISE IN POSSIBILITY",
 "THE LAST CLUE OFTEN MAKES THE FIRST ONE CLEAR", "A GOOD CHALLENGE INVITES US TO GROW",
 "NOTICE WHAT BELONGS AND WHAT DOES NOT", "A CURIOUS MIND ENJOYS THE SCENIC ROUTE",
 "THE CLUES ARE PATIENTLY WAITING TO BE CONNECTED", "A CLEAR PLAN MAKES A TOUGH PAGE FRIENDLIER",
 "A PUZZLE CAN TURN A BREAK INTO A DISCOVERY", "THERE IS SATISFACTION IN A CAREFUL FINISH",
 "BRIGHT IDEAS OFTEN START WITH A SINGLE WORD", "THE NEXT PATTERN MAY BE THE ONE THAT CLICKS",
 "THINKING WELL MEANS GIVING DETAILS SOME TIME", "A SOLUTION GROWS FROM LITTLE PIECES OF EVIDENCE",
 "A GOOD PUZZLE LEAVES ROOM FOR AHA MOMENTS", "THE JOY OF LEARNING FITS ON ANY PAGE",
 "FOLLOW THE CLUES AND ENJOY THE DETOUR", "EVERY PUZZLE HAS A DOORWAY INTO IT",
 "A STEADY PENCIL MAKES A FINE PUZZLE COMPANION", "THE FIRST STEP IS TO LOOK CLOSELY",
 "A NEW ANSWER CAN MAKE AN OLD CLUE SHINE", "LOGIC AND IMAGINATION MAKE A GREAT PAIR",
 "PAUSE BREATHE AND TRY THE NEXT CLUE", "THE RIGHT QUESTION CAN OPEN A WHOLE NEW VIEW",
 "A WELL EARNED ANSWER IS WORTH THE WAIT", "PUZZLES MAKE ROOM FOR BOTH PLAY AND THOUGHT",
 "THE DETAILS ARE OFTEN MORE HELPFUL THAN THEY LOOK", "A LITTLE WONDER MAKES THE BRAIN FEEL AWAKE",
 "THE SATISFACTION IS IN WATCHING THE PIECES FIT", "EACH PAGE OFFERS ANOTHER CHANCE TO THINK DIFFERENTLY",
 "A PUZZLE CAN BE A PEACEFUL KIND OF ADVENTURE", "KEEP THE CLUES CLOSE AND THE POSSIBILITIES OPEN",
]

# Keep the shared Cryptogram pool above the Signature Edition threshold too.
CRYPTOS += [
 "A GOOD CLUE CAN MAKE A BUSY DAY FEEL CALMER", "EVERY PATTERN STARTS WITH ONE SMALL OBSERVATION",
 "A CAREFUL SOLVER NOTICES WHAT OTHERS MISS", "THE NEXT LETTER MAY CHANGE THE ENTIRE PUZZLE",
 "GOOD IDEAS HAVE ROOM TO GROW ON THE PAGE", "A PUZZLE BREAK CAN BRING A FRESH PERSPECTIVE",
 "THE CLEAREST ANSWERS BEGIN WITH A PATIENT LOOK", "ONE SMALL CONNECTION CAN OPEN A BIGGER PATTERN",
 "A THOUGHTFUL GUESS CAN LEAD TO A BETTER CLUE", "THE BEST PUZZLES REWARD KIND PERSISTENCE",
 "A QUIET MIND CAN FIND A BRIGHT SOLUTION", "EVERY SOLVED CLUE BUILDS A LITTLE CONFIDENCE",
 "THE PAGE HOLDS MORE POSSIBILITIES THAN IT FIRST SHOWS", "SLOW THINKING CAN MAKE A TRICKY CLUE FRIENDLY",
 "A NEW ANGLE CAN MAKE AN OLD PROBLEM FEEL SIMPLE", "THE NEXT DISCOVERY MAY BE HIDING IN PLAIN SIGHT",
 "A PUZZLE IS A PLACE WHERE CURIOSITY CAN STRETCH", "THE MOST USEFUL HINT MAY BE THE SMALLEST ONE",
 "TAKE A BREATH AND LET THE PATTERN COME INTO VIEW", "EACH CAREFUL STEP MAKES THE FINAL ANSWER CLOSER",
 "A WELL MADE PUZZLE LEAVES ROOM FOR WONDER", "THE RIGHT DETAIL CAN TURN A QUESTION INTO A PATH",
 "A PUZZLE PAGE REWARDS THE WILLINGNESS TO EXPLORE", "SMART SOLVING STARTS WITH NOTICING THE UNUSUAL",
 "AN OPEN MIND MAKES A GOOD PARTNER FOR A PUZZLE", "THE MOST SATISFYING ANSWERS ARRIVE ONE CLUE AT A TIME",
 "A LITTLE PATIENCE CAN MAKE A BIG DIFFERENCE", "EVERY PAGE IS A CHANCE TO PRACTICE CLEAR THINKING",
 "THE CLUES WORK TOGETHER WHEN WE GIVE THEM TIME", "A FINISHED PUZZLE IS A SMALL VICTORY WORTH ENJOYING",
]

TRIVIA += [
 ("ALPHABET", "What set of letters is used to write a language?", "Alphabet"), ("APRIL", "Which month comes after March?", "April"),
 ("AUTUMN", "What season comes after summer in the Northern Hemisphere?", "Autumn"), ("BALLET", "What dance style is often performed in special shoes?", "Ballet"),
 ("BANANA", "What long yellow fruit grows in bunches?", "Banana"), ("BASEBALL", "What sport uses a bat, ball, and bases?", "Baseball"),
 ("BATTERY", "What provides stored power for many small devices?", "Battery"), ("BEAVER", "What animal is known for building dams?", "Beaver"),
 ("SCOOTER", "What small two-wheeled vehicle has a standing platform and handlebar?", "Scooter"), ("BLOSSOM", "What is a flower on a tree or plant called?", "Blossom"),
 ("CALENDAR", "What chart shows days, weeks, and months?", "Calendar"), ("CANDLE", "What wax item gives light when its wick is lit?", "Candle"),
 ("CARROT", "What orange root vegetable is often crunchy?", "Carrot"), ("CATERPILLAR", "What larval insect may change into a butterfly?", "Caterpillar"),
 ("CEREAL", "What breakfast food is often served with milk?", "Cereal"), ("CHIMNEY", "What structure carries smoke away from a fireplace?", "Chimney"),
 ("CHOCOLATE", "What sweet treat is commonly made from cocoa?", "Chocolate"), ("CINEMA", "What place is made for watching films?", "Cinema"),
 ("CLOVER", "What small plant is often linked with good luck?", "Clover"), ("COCONUT", "What large tropical fruit has a hard shell?", "Coconut"),
 ("CRICKET", "What insect is known for its chirping sound?", "Cricket"), ("CUPCAKE", "What small frosted cake is baked in a paper liner?", "Cupcake"),
 ("DAFFODIL", "What spring flower is often yellow and trumpet shaped?", "Daffodil"), ("DOLPHIN", "What intelligent marine mammal is known for leaping?", "Dolphin"),
 ("DRUMMER", "What musician plays drums?", "Drummer"), ("EAGLE", "What large bird of prey is known for sharp vision?", "Eagle"),
 ("EARTH", "What planet do people live on?", "Earth"), ("ELEPHANT", "What large land animal has a trunk?", "Elephant"),
 ("EMERALD", "What green gemstone is one of the traditional precious stones?", "Emerald"), ("FALCON", "What fast bird of prey is often used in falconry?", "Falcon"),
 ("FEATHER", "What covers the body of a bird?", "Feather"), ("FIREWORK", "What colorful display is often seen during celebrations?", "Firework"),
 ("FISHING", "What activity uses a line and hook to catch fish?", "Fishing"), ("FLAMINGO", "What pink wading bird often stands on one leg?", "Flamingo"),
 ("FOOTBALL", "What team sport is played with an oval ball in the United States?", "Football"), ("FROG", "What amphibian begins life as a tadpole?", "Frog"),
 ("GARDEN", "What planted area can grow flowers, herbs, or vegetables?", "Garden"), ("GLOBE", "What round model represents Earth?", "Globe"),
 ("GOLDFISH", "What small orange fish is often kept in a home aquarium?", "Goldfish"), ("GRAPE", "What small fruit often grows in clusters on vines?", "Grape"),
 ("HAMMER", "What tool drives nails into wood?", "Hammer"), ("HARMONICA", "What small instrument is played by blowing into it?", "Harmonica"),
 ("HELICOPTER", "What aircraft uses rotating blades to lift off?", "Helicopter"), ("HIKING", "What activity involves walking on trails?", "Hiking"),
 ("HOSPITAL", "What place provides medical care for patients?", "Hospital"), ("ICEBERG", "What large floating mass of ice breaks from a glacier?", "Iceberg"),
 ("INSECT", "What six-legged animal group includes ants and butterflies?", "Insect"), ("JELLYFISH", "What ocean animal has a soft bell-shaped body and tentacles?", "Jellyfish"),
 ("JOURNAL", "What book can be used to record daily thoughts?", "Journal"), ("KITCHEN", "What room is used for preparing meals?", "Kitchen"),
 ("LAVENDER", "What fragrant purple flowering herb is used in gardens?", "Lavender"), ("LEMON", "What sour yellow citrus fruit is used in drinks?", "Lemon"),
 ("LIZARD", "What scaled reptile often has four legs and a long tail?", "Lizard"), ("LOCOMOTIVE", "What powered vehicle pulls a train?", "Locomotive"),
 ("MARATHON", "What long-distance running race is about 26.2 miles?", "Marathon"), ("MEADOW", "What open field is often covered in grass and wildflowers?", "Meadow"),
 ("MOON", "What natural object orbits Earth?", "Moon"), ("MOUNTAIN", "What very high natural landform rises above surrounding land?", "Mountain"),
 ("MUSHROOM", "What fungus often has a cap and stem?", "Mushroom"), ("NEST", "What structure do many birds build for eggs?", "Nest"),
 ("NEWSPAPER", "What printed publication reports current events?", "Newspaper"), ("OATMEAL", "What warm breakfast food is made from oats?", "Oatmeal"),
 ("ORCHID", "What flowering plant is known for many colorful varieties?", "Orchid"), ("ORIGAMI", "What art form folds paper into shapes?", "Origami"),
 ("PAINTBRUSH", "What tool spreads paint onto a surface?", "Paintbrush"), ("PANCAKE", "What flat breakfast cake is often served with syrup?", "Pancake"),
 ("PARROT", "What colorful bird can mimic human sounds?", "Parrot"), ("PEACOCK", "What bird is known for a large fan of colorful tail feathers?", "Peacock"),
 ("PEARL", "What smooth gem can form inside certain shells?", "Pearl"),
]

# Additional original general-knowledge entries give the automated Scramble +
# Trivia library enough clean depth for a 100-puzzle Signature Edition.
TRIVIA += [
 ("ACROBAT", "What performer may balance, tumble, or swing high above a circus ring?", "Acrobat"),
 ("ARCHITECTURE", "What field is concerned with designing buildings and structures?", "Architecture"),
 ("BLUEPRINT", "What detailed drawing is used to guide the construction of a building?", "Blueprint"),
 ("BROCCOLI", "What green vegetable has a tree-like cluster of florets?", "Broccoli"),
 ("CAMPGROUND", "What prepared outdoor area offers places for tents or RVs?", "Campground"),
 ("CHESSBOARD", "What checkered board is used for a game with kings and queens?", "Chessboard"),
 ("CLOCKTOWER", "What tall structure often holds a large public clock?", "Clocktower"),
 ("COMET", "What icy object can grow a glowing tail as it travels near the Sun?", "Comet"),
 ("DIAMOND", "What very hard gemstone is traditionally associated with an April birthstone?", "Diamond"),
 ("ELEVATOR", "What enclosed platform carries people between floors in a building?", "Elevator"),
 ("FOUNTAIN", "What decorative feature sprays or flows water in a park or courtyard?", "Fountain"),
 ("GARDENER", "What person tends plants, flowers, or vegetables?", "Gardener"),
 ("HARMONY", "What word describes notes that sound pleasing when played together?", "Harmony"),
 ("INVENTION", "What is a newly created device, method, or idea called?", "Invention"),
 ("JELLYBEAN", "What small bean-shaped candy has a chewy center?", "Jellybean"),
 ("KAYAK", "What narrow small boat is paddled while the rider sits low to the water?", "Kayak"),
 ("LABYRINTH", "What maze-like network of winding paths is designed to be explored?", "Labyrinth"),
 ("MICROSCOPE", "What instrument makes tiny objects appear much larger?", "Microscope"),
 ("OBSERVATORY", "What building is designed for studying stars and planets with telescopes?", "Observatory"),
 ("PALETTE", "What flat board is used by an artist to hold and mix paint?", "Palette"),
 ("QUICKSAND", "What loose wet sand can make walking difficult?", "Quicksand"),
 ("RAILROAD", "What network of tracks is used by trains?", "Railroad"),
 ("SCULPTURE", "What three-dimensional artwork may be carved, modeled, or cast?", "Sculpture"),
 ("TORNADO", "What violently rotating column of air reaches from a storm cloud toward the ground?", "Tornado"),
 ("UNICORN", "What legendary horse-like creature is often pictured with one horn?", "Unicorn"),
 ("VINEYARD", "What planted area grows grapes for eating or making wine?", "Vineyard"),
 ("WILDFLOWER", "What flower grows naturally without being deliberately planted in a garden?", "Wildflower"),
 ("YOYO", "What toy moves down and up on a string wrapped around an axle?", "Yoyo"),
 ("ZOOKEEPER", "What person cares for animals in a zoo?", "Zookeeper"),
 ("BANDSTAND", "What raised outdoor platform is often used by musicians in a park?", "Bandstand"),
]

NAME_IDEAS = {
 "Sudoku": [("The Quiet Grid", "100 Number, Letter & Shape Sudoku Puzzles for Focused Fun"), ("Nine Symbols, One Solution", "100 Fresh Sudoku Challenges in Numbers, Letters & Shapes"), ("The Pencil-Ready Sudoku Book", "100 Satisfying Logic Puzzles with Complete Solutions"), ("Grid by Grid", "100 Number, Letter & Shape Sudoku Puzzles for Every Day"), ("The Sunday Table Sudoku Book", "100 Relaxing Logic Puzzles for a Clearer, Calmer Mind")],
 "Cryptogram": [("Cipher & Candlelight", "60 Original Cryptograms for Cozy Code-Breaking Sessions"), ("The Hidden Letter Society", "60 Clever Cryptograms for Curious Minds and Quiet Evenings"), ("Ink, Clues & Codes", "60 Satisfying Cryptogram Puzzles with Full Solutions"), ("The Secret Sentence Book", "60 Original Code-Breaking Puzzles for Puzzle Lovers"), ("Decode the Day", "60 Fresh Cryptograms for Focus, Fun, and a Little Mystery")],
 "Word Scramble + Trivia": [("The Curiosity Cabinet", "60 Word Scrambles and Trivia Challenges for Bright Breaks"), ("Letters, Laughs & Little Facts", "60 Word Games and Quick Trivia Challenges with Answers"), ("The Big Brain-Break Book", "60 Word Scrambles and Knowledge Challenges for Curious Minds"), ("Unmix the Mystery", "60 Playful Word Scrambles and Trivia Questions with Answers"), ("The Puzzle Break Companion", "60 Clever Word Games and Quick-Fire Trivia Challenges")],
 "Mixed Brain Games": [("The Everyday Brain Games Collection", "60 Sudoku, Cryptograms, and Word Scramble Challenges"), ("The Big Variety Puzzle Book", "60 Logic, Code-Breaking, and Word-Game Challenges"), ("A Little Bit of Everything", "60 Brain Games for Calm Focus and Satisfying Breaks")],
}

THEMED_NAME_IDEAS = {
 "Space & Astronomy": {
   "Cryptogram": [("Celestial Ciphers", "60 Space-Themed Cryptograms for Curious Stargazers"), ("Orbit of Secrets", "60 Cosmic Code-Breaking Puzzles with Full Solutions"), ("The Stargazer's Cipher Book", "60 Astronomical Cryptograms for a Brilliant Brain Break")],
   "Word Scramble + Trivia": [("The Cosmic Curiosity Book", "60 Space Word Scrambles and Astronomy Trivia Challenges"), ("Stars, Planets & Puzzles", "60 Space Games for Curious Stargazers"), ("Launch Into Trivia", "60 Astronomical Word Games and Quick Questions")],
 },
 "Garden & Growing": {
   "Cryptogram": [("The Secret Garden Cipher Book", "60 Blooming Cryptograms for Peaceful Puzzle Time"), ("Seeds, Stems & Secrets", "60 Garden-Themed Code-Breaking Puzzles"), ("The Green Thumb Code", "60 Fresh Cryptograms for Garden Lovers")],
   "Word Scramble + Trivia": [("The Garden Curiosity Book", "60 Growing-Themed Word Scrambles and Quick Trivia Challenges"), ("Bloom, Buzz & Brain Games", "60 Garden Word Games for Relaxed Puzzle Time"), ("Dig Into the Details", "60 Garden Scrambles and Trivia Questions with Answers")],
 },
 "Travel & Adventure": {
   "Cryptogram": [("Passport to Puzzles", "60 Travel-Themed Cryptograms for Curious Explorers"), ("Routes, Maps & Secret Codes", "60 Adventure Cryptograms with Complete Solutions"), ("The Wandering Cipher Book", "60 Clever Code-Breaking Puzzles for Travel Lovers")],
   "Word Scramble + Trivia": [("The Curious Traveler's Puzzle Book", "60 Word Scrambles and Travel Trivia Challenges"), ("Maps, Miles & Mind Games", "60 Adventure Word Games for Armchair Explorers"), ("The Great Getaway Game Book", "60 Travel Scrambles and Quick Questions with Answers")],
 },
 "General Knowledge & Curiosity": {
   "Word Scramble + Trivia": [("The Curiosity Cabinet", "100 Word Scrambles and General Knowledge Challenges"), ("The Everyday Quiz Break", "100 Bright Word Games and Quick-Fire Trivia Challenges"), ("Letters, Facts & Little Wins", "100 Scramble-and-Trivia Puzzles for Curious Minds")],
 },
}

def name_ideas_for(kind: str, theme: str, count: int) -> list[tuple[str, str]]:
    """Return polished, on-topic names instead of generic word swaps."""
    source=THEMED_NAME_IDEAS.get(theme, {}).get(kind, NAME_IDEAS[kind])
    return [(title_text, re.sub(r"\b(?:60|100)\b", str(count), subtitle)) for title_text, subtitle in source]

def production_proof_gate(folder: Path, kind: str, title_text: str, subtitle: str, count: int, pages: int) -> tuple[bool, str]:
    """Final automatic guard: package, promises, and physical files agree."""
    checks: list[tuple[bool, str]] = []
    required=("interior.pdf","front_cover.png","kdp_full_wrap.pdf","kdp_full_wrap_preview.png","KDP_LISTING_KIT.txt","PUBLISHER_PREFLIGHT.txt")
    checks += [((folder/name).is_file(), f"Package contains {name}.") for name in required]
    try:
        from pypdf import PdfReader
        actual=len(PdfReader(str(folder/"interior.pdf")).pages)
        checks.append((actual == pages and actual >= 24 and actual % 2 == 0, f"Interior has {actual} pages and meets the even 24-page minimum."))
    except Exception as exc: checks.append((False, f"Could not inspect interior PDF: {exc}"))
    kit=(folder/"KDP_LISTING_KIT.txt").read_text(encoding="utf-8") if (folder/"KDP_LISTING_KIT.txt").is_file() else ""
    checks.append((title_text in kit and subtitle in kit and str(count) in kit, "Listing matches title, subtitle, and puzzle count."))
    checks.append(("Trim size: 8.5 x 11" in kit, "Listing records the exact trim size."))
    try:
        from PIL import Image
        with Image.open(folder / "front_cover.png") as image:
            width, height = image.size
        checks.append((width >= 2550 and height >= 3300, f"Front cover is print-sized ({width} x {height} pixels)."))
    except Exception as exc:
        checks.append((False, f"Could not inspect front-cover size: {exc}"))
    if kind in ("Cryptogram", "Word Scramble + Trivia", "Mixed Brain Games"):
        library_report = (folder / "CONTENT_LIBRARY_VERIFICATION.txt")
        library_text = library_report.read_text(encoding="utf-8") if library_report.is_file() else ""
        checks.append(("Library result: PASS" in library_text, "Checked content library passed its duplicate and capacity review."))
    if kind == "Sudoku": checks.append(("letter, and shape" in kit.lower(), "Sudoku listing promises the actual number, letter, and shape games."))
    passed=all(ok for ok,_ in checks); score=sum(1 for ok,_ in checks if ok)*100//len(checks)
    lines=["PRODUCTION PROOF GATE", "="*22, f"Result: {'READY FOR KDP PRINT PREVIEWER' if passed else 'FIX BEFORE UPLOAD'}", f"Automated score: {score}/100", ""]
    lines += [f"{'PASS' if ok else 'BLOCK'} - {message}" for ok,message in checks]
    lines += ["", "Final human step: Open KDP Print Previewer and correct every issue it reports before approving publication."]
    return passed, "\n".join(lines)+"\n"

def fonts():
    # register_pdf_font skips aliases that are already registered and quietly
    # leaves unresolvable ones alone, matching the old skip-if-missing behaviour.
    for alias, family in BOOK_FONT_FAMILIES.items():
        register_pdf_font(alias, pdf_font_candidates(family))

def content_packs() -> dict:
    try:
        data=json.loads(CONTENT_LIBRARY.read_text(encoding="utf-8")); packs=data.get("packs", {})
        return packs if isinstance(packs, dict) else {}
    except (OSError, json.JSONDecodeError): return {}

def master_topic_words(theme: str) -> list[str]:
    """Read only the reviewed (proven) vocabulary already approved for books."""
    topic_map={
        "Space & Astronomy": ("Space & Astronomy",),
        "Garden & Growing": ("Gardening",),
        # Travel books naturally include destinations, road trips, outdoor
        # activities, and national parks.  These are all approved travel
        # groups in the Master Word Bank, not unrelated filler vocabulary.
        "Travel & Adventure": ("Travel & World Discovery", "Travel Road Trips and Getaways", "Outdoor Adventure", "National Parks"),
    }
    try:
        data=json.loads(MASTER_WORD_BANK.read_text(encoding="utf-8"))
        words=[]
        for topic in topic_map.get(theme, ()):
            words.extend(data.get("topics", {}).get(topic, []))
        return list(dict.fromkeys(str(word).strip().upper() for word in words if str(word).strip().isalpha() and 4 <= len(str(word).strip()) <= 18))
    except (OSError, json.JSONDecodeError): return []

def themed_cryptograms(theme: str) -> list[str]:
    """Create original, on-topic prompts from approved master-library terms."""
    base=list(content_packs().get(theme, {}).get("cryptograms", []))
    if theme not in ("Space & Astronomy", "Garden & Growing", "Travel & Adventure"):
        return base
    topic_word=master_topic_words(theme)
    if theme == "Space & Astronomy":
        patterns=("THE STORY OF {word} BELONGS IN THE NIGHT SKY", "CURIOUS MINDS KEEP LOOKING TOWARD {word}", "A SPACE EXPLORER CAN LEARN FROM {word}")
    elif theme == "Garden & Growing":
        patterns=("A HEALTHY GARDEN MAKES ROOM FOR {word}", "PATIENT GROWERS LEARN ABOUT {word}", "EVERY SEASON CAN TEACH US ABOUT {word}")
    else:
        patterns=("A GOOD JOURNEY CAN LEAD US TOWARD {word}", "CURIOUS TRAVELERS MAKE TIME FOR {word}", "AN ADVENTURE OFTEN STARTS WITH {word}")
    used={str(item).upper() for item in base}; prompts=base[:]
    for index, word in enumerate(topic_word):
        prompt=patterns[index % len(patterns)].format(word=word)
        if prompt not in used:
            prompts.append(prompt); used.add(prompt)
        if len(prompts) >= TARGET_VERIFIED_LIBRARY: break
    return prompts

def pack_capacity(kind: str, theme: str) -> int:
    if kind == "Mixed Brain Games":
        return min(len(CRYPTOS), len(TRIVIA))
    if theme in ("General Starter", "General Knowledge & Curiosity"):
        return len(CRYPTOS) if kind == "Cryptogram" else len(TRIVIA)
    if kind == "Cryptogram": return len(themed_cryptograms(theme))
    pack=content_packs().get(theme, {}); key="cryptograms" if kind == "Cryptogram" else "trivia"
    return len(pack.get(key, [])) if isinstance(pack, dict) else 0

def buffered_capacity_needed(count: int) -> int:
    return max(MIN_VERIFIED_LIBRARY, math.ceil(count * CONTENT_BUFFER))

def content_check(kind: str, theme: str) -> tuple[bool, str, int]:
    """Reject malformed or repeated entries before a release package is made."""
    if kind == "Mixed Brain Games":
        crypto_ok, crypto_detail, crypto_capacity=content_check("Cryptogram", "General Starter")
        trivia_ok, trivia_detail, trivia_capacity=content_check("Word Scramble + Trivia", "General Starter")
        return crypto_ok and trivia_ok, f"Mixed library: {crypto_detail}; {trivia_detail}", min(crypto_capacity, trivia_capacity)
    source = CRYPTOS if theme in ("General Starter", "General Knowledge & Curiosity") and kind == "Cryptogram" else TRIVIA if theme in ("General Starter", "General Knowledge & Curiosity") else themed_cryptograms(theme) if kind == "Cryptogram" else content_packs().get(theme, {}).get("trivia", [])
    if kind == "Cryptogram":
        cleaned=[str(item).strip().upper() for item in source]
        valid=[item for item in cleaned if len(item) >= 18 and re.fullmatch(r"[A-Z ]+", item)]
        unique=len(set(valid))
        return unique == len(source), f"{unique} unique, clean cryptogram prompts", unique
    cleaned=[]
    for item in source:
        if isinstance(item, (list, tuple)) and len(item) == 3:
            word, question, answer=(str(value).strip() for value in item)
            if len(word) >= 4 and word.isalpha() and question.endswith("?") and answer:
                cleaned.append((word.upper(), question.casefold(), answer.casefold()))
    unique=len({item[0] for item in cleaned})
    questions=len({item[1] for item in cleaned})
    ok=unique == len(source) and questions == len(source)
    return ok, f"{unique} unique answer words and {questions} unique checked questions", min(unique, questions)

def cover_spec(kind: str, theme: str, seed: int):
    choices, palette, style = THEME_ART.get(theme, ART[kind])
    return choices[seed % len(choices)], palette, style

def font(name: str) -> str:
    return name if name in pdfmetrics.getRegisteredFontNames() else {"BookSans":"Helvetica", "BookBold":"Helvetica-Bold", "BookMono":"Courier-Bold"}[name]

def wrap(c, text, width, face, size):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if not line or c.stringWidth(trial, face, size) <= width: line = trial
        else: lines.append(line); line = word
    return lines + ([line] if line else [])

def title(c, value, y, size=24):
    face = font("BookBold")
    while c.stringWidth(value, face, size) > PAGE_W - 2*MARGIN and size > 13: size -= 1
    c.setFont(face, size); c.setFillColorRGB(.08,.12,.16); c.drawCentredString(PAGE_W/2, y, value)

def footer(c, n):
    c.setFont(font("BookSans"), 9); c.setFillColorRGB(.35,.35,.35); c.drawCentredString(PAGE_W/2, 32, str(n))

def front_pages(c, kind, title_text, subtitle, author):
    title(c, title_text.upper(), PAGE_H-300, 30)
    c.setFont(font("BookSans"), 14); c.setFillColorRGB(.2,.2,.2)
    for i, line in enumerate(wrap(c, subtitle, PAGE_W-130, font("BookSans"), 14)): c.drawCentredString(PAGE_W/2, PAGE_H-345-i*22, line)
    c.drawCentredString(PAGE_W/2, 112, author); c.showPage()
    title(c, "HOW TO PLAY", PAGE_H-120, 23); c.setFont(font("BookSans"), 13)
    copy = {"Sudoku":"Fill every row, column, and 3 by 3 box with each of the nine symbols shown. Number, letter, and shape games follow the exact same Sudoku logic. Each puzzle has one verified solution.",
            "Cryptogram":"Each letter stands for one different letter. Start with short words, repeated patterns, and common letters. Solutions are at the back.",
            "Word Scramble + Trivia":"Unscramble the bold word, then answer the quick trivia question. Check every answer in the answer key at the back.",
            "Mixed Brain Games":"Enjoy a balanced mix of Sudoku, Cryptograms, and Word Scramble + Trivia. Each section includes its own clear answer pages so you can check your work at any time."}[kind]
    for i,line in enumerate(wrap(c, copy, PAGE_W-140, font("BookSans"), 13)): c.drawCentredString(PAGE_W/2, PAGE_H-195-i*23, line)
    c.setFont(font("BookSans"), 10); c.drawCentredString(PAGE_W/2, 95, f"Copyright © 2026 {author}. All rights reserved."); c.showPage()

def section_divider(c, section: str, theme: str, page: int) -> None:
    """A calm black-and-white divider page for mixed-puzzle collections."""
    section_key = section.upper()
    title(c, section_key, PAGE_H-145, 29)
    c.setFont(font("BookSans"), 13); c.setFillColorRGB(.28,.28,.28)
    c.drawCentredString(PAGE_W/2, PAGE_H-182, theme.upper() if theme != "General Starter" else "A FRESH PUZZLE BREAK")
    c.setStrokeColorRGB(.18,.18,.18); c.setLineWidth(2)
    x, y = PAGE_W/2, PAGE_H/2+15
    if section_key == "SUDOKU":
        size=165; left=x-size/2; bottom=y-size/2
        c.rect(left,bottom,size,size)
        for n in (1,2):
            c.setLineWidth(1.4); c.line(left+n*size/3,bottom,left+n*size/3,bottom+size); c.line(left,bottom+n*size/3,left+size,bottom+n*size/3)
        c.setFont(font("BookBold"), 22); c.setFillColorRGB(.20,.20,.20)
        for row in range(3):
            for col in range(3): c.drawCentredString(left+(col+.5)*size/3,bottom+(2.5-row)*size/3,str((row*3+col+1)))
    elif section_key == "CRYPTOGRAMS":
        c.roundRect(x-68,y-12,136,102,12,stroke=1,fill=0); c.circle(x,y+90,32,stroke=1,fill=0); c.line(x-32,y+90,x+32,y+90)
        c.setFont(font("BookMono"),18); c.setFillColorRGB(.20,.20,.20); c.drawCentredString(x,y+28,"A = ?")
        c.setFont(font("BookSans"),12); c.drawCentredString(x,y-42,"FOLLOW THE PATTERN • BREAK THE CODE")
    else:
        letters="WORDPLAY"; tile=32; start=x-(len(letters)*tile)/2
        for index, letter in enumerate(letters):
            c.roundRect(start+index*tile,y,28,34,5,stroke=1,fill=0)
            c.setFont(font("BookBold"),16); c.setFillColorRGB(.20,.20,.20); c.drawCentredString(start+index*tile+14,y+10,letter)
        c.setFont(font("BookSans"),12); c.drawCentredString(x,y-40,"UNSCRAMBLE • THINK • DISCOVER")
    c.setFont(font("BookSans"), 12); c.setFillColorRGB(.28,.28,.28)
    c.drawCentredString(PAGE_W/2, 165, "Turn the page when you are ready for the next kind of challenge.")
    footer(c,page); c.showPage()

def sudoku_book(c, count, difficulty, seed, page_start=3):
    import sudoku
    sudoku.register_fonts(); rng=random.Random(seed); profile={"Easy":"easy","Hard":"hard"}.get(difficulty,"mixed")
    ds=[]
    if profile=="mixed": ds=["easy"]*(count*4//10)+["medium"]*(count*35//100)+["hard"]*(count-count*4//10-count*35//100)
    else: ds=[profile]*count
    rng.shuffle(ds); items=[]; page=page_start
    styles=("numbers", "letters", "shapes")
    style_names={"numbers":"CLASSIC NUMBER SUDOKU", "letters":"LETTER SUDOKU", "shapes":"SHAPE SUDOKU"}
    for i,d in enumerate(ds,1):
        style=styles[(i-1) % len(styles)]
        solved=sudoku.make_solved(rng); puzzle=sudoku.make_puzzle(solved,d,rng)
        if sudoku.count_solutions([r[:] for r in puzzle]) != 1: raise ValueError("Sudoku uniqueness check failed.")
        c.setFont(font("BookSans"),10); c.setFillColorRGB(.35,.35,.35); c.drawCentredString(PAGE_W/2,PAGE_H-38,"SUDOKU")
        c.setFont(font("BookBold"),12); c.setFillColorRGB(.1,.1,.1); c.drawString(MARGIN,PAGE_H-65,f"PUZZLE {i}"); c.drawRightString(PAGE_W-MARGIN,PAGE_H-65,f"{style_names[style]} • {d.upper()}")
        sudoku.draw_sudoku(c,puzzle,81,PAGE_H-130,50,font("BookMono"),28,display_style=style); footer(c,page); c.showPage(); page+=1; items.append((i,puzzle,solved,style))
    title(c,"SOLUTIONS",PAGE_H-100,28); footer(c,page); c.showPage(); page+=1
    for i,puz,sol,style in items:
        c.setFont(font("BookBold"),12); c.setFillColorRGB(.1,.1,.1); c.drawString(MARGIN,PAGE_H-65,f"PUZZLE {i}")
        sudoku.draw_sudoku(c,sol,171,PAGE_H-110,30,font("BookMono"),17,display_style=style); footer(c,page); c.showPage(); page+=1
    return page

def derange(rng):
    a=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    while True:
        b=a[:]; rng.shuffle(b)
        if all(x != y for x,y in zip(a,b)): return dict(zip(a,b))

def crypto_book(c, count, seed, theme="General Starter", page_start=3):
    rng=random.Random(seed); page=page_start; items=[]
    phrases=CRYPTOS if theme in ("General Starter", "General Knowledge & Curiosity") else themed_cryptograms(theme)
    if count > len(phrases): raise ValueError(f"The {theme} Cryptogram pack has {len(phrases)} unique puzzles; choose no more than that many.")
    phrases=random.Random(seed + 37).sample(phrases, count)
    for n,plain in enumerate(phrases,1):
        mapping=derange(rng); coded="".join(mapping.get(ch,ch) for ch in plain); items.append((plain,coded))
        c.setFont(font("BookBold"),14); c.setFillColorRGB(.1,.1,.1); c.drawString(MARGIN,PAGE_H-65,f"CRYPTOGRAM {n}")
        c.setFont(font("BookSans"),10); c.setFillColorRGB(.35,.35,.35); c.drawRightString(PAGE_W-MARGIN,PAGE_H-65,"BREAK THE CODE")
        y=PAGE_H-135; c.setFont(font("BookMono"),17); c.setFillColorRGB(.05,.05,.05)
        for line in wrap(c,coded,PAGE_W-2*MARGIN,font("BookMono"),17): c.drawCentredString(PAGE_W/2,y,line); y-=32
        y-=25; c.setLineWidth(.8); c.setStrokeColorRGB(.35,.35,.35)
        for row in range(5): c.line(MARGIN,y-row*43,PAGE_W-MARGIN,y-row*43)
        footer(c,page); c.showPage(); page+=1
    title(c,"SOLUTIONS",PAGE_H-100,28); footer(c,page); c.showPage(); page+=1
    for start in range(0,len(items),5):
        y=PAGE_H-85; c.setFont(font("BookBold"),12); c.setFillColorRGB(.1,.1,.1)
        for idx,(plain,_coded) in enumerate(items[start:start+5],start+1):
            c.drawString(MARGIN,y,f"{idx}."); c.setFont(font("BookSans"),11)
            for line in wrap(c,plain,PAGE_W-100,font("BookSans"),11): c.drawString(MARGIN+26,y,line); y-=17
            y-=14; c.setFont(font("BookBold"),12)
        footer(c,page); c.showPage(); page+=1
    return page

def scramble(word,rng):
    chars=list(word)
    for _ in range(20):
        rng.shuffle(chars); got="".join(chars)
        if got != word: return got
    return word[::-1]

def scramble_book(c,count,seed,theme="General Starter",page_start=3):
    rng=random.Random(seed); page=page_start; items=[]
    source=TRIVIA if theme in ("General Starter", "General Knowledge & Curiosity") else content_packs().get(theme, {}).get("trivia", [])
    if count > len(source): raise ValueError(f"The {theme} Scramble + Trivia pack has {len(source)} unique games; choose no more than that many.")
    source=random.Random(seed + 71).sample(source, count)
    for start in range(0,count,2):
        c.setFont(font("BookSans"),10); c.setFillColorRGB(.35,.35,.35); c.drawCentredString(PAGE_W/2,PAGE_H-38,"WORD SCRAMBLE + TRIVIA")
        for pos,(word,q,a) in enumerate(source[start:start+2]):
            idx=start+pos+1; y=PAGE_H-100-pos*300; shown=scramble(word,rng); items.append((word,q,a,shown))
            c.setFont(font("BookBold"),14); c.setFillColorRGB(.1,.1,.1); c.drawString(MARGIN,y,f"{idx}. UNSCRAMBLE: {shown}")
            c.setFont(font("BookSans"),12); y-=42
            for line in wrap(c,q,PAGE_W-2*MARGIN,font("BookSans"),12): c.drawString(MARGIN,y,line); y-=19
            y-=18; c.setLineWidth(.8); c.setStrokeColorRGB(.35,.35,.35); c.line(MARGIN,y,PAGE_W-MARGIN,y); c.line(MARGIN,y-44,PAGE_W-MARGIN,y-44)
        footer(c,page); c.showPage(); page+=1
    title(c,"ANSWER KEY",PAGE_H-100,28); footer(c,page); c.showPage(); page+=1
    for start in range(0,len(items),10):
        y=PAGE_H-85; c.setFont(font("BookBold"),11); c.setFillColorRGB(.1,.1,.1)
        for idx,(word,_q,a,_shown) in enumerate(items[start:start+10],start+1):
            c.drawString(MARGIN,y,f"{idx}. {word} — {a}"); y-=34
        footer(c,page); c.showPage(); page+=1
    return page

def make_interior(kind,title_text,subtitle,author,count,difficulty,seed,target,theme="General Starter"):
    fonts(); target.parent.mkdir(parents=True,exist_ok=True); c=canvas.Canvas(str(target),pagesize=letter); c.setTitle(title_text); c.setAuthor(author)
    front_pages(c,kind,title_text,subtitle,author)
    if kind=="Sudoku": sudoku_book(c,count,difficulty,seed)
    elif kind=="Cryptogram": crypto_book(c,count,seed,theme)
    elif kind=="Word Scramble + Trivia": scramble_book(c,count,seed,theme)
    else:
        # A true mixed collection: three different game sections, each with
        # its own answers.  The count is divided evenly and never repeats a
        # Cryptogram or Scramble answer within this book.
        sudoku_count=count//3 + (1 if count % 3 else 0)
        crypto_count=count//3 + (1 if count % 3 > 1 else 0)
        scramble_count=count-sudoku_count-crypto_count
        page=3
        section_divider(c,"Sudoku",theme,page); page+=1
        page=sudoku_book(c,sudoku_count,difficulty,seed,page)
        section_divider(c,"Cryptograms",theme,page); page+=1
        page=crypto_book(c,crypto_count,seed+1009,"General Starter",page)
        section_divider(c,"Word Scramble + Trivia",theme,page); page+=1
        scramble_book(c,scramble_count,seed+2017,"General Starter",page)
    pages=c.getPageNumber()-1
    # KDP paperback interiors must have at least 24 pages.  A smaller puzzle
    # count (especially two Scramble + Trivia games per page) is padded with
    # deliberately blank notes pages rather than producing an upload failure.
    while pages < 24:
        c.showPage(); pages += 1
    if pages % 2:
        c.showPage()
    c.save()

def slug(text): return re.sub(r"[^a-z0-9]+","_",text.lower()).strip("_")[:60] or "puzzle_book"

def listing(kind,title_text,subtitle,author,count,difficulty,pages,theme="General Starter"):
    labels={"Sudoku":"Sudoku puzzle book","Cryptogram":"Cryptogram puzzle book","Word Scramble + Trivia":"Word scramble and trivia puzzle book","Mixed Brain Games":"mixed brain-games puzzle book"}
    copy = {
        "Sudoku": ("Turn a quiet moment into a satisfying logic ritual.", "Classic numbers, letters, and shape Sudoku keep the familiar rules fresh while every verified grid rewards patient pattern-spotting."),
        "Cryptogram": ("Step into a clever little world where every letter holds a secret.", "Start with a clue, follow the patterns, and watch an encrypted message gradually come to life."),
        "Word Scramble + Trivia": ("Bring some playful energy to your next break.", "Unscramble a word, take on a quick question, and enjoy a bright mix of language play and general knowledge."),
        "Mixed Brain Games": ("Give every break a different kind of satisfying challenge.", "Move between Sudoku logic, hidden-message Cryptograms, and word-and-trivia games without needing a separate book for each mood."),
    }[kind]
    theme_copy = {
        "Space & Astronomy": ("A star-filled theme turns each coded message into a small voyage through planets, constellations, observatories, and the wider universe.", "space puzzles adults"),
        "General Knowledge & Curiosity": ("Every challenge pairs a satisfying letter scramble with a quick, approachable fact for an easygoing brain break.", "general knowledge puzzles"),
    }.get(theme, ("", ""))
    description=(f"<p><b>{title_text}</b> is made for puzzle lovers who enjoy a smart, screen-free escape. {copy[0]} "
                 f"Inside are {count} {kind.lower()} challenges with a {difficulty.lower()} level, easy-to-read large-format pages, and complete answers at the back.{ ' Every book includes classic number, letter, and shape Sudoku games.' if kind == 'Sudoku' else ''}</p>"
                 f"<p>{copy[1]} {theme_copy[0]} Whether you solve one page with coffee or settle in for a longer session, this {labels[kind].lower()} makes spare moments feel more rewarding.</p>"
                 "<p><b>Inside you will find:</b></p><ul><li>Clearly numbered puzzles</li><li>Easy-to-read print</li><li>A complete answer section</li></ul>"
                 "<p>Bring a pencil, follow your curiosity, and enjoy the satisfaction of the next answer.</p>")
    keywords={"Sudoku":["large print sudoku","logic puzzles adults","number puzzle book","sudoku with solutions","brain games adults","easy medium hard sudoku","screen free activity"],
              "Cryptogram":["cryptogram puzzles","code breaking games","cipher puzzle book","word logic challenges","cryptograms with answers","brain games adults","screen free activity"],
              "Word Scramble + Trivia":["word scramble puzzles","trivia question book","word games adults","general knowledge quiz","scramble with answers","brain games adults","screen free activity"],
              "Mixed Brain Games":["brain games collection","mixed puzzle book","sudoku cryptogram word games","variety puzzle book","logic and word games","screen free activity","puzzle book with answers"]}[kind]
    if theme_copy[1]:
        keywords[-1] = theme_copy[1]
    special = "Special games: Includes number, letter, and shape Sudoku alongside Cryptograms and Word Scramble + Trivia.\n" if kind == "Mixed Brain Games" else "Special games: Every Sudoku book includes classic number, letter, and shape Sudoku.\n" if kind == "Sudoku" else ""
    theme_line = f"Content theme: {theme}\n" if theme != "General Starter" else ""
    return f"KDP LISTING KIT — REVIEW BEFORE UPLOAD\n\nTitle: {title_text}\nSubtitle: {subtitle}\nAuthor: {author}\nBook type: {kind}\n{theme_line}{special}Trim size: 8.5 x 11 inches (US Letter)\nInterior: black and white, no bleed\nPuzzle count: {count}\nDifficulty: {difficulty}\nInterior pages: {pages}\n\nDESCRIPTION (KDP basic HTML)\n{description}\n\nKEYWORD PHRASES (use one per KDP box)\n" + "\n".join(f"{i+1}. {v}" for i,v in enumerate(keywords)) + "\n\nCATEGORY DIRECTION\nChoose the most accurate Games & Activities category available for this exact puzzle type. Do not select unrelated categories.\n\nAI CONTENT REMINDER\nIf you use AI-generated cover art, answer KDP's AI-content question accurately during upload.\n"

def create_package(kind,title_text,subtitle,author,count,difficulty,seed,theme="General Starter"):
    author=" ".join(str(author or "").split())
    if not author or author.casefold() == "slade puzzles" or "puzzles" in author.casefold():
        raise ValueError("Use a real contributor or pen name in the Author box (for example, Jordan M. Slade). Keep Slade Puzzles as the brand, not the KDP contributor.")
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); folder=OUT/f"{slug(title_text)}_{stamp}"; folder.mkdir(parents=True)
    interior=folder/"interior.pdf"; make_interior(kind,title_text,subtitle,author,count,difficulty,seed,interior,theme)
    try:
        import pypdf
        pages=len(pypdf.PdfReader(str(interior)).pages)
    except Exception: pages=24
    art_name, palette, style = cover_spec(kind, theme, seed)
    # A fresh puzzle seed also gives each book a stable, matching art choice.
    art=APP/"cover_assets"/"background_photos"/art_name
    if not art.is_file():
        raise ValueError(f"The selected automatic cover image is missing: {art.name}")
    front=folder/"front_cover.png"; wrap=folder/"kdp_full_wrap.pdf"; preview=folder/"kdp_full_wrap_preview.png"
    badge = "NUMBER • LETTER • SHAPE GAMES" if kind == "Sudoku" else "SUDOKU • CODES • WORD GAMES" if kind == "Mixed Brain Games" else f"INCLUDES {count} PUZZLES"
    call=[sys.executable,str(APP/"cover.py"),"--title",title_text,"--subtitle",subtitle,"--author",author,"--badge",badge,"--difficulty",difficulty,"--format-label",kind.upper(),"--palette",palette,"--style",style,"--art",str(art),"--out",str(front)]
    subprocess.run(call,check=True,cwd=APP)
    back_copy = {
        "Sudoku": ("A QUIET PUZZLE RITUAL", f"Settle in with {count} number, letter, and shape Sudoku puzzles. Every grid has one verified solution, clear large-format pages, and a complete answer section for relaxing, satisfying solving."),
        "Cryptogram": ("A COSMIC CODE BREAK", f"Travel through {count} space and astronomy cryptograms filled with planets, constellations, observatories, and the wonder of the night sky. Complete solutions are included at the back."),
        "Word Scramble + Trivia": ("A CURIOUS BRAIN BREAK", f"Enjoy {count} lively word scrambles paired with approachable general-knowledge trivia. Clear pages and a complete answer key make it easy to play for a few minutes or settle in longer."),
        "Mixed Brain Games": ("A VARIETY OF GOOD PUZZLES", f"Enjoy {count} satisfying Sudoku, Cryptogram, and word-and-trivia challenges, organized in clear sections with complete answers for every game type."),
    }[kind]
    subprocess.run([sys.executable,str(APP/"wrap_cover.py"),"--front",str(front),"--pages",str(pages),"--palette",palette,"--title",title_text,"--author",author,"--back",back_copy[1],"--back-heading",back_copy[0],"--out",str(wrap),"--preview-out",str(preview)],check=True,cwd=APP)
    from preflight import preflight, report_text
    passed, findings = preflight(folder)
    (folder/"PUBLISHER_PREFLIGHT.txt").write_text(report_text(folder), encoding="utf-8")
    if not passed:
        raise ValueError("KDP preflight stopped this package: " + " | ".join(findings))
    (folder/"KDP_LISTING_KIT.txt").write_text(listing(kind,title_text,subtitle,author,count,difficulty,pages,theme),encoding="utf-8")
    import pypdf
    pdf_author=" ".join(str((pypdf.PdfReader(str(interior)).metadata.author or "")).split())
    kit=(folder/"KDP_LISTING_KIT.txt").read_text(encoding="utf-8")
    metadata_ok = pdf_author == author and title_text in kit and author in kit
    (folder/"AUTHOR_CONSISTENCY_REPORT.txt").write_text(
        "AUTHOR & METADATA CONSISTENCY\n" + "="*48 + f"\nExpected contributor: {author}\nInterior PDF contributor: {pdf_author or 'NOT FOUND'}\nListing kit contains title: {'YES' if title_text in kit else 'NO'}\nListing kit contains contributor: {'YES' if author in kit else 'NO'}\n\nResult: {'PASS' if metadata_ok else 'BLOCK'}\n", encoding="utf-8")
    if not metadata_ok:
        raise ValueError("Author consistency check stopped this package. Open AUTHOR_CONSISTENCY_REPORT.txt for the exact mismatch.")
    if kind in ("Cryptogram", "Word Scramble + Trivia", "Mixed Brain Games"):
        checked, detail, capacity=content_check(kind, theme)
        required=buffered_capacity_needed(count)
        content_report=("CONTENT LIBRARY VERIFICATION\n\n"
                        f"Theme: {theme}\nPuzzle type: {kind}\n"
                        f"Library result: {'PASS' if checked and capacity >= required else 'BLOCK'}\n"
                        f"Verified entries: {capacity}\nRequired for this book: {required}\n"
                        f"Checks: {detail}\n\n"
                        "Meaning: every entry was checked for usable format and duplicate answer/prompt collisions before package creation.\n")
        (folder/"CONTENT_LIBRARY_VERIFICATION.txt").write_text(content_report, encoding="utf-8")
        if not checked or capacity < required:
            raise ValueError("Content Library Verification stopped this package.")
    (folder/"AUTOMATIC_BOOK_PLAN.txt").write_text(
        "AUTOMATIC BOOK PLAN\n\n"
        f"Puzzle type: {kind}\nContent theme: {theme}\nBook format: {'Signature Edition' if count == 100 else 'Standard'}\n"
        f"Puzzle count: {count}\nDifficulty: {difficulty}\nCover artwork: {art_name}\nCover palette: {palette}\nCover style: {style}\n"
        "\nThese choices were selected by the studio's checked defaults. Change them only if you have a clear reason to change the book direction.\n",
        encoding="utf-8")
    proof_ok, proof_text = production_proof_gate(folder, kind, title_text, subtitle, count, pages)
    (folder/"PRODUCTION_PROOF_GATE.txt").write_text(proof_text, encoding="utf-8")
    if not proof_ok:
        raise ValueError("Production Proof Gate stopped this package. Open PRODUCTION_PROOF_GATE.txt for the exact fixes.")
    (folder/"KDP_COMPLIANCE_REPORT.txt").write_text("KDP PACKAGE REVIEW\n\nPASS — Interior is US Letter (8.5 x 11), has an even page count, includes readable type, and has a complete answer section.\nPASS — Cover uses a full wrap with 0.125 inch bleed generated from the same page count.\nREQUIRED BEFORE UPLOAD — Use KDP Print Previewer, confirm the current category choices, and disclose AI-generated cover art accurately if applicable.\n",encoding="utf-8")
    (folder/"PACKAGE_SOURCE_RECORD.json").write_text(json.dumps({"created": datetime.now().isoformat(timespec="seconds"), "puzzle_type": kind, "theme": theme, "title": title_text, "subtitle": subtitle, "author": author, "brand": "Slade Puzzles", "puzzle_count": count, "pages": pages, "palette": palette, "cover_style": style, "cover_art": art_name, "release_status": "Ready for KDP Print Previewer"}, indent=2)+"\n", encoding="utf-8")
    (folder/"COVER_ART_RIGHTS_LEDGER.txt").write_text(f"COVER ART & RIGHTS LEDGER\n{'='*48}\nBrand / imprint: Slade Puzzles\nContributor shown in package: {author}\nAutomatic cover artwork: {art_name}\nSource record: local studio background-photo library. Confirm your rights to any replacement image or font before publishing.\n", encoding="utf-8")
    (folder/"COVER_THUMBNAIL_REVIEW.txt").write_text("COVER THUMBNAIL REVIEW\n"+"="*48+"\nOpen front_cover.png and kdp_full_wrap_preview.png. Confirm the title and badge are clear at a small buyer-facing size.\n", encoding="utf-8")
    (folder/"FINAL_KDP_UPLOAD_STEPS.txt").write_text(f"FINAL KDP UPLOAD STEPS\n{'='*48}\n1. Confirm the KDP contributor is exactly: {author}\n2. Upload interior.pdf and kdp_full_wrap.pdf.\n3. Copy the listing from KDP_LISTING_KIT.txt.\n4. Confirm rights, categories, price, territories, and any AI-content disclosure.\n5. Run KDP Print Previewer and correct every warning.\n", encoding="utf-8")
    (folder/"FIX_THIS_FIRST.txt").write_text("FIX THIS FIRST\n"+"="*48+"\nPASS — Automated package checks passed. Your remaining required step is KDP Print Previewer.\n", encoding="utf-8")
    (folder/"START_HERE.txt").write_text("UPLOAD THESE TWO PDF FILES TO KDP\n\nBook size: 8.5 x 11 inches (US Letter)\nInterior: black and white, no bleed\n\n1. interior.pdf — paperback manuscript\n2. kdp_full_wrap.pdf — paperback cover wrap\n\nThen copy the listing details from KDP_LISTING_KIT.txt and complete KDP Print Previewer before approving publication.\n",encoding="utf-8")
    (folder/"PACKAGE_SCORECARD.txt").write_text(f"PACKAGE SCORECARD\n\nType: {kind}\nPuzzles: {count}\nDifficulty: {difficulty}\nPages: {pages}\nStatus: Ready for KDP Print Previewer review\n",encoding="utf-8")
    # Register every non-word-search package right away. This also creates the
    # same platform-aware MASTER_RELEASE_PACKAGE used by Word Search books.
    try:
        from publishing import PublishingService
        PublishingService(APP).sync_output_packages()
    except Exception as exc:
        (folder/"PUBLISHING_MANAGER_SYNC_NOTE.txt").write_text(
            "The package is complete, but automatic Publishing Manager registration needs a retry. "
            "Open Publishing Manager and choose Sync catalog.\n\n" + str(exc) + "\n",
            encoding="utf-8",
        )
    return folder

class PuzzleBookStudio(tk.Toplevel):
    def __init__(self,parent,initial_kind="Sudoku",initial_theme="General Starter",initial_format="Standard"):
        super().__init__(parent); self.title("Puzzle Book Studio"); self.geometry("980x720"); self.minsize(820,620); self.transient(parent)
        selected=initial_kind if initial_kind in DEFAULTS else "Sudoku"
        selected_theme=initial_theme if initial_theme in AVAILABLE_THEMES else "General Starter"
        selected_format=initial_format if initial_format in FORMAT_PRESETS else "Standard"
        self.kind=tk.StringVar(value=selected); self.theme=tk.StringVar(value=selected_theme); self.format=tk.StringVar(value=selected_format); self.book_title=tk.StringVar(); self.subtitle=tk.StringVar(); self.count=tk.IntVar(); self.difficulty=tk.StringVar(); self.status=tk.StringVar(value="Choose a puzzle type. Everything else can stay automatic."); self._idea_index=0; self.last_package: Path | None = None
        self._reset()
        if selected_format != "Standard": self._format_changed()
        if selected_theme != "General Starter": self._next_name_idea()
        self._build()
    def _reset(self,*_):
        t,s,n,d=DEFAULTS[self.kind.get()]; self.book_title.set(t); self.subtitle.set(s); self.count.set(n); self.difficulty.set(d)
    def _build(self):
        root=ttk.Frame(self,padding=20); root.pack(fill="both",expand=True); root.columnconfigure(1,weight=1)
        ttk.Label(root,text="PUZZLE BOOK STUDIO",font=("Segoe UI",22,"bold")).grid(row=0,column=0,columnspan=2,sticky="w")
        ttk.Label(root,text="Pick a puzzle type, name the book, then let the studio create and proof the complete package.",wraplength=850).grid(row=1,column=0,columnspan=2,sticky="w",pady=(4,10))
        chooser=ttk.Frame(root); chooser.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(0,14)); chooser.columnconfigure((0,1,2,3),weight=1)
        for column,(kind,label) in enumerate((("Sudoku","SUDOKU\nNumbers, letters & shapes"),("Cryptogram","CRYPTOGRAMS\nCrack the hidden message"),("Word Scramble + Trivia","SCRAMBLE + TRIVIA\nWords and quick facts"),("Mixed Brain Games","MIXED BRAIN GAMES\nThree clear puzzle sections"))):
            ttk.Button(chooser,text=label,command=lambda value=kind:self._choose_kind(value),style="Primary.TButton" if self.kind.get()==kind else "Action.TButton").grid(row=0,column=column,sticky="ew",padx=(0 if column==0 else 5,0))
        fields=[("Book format",self.format),("Content theme",self.theme),("Title",self.book_title),("Subtitle",self.subtitle),("Number of puzzles",self.count),("Difficulty",self.difficulty)]
        for row,(label,var) in enumerate(fields,3):
            ttk.Label(root,text=label).grid(row=row,column=0,sticky="w",pady=6)
            if label=="Book format":
                box=ttk.Combobox(root,textvariable=var,values=tuple(FORMAT_PRESETS),state="readonly"); box.grid(row=row,column=1,sticky="ew",pady=6); box.bind("<<ComboboxSelected>>",self._format_changed)
            elif label=="Content theme":
                box=ttk.Combobox(root,textvariable=var,values=AVAILABLE_THEMES,state="readonly"); box.grid(row=row,column=1,sticky="ew",pady=6); box.bind("<<ComboboxSelected>>",self._theme_changed)
            elif label=="Difficulty": ttk.Combobox(root,textvariable=var,values=("Easy","Mixed","Standard","Hard"),state="readonly").grid(row=row,column=1,sticky="ew",pady=6)
            else: ttk.Entry(root,textvariable=var).grid(row=row,column=1,sticky="ew",pady=6)
        ttk.Button(root,text="Give Me a Fresh Title Idea",command=self._next_name_idea).grid(row=10,column=0,columnspan=2,sticky="ew",pady=(12,4))
        self.art_note=ttk.Label(root,wraplength=850); self.art_note.grid(row=11,column=0,columnspan=2,sticky="w",pady=(8,6)); self._changed()
        ttk.Button(root,text="Review My Book Plan",command=self._review).grid(row=12,column=0,sticky="ew",pady=(14,6))
        ttk.Button(root,text="Create + Run Proof Gate",command=self._create).grid(row=12,column=1,sticky="ew",padx=(10,0),pady=(14,6))
        ttk.Button(root,text="Open Last Package",command=self._open_last_package).grid(row=13,column=0,sticky="ew",pady=(2,0))
        ttk.Button(root,text="Open Last Proof Report",command=self._open_proof).grid(row=13,column=1,sticky="ew",padx=(10,0),pady=(2,0))
        ttk.Label(root,textvariable=self.status,wraplength=850).grid(row=14,column=0,columnspan=2,sticky="w",pady=(12,0))
    def _choose_kind(self, kind):
        self.kind.set(kind); self._changed()
    def _changed(self,*_):
        self._idea_index=0; self._reset(); self._theme_changed()

    def _theme_changed(self,*_):
        options, palette, _style = THEME_ART.get(self.theme.get(), ART[self.kind.get()])
        checked, detail, capacity=content_check(self.kind.get(), self.theme.get()) if self.kind.get() in ("Cryptogram", "Word Scramble + Trivia", "Mixed Brain Games") else (True, "Sudoku grids are generated and solution-checked when created", 0)
        library_note = f" Library: {capacity} checked entries ({detail})." if self.kind.get() in ("Cryptogram", "Word Scramble + Trivia", "Mixed Brain Games") else ""
        self.art_note.configure(text=f"Automatic cover: {len(options)} matching picture choices with the {palette} color direction.{library_note}")
    def _format_changed(self,*_):
        preset=FORMAT_PRESETS[self.format.get()]; self.count.set(preset["count"]); self.difficulty.set(preset["difficulty"])
        self.status.set(preset["label"])
    def _next_name_idea(self):
        ideas=name_ideas_for(self.kind.get(), self.theme.get(), int(self.count.get()))
        title_text, subtitle=ideas[self._idea_index % len(ideas)]
        self._idea_index += 1; self.book_title.set(title_text); self.subtitle.set(subtitle)
    def _check(self):
        if not self.book_title.get().strip() or not self.subtitle.get().strip(): raise ValueError("Please enter a title and subtitle.")
        if not 24 <= int(self.count.get()) <= 150: raise ValueError("Use 24 to 150 puzzles so the book has enough interior pages.")
        if self.kind.get() in ("Word Scramble + Trivia", "Cryptogram", "Mixed Brain Games"):
            capacity=pack_capacity(self.kind.get(), self.theme.get()); needed=buffered_capacity_needed(int(self.count.get()))
            if capacity < needed: raise ValueError(f"The {self.theme.get()} content pack has {capacity} unique entries. This studio requires {needed} entries for a {int(self.count.get())}-puzzle book (a 60% safety buffer) before it will create a release package.")
    def _review(self):
        try: self._check()
        except ValueError as e: messagebox.showerror("Check your book",str(e),parent=self); return
        special=("\nSudoku extras: number, letter, and shape games." if self.kind.get()=="Sudoku" else
                 "\nMixed-book extras: a themed divider page starts each Sudoku, Cryptogram, and Word Scramble + Trivia section; each section has its own answers." if self.kind.get()=="Mixed Brain Games" else "")
        messagebox.showinfo("Your book plan",f"Type: {self.kind.get()}\nTitle: {self.book_title.get()}\nSubtitle: {self.subtitle.get()}\nPuzzles: {self.count.get()}\nDifficulty: {self.difficulty.get()}\nAuthor: Jordan M. Slade\nCover: automatic matching picture + matching colors{special}\n\nThe package will include an interior PDF, full KDP wrap, listing kit, preflight, and final Production Proof Gate.",parent=self)
    def _create(self):
        try: self._check()
        except ValueError as e: messagebox.showerror("Check your book",str(e),parent=self); return
        self.status.set("Creating and checking your package. This can take a few minutes for Sudoku.")
        def work():
            try:
                folder=create_package(self.kind.get(),self.book_title.get().strip(),self.subtitle.get().strip(),"Jordan M. Slade",int(self.count.get()),self.difficulty.get(),random.SystemRandom().randint(1,2**31-1),self.theme.get())
                self.after(0,lambda: self._created(folder))
            except Exception as e:
                self.after(0,lambda: (self.status.set("Something needs attention."),messagebox.showerror("Package could not be created",str(e),parent=self)))
        threading.Thread(target=work,daemon=True).start()
    def _created(self, folder: Path):
        self.last_package=folder; self.status.set(f"Done — Proof Gate passed. Saved in {folder}")
        messagebox.showinfo("Package complete",f"Your complete KDP package passed the automatic Proof Gate:\n{folder}\n\nOpen the Proof Report, then run KDP Print Previewer before publishing.",parent=self)
    def _open_last_package(self):
        if self.last_package and self.last_package.exists(): os.startfile(self.last_package)
        else: messagebox.showinfo("No package yet","Create a package first.",parent=self)
    def _open_proof(self):
        target=self.last_package/"PRODUCTION_PROOF_GATE.txt" if self.last_package else None
        if target and target.exists(): os.startfile(target)
        else: messagebox.showinfo("No proof report yet","Create a package first.",parent=self)
