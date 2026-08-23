"""Create the 20-book National Parks word-search collection.

Each title has 48 twelve-word puzzles, suitable for the app's large-print
format.  Re-run this file only when intentionally refreshing this collection.
"""
from __future__ import annotations

import json
from pathlib import Path


THEMES = Path(__file__).resolve().parent / "themes"

PARKS = [
    ("Great Smoky Mountains", "Forest Trails", "nature", "forest-cabin", ["SMOKYMOUNTAINS", "APPALACHIAN", "CADES COVE", "CLINGMANSDOME", "BLUE RIDGE", "FIREFLIES", "BLACK BEAR", "ELK", "HEMLOCK", "WILDFLOWER", "MOUNTAINLAUREL", "STREAM", "CABIN", "WATERFALL", "FOOTHILLS", "RIDGELINE"]),
    ("Zion", "Canyon Cliffs", "desert-sun", "sunburst", ["ZION", "ANGELS LANDING", "NARROWS", "CANYON", "SANDSTONE", "VIRGIN RIVER", "EMERALD POOLS", "WATCHMAN", "MESA", "CLIFF", "SLOT CANYON", "COTTONWOOD", "DESERT BIGHORN", "RED ROCK", "TRAILHEAD", "SUNRISE"]),
    ("Yellowstone", "Geysers and Wildlife", "nature", "gallery", ["YELLOWSTONE", "OLD FAITHFUL", "GEYSER", "BISON", "WOLF", "GRAND PRISMATIC", "HOT SPRING", "MAMMOTH", "LAVA CREEK", "RANGER", "ELK", "BOILING RIVER", "CALDERA", "MUD POT", "GRIZZLY", "LODGE"]),
    ("Grand Canyon", "Desert Vistas", "autumn-harvest", "ticket", ["GRAND CANYON", "COLORADO RIVER", "SOUTH RIM", "NORTH RIM", "KAIBAB", "CONDOR", "RAPIDS", "CANYON WALL", "DESERT VIEW", "MULE", "SUNSET", "OVERLOOK", "GEOLOGY", "RIM TRAIL", "SAGEBRUSH", "VIEWPOINT"]),
    ("Yosemite", "Granite and Waterfalls", "coastal-blue", "halo", ["YOSEMITE", "HALF DOME", "EL CAPITAN", "YOSEMITE FALLS", "SEQUOIA", "TUOLUMNE", "MERCE RIVER", "GLACIER POINT", "GRANITE", "MEADOW", "MARMOT", "CLIMBER", "VALLEY", "BRIDALVEIL", "DOGWOOD", "TRAIL"]),
    ("Rocky Mountain", "Alpine Peaks", "winter-frost", "stripe", ["ROCKY MOUNTAIN", "LONGS PEAK", "ALPINE", "ELK", "MARMOT", "TUNDRA", "TRAIL RIDGE", "BEAR LAKE", "ASPEN", "PINE", "SNOWFIELD", "MOOSE", "ELEVATION", "SUMMIT", "WILDFLOWER", "GLACIER"]),
    ("Acadia", "Coastal Shores", "ocean-breeze", "gallery", ["ACADIA", "CADILLAC MOUNTAIN", "THUNDER HOLE", "ATLANTIC", "TIDEPOOL", "LOBSTER", "GRANITE", "BIRCH", "FIR", "OCEAN PATH", "BAR HARBOR", "SEAL", "LIGHTHOUSE", "COBBLE BEACH", "ISLAND", "FOG"]),
    ("Grand Teton", "Mountain Lakes", "coastal-blue", "halo", ["GRAND TETON", "JACKSON LAKE", "MOOSE", "SNAKE RIVER", "MORAN", "TETON RANGE", "WILLOW", "OSPREY", "MOUNTAIN GOAT", "GLACIER", "SAGE", "ASPEN", "KAYAK", "OVERLOOK", "RANCH", "WILDFLOWER"]),
    ("Olympic", "Rainforests and Coast", "forest-cabin", "gallery", ["OLYMPIC", "HOH RAINFOREST", "HURRICANE RIDGE", "PACIFIC", "SEA STACK", "MOSS", "FERN", "ELK", "TIDEPOOL", "DRIFTWOOD", "CEDAR", "GLACIER", "RIVER", "COASTLINE", "OTTER", "RAINSHADOW"]),
    ("Glacier", "Lakes and Wildflowers", "winter-frost", "stripe", ["GLACIER", "GOING TO SUN", "LAKE MCDONALD", "GRIZZLY", "MOUNTAIN GOAT", "WILDFLOWER", "CEDAR", "GLACIER LILY", "TRAIL", "OVERLOOK", "WATERTON", "RAPIDS", "EAGLE", "ALPINE", "SNOWMELT", "VALLEY"]),
    ("Joshua Tree", "Desert Night", "desert-sun", "sunburst", ["JOSHUA TREE", "MOJAVE", "COLORADO DESERT", "YUCCA", "BOULDER", "CHOLLA", "COYOTE", "JACKRABBIT", "STARLIGHT", "DARK SKY", "OASIS", "SAND", "ROCKPILE", "DESERT TORTOISE", "SUNSET", "CACTUS"]),
    ("Cuyahoga Valley", "Rivers and Rails", "spring-meadow", "colorblock", ["CUYAHOGA VALLEY", "CUYAHOGA RIVER", "BRANDYWINE", "TOWPATH", "BEAVER", "HERON", "WETLAND", "WATERFALL", "MAPLE", "RAILROAD", "BIKE TRAIL", "MEADOW", "OTTER", "CANAL", "WILDFLOWER", "VALLEY"]),
    ("Indiana Dunes", "Shores and Sand", "beach-vacation", "playful", ["INDIANA DUNES", "LAKE MICHIGAN", "SAND DUNE", "BEACHGRASS", "PIPING PLOVER", "WETLAND", "OAK SAVANNA", "TRAIL", "SHORELINE", "MIGRATING BIRD", "SUNSET", "DRIFTWOOD", "WILDFLOWER", "MARSH", "BEACH", "WAVES"]),
    ("Hot Springs", "Thermal Waters", "espresso-cream", "classic", ["HOT SPRINGS", "BATHHOUSE", "THERMAL WATER", "MINERAL", "STEAM", "SPA", "OUACHITA", "FOUNTAIN", "PROMENADE", "SPRING WATER", "HIKING", "FOREST", "HERITAGE", "TUB", "RANGER", "RELAX"]),
    ("Bryce Canyon", "Hoodoos and Starlight", "spooky-night", "retro", ["BRYCE CANYON", "HOODOO", "AMPHITHEATER", "PONDEROSA", "DARK SKY", "SUNRISE POINT", "THOR HAMMER", "RIM TRAIL", "RED ROCK", "MULE DEER", "PINE", "STARGAZING", "CANYON", "FROST", "OVERLOOK", "TRAIL"]),
    ("Shenandoah", "Blue Ridge Forests", "forest-cabin", "gallery", ["SHENANDOAH", "SKYLINE DRIVE", "BLUE RIDGE", "BLACK BEAR", "WHITE OAK", "WATERFALL", "OVERLOOK", "WILDFLOWER", "DEER", "TRAIL", "MOUNTAIN LAUREL", "RIVER", "FOREST", "FOG", "HIKER", "RIDGE"]),
    ("Mount Rainier", "Volcano and Meadows", "lavender-pop", "halo", ["MOUNT RAINIER", "VOLCANO", "PARADISE", "WILDFLOWER", "GLACIER", "NISQUALLY", "MEADOW", "MARMOT", "SNOW", "SUMMIT", "DOUGLAS FIR", "WATERFALL", "ALPINE", "TRAIL", "CLOUD", "RANGER"]),
    ("Arches", "Stone Arches", "desert-sun", "ticket", ["ARCHES", "DELICATE ARCH", "BALANCED ROCK", "SANDSTONE", "MOAB", "WINDOWS", "FIERY FURNACE", "RED ROCK", "DESERT", "RAVEN", "LIZARD", "CANYON", "SUNSET", "TRAIL", "TURRET", "STARLIGHT"]),
    ("New River Gorge", "Rivers and Rapids", "coastal-blue", "colorblock", ["NEW RIVER GORGE", "WHITEWATER", "RAPIDS", "BRIDGE", "RAIL TRAIL", "PEREGRINE", "SANDSTONE", "RIVERBANK", "KAYAK", "CLIFF", "FOREST", "OVERLOOK", "WATERFALL", "HIKER", "CANYON", "ADVENTURE"]),
    ("Death Valley", "Desert Basins", "sunset", "sunburst", ["DEATH VALLEY", "BADWATER", "SALT FLAT", "MESQUITE", "DUNE", "DESERT", "ZABRISKIE", "WILDFLOWER", "COYOTE", "CANYON", "STARLIGHT", "SUNRISE", "BASIN", "OASIS", "HEAT", "MOUNTAIN"]),
]

