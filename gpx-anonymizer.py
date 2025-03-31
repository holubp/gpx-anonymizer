#!/usr/bin/env python3
import argparse
import math
import logging
import xml.etree.ElementTree as ET

def haversine(lat1, lon1, lat2, lon2):
    """
    Compute the great-circle distance (in meters) between two points.
    """
    R = 6371000  # Earth radius in meters.
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def point_in_rect(lat, lon, rect):
    """
    Return True if (lat, lon) lies inside the rectangle defined by two diagonal corners.
    """
    lat1, lon1, lat2, lon2 = rect
    min_lat, max_lat = min(lat1, lat2), max(lat1, lat2)
    min_lon, max_lon = min(lon1, lon2), max(lon1, lon2)
    return (min_lat <= lat <= max_lat) and (min_lon <= lon <= max_lon)

def point_in_circle(lat, lon, circle):
    """
    Return True if (lat, lon) lies inside the circle defined by center (lat, lon) and radius (in meters).
    """
    center_lat, center_lon, radius = circle
    return haversine(lat, lon, center_lat, center_lon) <= radius

def point_in_circle_vicinity(lat, lon, circle, global_vicinity=None):
    """
    Return True if (lat, lon) is within the circle’s removal region expanded by its vicinity.
    If global_vicinity is provided, that value (in meters) is used; otherwise, the default is the circle’s radius.
    """
    center_lat, center_lon, radius = circle
    effective_vicinity = global_vicinity if global_vicinity is not None else radius
    return haversine(lat, lon, center_lat, center_lon) <= (radius + effective_vicinity)

def point_in_expanded_rectangle(lat, lon, rect, global_vicinity=None):
    """
    Return True if (lat, lon) lies within the rectangle expanded outward by the vicinity.
    For a rectangle defined by two diagonal corners, if global_vicinity is provided that value is used;
    otherwise the default vicinity is half of the rectangle’s smallest side (in meters).
    """
    lat1, lon1, lat2, lon2 = rect
    min_lat, max_lat = min(lat1, lat2), max(lat1, lat2)
    min_lon, max_lon = min(lon1, lon2), max(lon1, lon2)
    center_lat = (min_lat + max_lat) / 2.0
    width = haversine(center_lat, min_lon, center_lat, max_lon)
    height = haversine(min_lat, (min_lon+max_lon)/2.0, max_lat, (min_lon+max_lon)/2.0)
    default_vicinity = min(width, height) / 2.0
    effective_vicinity = global_vicinity if global_vicinity is not None else default_vicinity
    # Convert effective vicinity from meters to degrees (approximate).
    d_lat = effective_vicinity / 111111.0
    d_lon = effective_vicinity / (111111.0 * math.cos(math.radians(center_lat)))
    expanded_min_lat = min_lat - d_lat
    expanded_max_lat = max_lat + d_lat
    expanded_min_lon = min_lon - d_lon
    expanded_max_lon = max_lon + d_lon
    return (expanded_min_lat <= lat <= expanded_max_lat) and (expanded_min_lon <= lon <= expanded_max_lon)

