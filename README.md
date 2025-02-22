# GPX Anonymizer

This Python script processes a GPX file by removing track points that fall within specified manual regions and splitting track segments when discontinuities occur. This can be used when you want to implement anonymization to your GPX recordings in the vicinity of places of frequent occurence (e.g., similar to how Strava implements your privacy protection). It also detects "stray" track segments—those with a total length less than or equal to a user-specified threshold and that occur within a vicinity of each removal region—and can optionally remove them. Such processing can be useful before sharing your GPX files into OpenStreetMap.

## Features

- **Manual Region Removal:**  
  Specify removal regions as:
  - **Rectangles:** Use two diagonal corners.
  - **Circles:** Use a center and a radius.

- **Stray Segment Detection:**  
  After removing points, the script examines remaining track segments:
  - A segment is considered *stray* if its length is less than or equal to a specified maximum (default is 10 m).
  - Only segments within a vicinity of a removal region are flagged as stray.
    - **For circles:** The default vicinity is half the circle's diameter (i.e. its radius).
    - **For rectangles:** The default vicinity is half of the rectangle’s smallest side.
  - A global vicinity value can be provided using `--max-stray-vicinity`.

- **Logging:**  
  Detailed statistics are output in:
  - **Verbose mode** (`-v`): General statistics.
  - **Debug mode** (`-d`): More detailed logging.
  
  For each manual region, the script logs:
  - Number of points removed.
  - Number and length statistics of stray segments detected within that region’s vicinity.
  - Immediately after each region's statistics, information about stray segments detected (and removed, if applicable) is output.

- **Optional Removal of Stray Segments:**  
  Use the `-s` or `--remove-stray-segments` switch to remove stray segments from the final output.  
  **Note:** Removal of stray segments is performed separately for each specified region.

- **Flexible Command-Line Interface:**  
  Input and output files can be provided as positional arguments or with `-i/--input` and `-o/--output`.

## Requirements

- Python 3 (the script uses only standard libraries: `argparse`, `math`, `logging`, and `xml.etree.ElementTree`).

## Usage

Make the script executable:

    chmod +x gpx-anonymizer.py

### Command-Line Options

- **Input/Output Files:**
  - Positional:  

        gpx-anonymizer.py input.gpx output.gpx

  - Named: `-i INPUT`, `-o OUTPUT`

- **Manual Removal Regions:**
  - **Rectangle:**  

        -r lat1 lon1 lat2 lon2
        --rect lat1 lon1 lat2 lon2

    *Example:*  

        -r 40.0 -75.0 41.0 -74.0

  - **Circle:**  

        -c lat lon radius
        --circle lat lon radius

    *Example:*  

        -c 40.5 -74.5 500

- **Stray Segment Options:**
  - Remove stray segments:  

        -s
        --remove-stray-segments

  - Maximum stray segment length (in meters):  

        --max-stray-length 10.0

    (default: 10 m)

  - Vicinity for stray segment detection:  

        --max-stray-vicinity 15

    If not provided, for circles the default is half the circle's diameter (i.e. the circle's radius), and for rectangles the default is half of the smallest side.

- **Logging Options:**
  - Verbose logging:  

        -v
        --verbose

  - Debug logging:  

        -d
        --debug

    (higher verbosity than `-v`)

### Examples

1. **Positional Input/Output with Verbose Logging (Stray segments retained):**

        python3 gpx-anonymizer.py input.gpx output.gpx -v -r 40.0 -75.0 41.0 -74.0 -c 40.5 -74.5 100

2. **Named Options with Debug Logging and Removing Stray Segments (Global Vicinity = 15 m):**

        python3 gpx-anonymizer.py -i input.gpx -o output.gpx -d -s --max-stray-length 10 --max-stray-vicinity 15 \
            -r 40.0 -75.0 41.0 -74.0 -r 39.5 -75.5 40.5 -74.5 -c 40.5 -74.5 100

In the examples above, the script logs, for each specified manual region, the number of removed points and the stray segment statistics (number and length) immediately after processing. If the stray segment removal switch (`-s`) is used, any segment flagged as stray for any region is removed from the final GPX output.

## License

This project is distributed under the [GPLv3](LICENSE) license.