FILLER = ["NATIONAL PARK", "TRAIL MAP", "RANGER", "BACKPACK", "CAMPGROUND", "WILDLIFE", "SCENIC", "EXPLORER", "DISCOVER", "NATURE", "OUTDOORS", "ADVENTURE", "CONSERVATION", "WILDERNESS", "VIEWPOINT", "DAYHIKE", "SUNRISE", "SUNSET", "PICNIC", "BINOCULARS"]


def clean(word: str) -> str:
    return "".join(letter for letter in word.upper() if letter.isalpha())


def build_puzzles(park: str, feature: str, words: list[str]) -> list[dict[str, object]]:
    # A park can already contain a useful general word such as RANGER.  Keep the
    # source bank unique before rotating selections so one puzzle never asks the
    # solver to find the same word twice.
    bank: list[str] = []
    for word in words + FILLER:
        cleaned = clean(word)
        if cleaned and cleaned not in bank:
            bank.append(cleaned)
    puzzles: list[dict[str, object]] = []
    for number in range(48):
        start = (number * 5) % len(bank)
        selected: list[str] = []
        for offset in range(len(bank)):
            candidate = bank[(start + offset) % len(bank)]
            if candidate not in selected:
                selected.append(candidate)
            if len(selected) == 12:
                break
        puzzles.append({"name": f"{park} {feature} Puzzle {number + 1:03d}", "words": selected})
    return puzzles


def main() -> None:
    THEMES.mkdir(exist_ok=True)
    for rank, (park, feature, palette, style, words) in enumerate(PARKS, start=1):
        data = {
            "title": f"National Parks #{rank:02d}: {park} Word Search",
            "subtitle": f"48 {feature.lower()} word search puzzles for adults and teens",
            "author": "Slade Puzzles",
            "series": "National Parks: Top 20 Collection",
            "series_rank": rank,
            "park_feature": feature,
            "palette": palette,
            "cover_style": style,
            "puzzles": build_puzzles(park, feature, words),
        }
        filename = f"national_parks_{rank:02d}_" + clean(park).lower() + ".json"
        (THEMES / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Created {filename}")


if __name__ == "__main__":
    main()