def process_gpx_with_stats(input_file, output_file, rects, circles, max_stray_length, remove_stray, max_stray_vicinity):
    """
    Process the GPX file by:
      1. Removing track points that fall inside any manual removal region (rectangles and/or circles),
         splitting the track segments when points are removed.
      2. For each remaining segment, if its total length is <= max_stray_length, check whether any of its
         points lie within the "vicinity" of each manual region's outline.
         For circles, the default vicinity is half the circle’s diameter (its radius);
         for rectangles, the default is half of the rectangle’s smallest side.
         If a segment qualifies as stray for a region, it is logged for that region.
      3. If remove_stray is True, segments flagged as stray for any region are removed from the final output.
      
    In –v/–d mode, the script logs:
      - The number of points removed per manual region.
      - For each manual region, the count and length statistics of stray segments (within that region’s vicinity).
    """

    tree = ET.parse(input_file)
    root = tree.getroot()
    # Detect the namespace from the root element.
    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag[1:root.tag.find("}")]
        ns = {"default": uri}
        ET.register_namespace("", uri)
    else:
        ns = {"default": ""}

    total_points_removed = 0
    rect_removed_counts = [0] * len(rects)
    circle_removed_counts = [0] * len(circles)
    new_segments = []  # Will collect new <trkseg> elements.

    # First pass: Remove points inside the specified regions.
    for trk in root.findall("default:trk", ns):
        for trkseg in trk.findall("default:trkseg", ns):
            segments_from_trkseg = []
            current_seg_points = []
            for trkpt in trkseg.findall("default:trkpt", ns):
                lat = float(trkpt.attrib["lat"])
                lon = float(trkpt.attrib["lon"])
                removed = False
                for idx, rect in enumerate(rects):
                    if point_in_rect(lat, lon, rect):
                        rect_removed_counts[idx] += 1
                        removed = True
                for idx, circle in enumerate(circles):
                    if point_in_circle(lat, lon, circle):
                        circle_removed_counts[idx] += 1
                        removed = True
                if removed:
                    total_points_removed += 1
                    if current_seg_points:
                        segments_from_trkseg.append(current_seg_points)
                        current_seg_points = []
                    continue
                else:
                    current_seg_points.append(trkpt)
            if current_seg_points:
                segments_from_trkseg.append(current_seg_points)
            trk.remove(trkseg)
            for seg_points in segments_from_trkseg:
                if ns["default"]:
                    new_seg = ET.Element("{" + ns["default"] + "}trkseg")
                else:
                    new_seg = ET.Element("trkseg")
                for pt in seg_points:
                    new_seg.append(pt)
                new_segments.append(new_seg)

    # Log point removal statistics.
    logging.info("Total points removed: %d", total_points_removed)
    for idx, rect in enumerate(rects, start=1):
        logging.info("Manual rectangle %d: Removed %d points", idx, rect_removed_counts[idx-1])
    for idx, circle in enumerate(circles, start=1):
        logging.info("Manual circle %d: Removed %d points", idx, circle_removed_counts[idx-1])

    # Second pass: Identify stray segments per manual region.
    # We'll index each segment from new_segments.
    global_stray_indices = set()
    stray_rect = [ [] for _ in rects ]    # For each rectangle: list of segment lengths.
    stray_circle = [ [] for _ in circles ]  # For each circle: list of segment lengths.
    for seg_idx, seg in enumerate(new_segments):
        pts = seg.findall("{" + ns["default"] + "}trkpt")
        if len(pts) < 2:
            seg_length = 0.0
        else:
            seg_length = 0.0
            prev_pt = pts[0]
            for pt in pts[1:]:
                lat1 = float(prev_pt.attrib["lat"])
                lon1 = float(prev_pt.attrib["lon"])
                lat2 = float(pt.attrib["lat"])
                lon2 = float(pt.attrib["lon"])
                seg_length += haversine(lat1, lon1, lat2, lon2)
                prev_pt = pt
        # Only consider segments below the maximum stray length.
        if seg_length <= max_stray_length:
            # Check for each manual rectangle.
            for i, rect in enumerate(rects):
                for pt in pts:
                    lat = float(pt.attrib["lat"])
                    lon = float(pt.attrib["lon"])
                    if point_in_expanded_rectangle(lat, lon, rect, max_stray_vicinity):
                        stray_rect[i].append(seg_length)
                        global_stray_indices.add(seg_idx)
                        break
            # Check for each manual circle.
            for i, circle in enumerate(circles):
                for pt in pts:
                    lat = float(pt.attrib["lat"])
                    lon = float(pt.attrib["lon"])
                    if point_in_circle_vicinity(lat, lon, circle, max_stray_vicinity):
                        stray_circle[i].append(seg_length)
                        global_stray_indices.add(seg_idx)
                        break

    # Log stray segment statistics per region.
    for i, lengths in enumerate(stray_rect, start=1):
        if lengths:
            logging.info("Manual rectangle %d: Stray segments (length <= %.2f m) in vicinity: %d segments", i, max_stray_length, len(lengths))
            logging.info("    Lengths: min=%.2f m, max=%.2f m, avg=%.2f m",
                         min(lengths), max(lengths), sum(lengths)/len(lengths))
        else:
            logging.info("Manual rectangle %d: No stray segments (length <= %.2f m) found in vicinity.", i, max_stray_length)
    for i, lengths in enumerate(stray_circle, start=1):
        if lengths:
            logging.info("Manual circle %d: Stray segments (length <= %.2f m) in vicinity: %d segments", i, max_stray_length, len(lengths))
            logging.info("    Lengths: min=%.2f m, max=%.2f m, avg=%.2f m",
                         min(lengths), max(lengths), sum(lengths)/len(lengths))
        else:
            logging.info("Manual circle %d: No stray segments (length <= %.2f m) found in vicinity.", i, max_stray_length)

    # Third pass: Remove stray segments if specified.
    if remove_stray:
        logging.info("Removing stray segments within vicinity (total segments to remove: %d)", len(global_stray_indices))
        final_segments = [ seg for idx, seg in enumerate(new_segments) if idx not in global_stray_indices ]
    else:
        logging.info("Stray segments are retained in the output.")
        final_segments = new_segments

    # Update each track: remove old <trkseg> elements and append final segments.
    for trk in root.findall("default:trk", ns):
        for child in list(trk):
            if child.tag == "{" + ns["default"] + "}trkseg":
                trk.remove(child)
        for seg in final_segments:
            trk.append(seg)

    tree.write(output_file, encoding="utf-8", xml_declaration=True)

def main():
    parser = argparse.ArgumentParser(
        description="Remove GPX track points in specified manual regions (rectangles and/or circles) and split tracks on discontinuities. "
                    "For each removal region, stray segments (segments shorter than or equal to --max-stray-length and within a vicinity) are logged. "
                    "Optionally, stray segments are removed."
    )
    # Positional input/output files.
    parser.add_argument("infile", nargs="?", help="Input GPX file")
    parser.add_argument("outfile", nargs="?", help="Output GPX file")
    # Named options.
    parser.add_argument("-i", "--input", help="Input GPX file")
    parser.add_argument("-o", "--output", help="Output GPX file")
    parser.add_argument("-r", "--rect", nargs=4, type=float, action="append",
                        metavar=("lat1", "lon1", "lat2", "lon2"),
                        help="Specify a rectangle removal region (two diagonal corners). May be repeated.")
    parser.add_argument("-c", "--circle", nargs=3, type=float, action="append",
                        metavar=("lat", "lon", "radius"),
                        help="Specify a circle removal region (center and radius in meters). May be repeated.")
    parser.add_argument("-s", "--remove-stray-segments", action="store_true",
                        help="Remove stray track segments (segments with length <= --max-stray-length and within vicinity of a removal region).")
    parser.add_argument("--max-stray-length", type=float, default=10.0,
                        help="Maximum length (in meters) for a track segment to be considered stray. Default is 10 m.")
    parser.add_argument("--max-stray-vicinity", type=float, default=None,
                        help="Vicinity (in meters) for stray segment detection. For circles, defaults to half the diameter (radius), "
                             "and for rectangles, to half the smallest side. If specified, this value is used for all shapes.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging.")

    args = parser.parse_args()

    if args.debug:
        log_level = logging.DEBUG
    elif args.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    logging.basicConfig(level=log_level, format="%(message)s")

    input_file = args.infile or args.input
    output_file = args.outfile or args.output
    if not input_file or not output_file:
        parser.error("Input and output GPX files must be specified either as positional arguments or via --input/--output.")

    manual_rects = args.rect if args.rect is not None else []
    manual_circles = args.circle if args.circle is not None else []
    if args.verbose or args.debug:
        if manual_rects:
            for idx, rect in enumerate(manual_rects, start=1):
                logging.info("Manual rectangle %d: (%.6f, %.6f) to (%.6f, %.6f)", idx, rect[0], rect[1], rect[2], rect[3])
        else:
            logging.info("No manual rectangle removal regions specified.")
        if manual_circles:
            for idx, circle in enumerate(manual_circles, start=1):
                logging.info("Manual circle %d: center=(%.6f, %.6f), radius=%.2f m", idx, circle[0], circle[1], circle[2])
        else:
            logging.info("No manual circle removal regions specified.")

    process_gpx_with_stats(input_file, output_file, manual_rects, manual_circles,
                           args.max_stray_length, args.remove_stray_segments, args.max_stray_vicinity)

if __name__ == "__main__":
    main()

